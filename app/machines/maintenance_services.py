"""Service helpers for recurring machine maintenance plans."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Machine, MaintenancePlan, Priority, Role, Task, TaskStatus
from app.security import has_dashboard_permission
from app.services.task_service import get_department_for_payload, parse_date, parse_enum


def visible_maintenance_plans_query(user):
    """Return maintenance plans visible to the current user."""
    query = MaintenancePlan.query
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(MaintenancePlan.department_id == user.department_id)
    return query


def parse_interval_days(value):
    """Parse and validate a recurrence interval in days."""
    try:
        interval_days = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("interval_days must be a number") from exc
    if interval_days < 1:
        raise ValueError("interval_days must be at least 1")
    return interval_days


def parse_optional_bool(value, default=True):
    """Parse optional boolean payload values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError("is_active must be a boolean")


def resolve_machine(machine_id):
    """Resolve an optional machine id from a plan payload."""
    if machine_id in (None, ""):
        return None
    try:
        parsed_id = int(machine_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("machine_id must be a valid machine id") from exc
    machine = db.session.get(Machine, parsed_id)
    if not machine:
        raise ValueError("machine_id does not reference an existing machine")
    return machine


def create_maintenance_plan(data, user):
    """Create a recurring maintenance plan."""
    try:
        title = str(data.get("title") or "").strip()
        if not title:
            raise ValueError("title is required")
        department = get_department_for_payload(data, user)
        plan = MaintenancePlan(
            title=title,
            description=str(data.get("description") or "").strip(),
            interval_days=parse_interval_days(data.get("interval_days")),
            next_due_date=parse_date(data.get("next_due_date")),
            priority=parse_enum(Priority, data.get("priority"), Priority.NORMAL),
            is_active=parse_optional_bool(data.get("is_active"), default=True),
            machine=resolve_machine(data.get("machine_id")),
            department=department,
            created_by=user.id,
        )
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    db.session.add(plan)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while creating maintenance plan"}, 500
    return plan, None, 201


def update_maintenance_plan(plan, data, user):
    """Apply a partial update to a recurring maintenance plan."""
    try:
        if "title" in data:
            title = str(data["title"] or "").strip()
            if not title:
                raise ValueError("title must not be empty")
            plan.title = title
        if "description" in data:
            plan.description = str(data["description"] or "").strip()
        if "interval_days" in data:
            plan.interval_days = parse_interval_days(data["interval_days"])
        if "next_due_date" in data:
            plan.next_due_date = parse_date(data["next_due_date"])
        if "priority" in data:
            plan.priority = parse_enum(Priority, data["priority"], plan.priority)
        if "is_active" in data:
            plan.is_active = parse_optional_bool(data["is_active"], default=plan.is_active)
        if "machine_id" in data:
            plan.machine = resolve_machine(data.get("machine_id"))
        if "department_id" in data or "department" in data:
            plan.department = get_department_for_payload(data, user)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while updating maintenance plan"}, 500
    return plan, None, 200


def delete_maintenance_plan(plan):
    """Delete a recurring maintenance plan."""
    try:
        db.session.delete(plan)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return {"error": "Database error while deleting maintenance plan"}, 500
    return None, 204


def get_visible_maintenance_plan(plan_id, user):
    """Return a visible maintenance plan by id, or None."""
    return visible_maintenance_plans_query(user).filter(MaintenancePlan.id == plan_id).first()


def advance_due_date(current_due_date, interval_days, generated_until):
    """Return the next due date after generated_until."""
    next_due_date = current_due_date + timedelta(days=interval_days)
    while next_due_date <= generated_until:
        next_due_date += timedelta(days=interval_days)
    return next_due_date


def task_payload_for_plan(plan):
    """Build the task fields for one maintenance plan run."""
    machine_label = f"{plan.machine.name}: " if plan.machine else ""
    title = f"Wartung: {machine_label}{plan.title}"[:160]
    description_parts = [
        plan.description,
        f"Wiederkehrender Wartungsplan #{plan.id}",
        f"Intervall: {plan.interval_days} Tage",
    ]
    if plan.machine:
        description_parts.append(f"Maschine: {plan.machine.name}")
    return {
        "title": title,
        "description": "\n".join(part for part in description_parts if part),
        "priority": plan.priority,
        "status": TaskStatus.OPEN,
        "due_date": plan.next_due_date,
        "department": plan.department,
        "created_by": plan.created_by,
    }


def generate_due_maintenance_tasks(user, generated_until=None):
    """Generate one open task for each due active maintenance plan."""
    if not has_dashboard_permission(user, "tasks", "write"):
        return None, {"error": "tasks write permission is required"}, 403
    target_date = generated_until or date.today()
    due_plans = (
        visible_maintenance_plans_query(user)
        .filter(
            MaintenancePlan.is_active.is_(True),
            MaintenancePlan.next_due_date <= target_date,
        )
        .order_by(MaintenancePlan.next_due_date.asc(), MaintenancePlan.id.asc())
        .all()
    )

    generated = []
    now = datetime.now(UTC)
    for plan in due_plans:
        payload = task_payload_for_plan(plan)
        task = Task(**payload)
        db.session.add(task)
        db.session.flush()
        plan.last_generated_task = task
        plan.last_generated_at = now
        plan.next_due_date = advance_due_date(
            plan.next_due_date,
            plan.interval_days,
            target_date,
        )
        generated.append({"plan": plan.to_dict(), "task": task.to_dict()})

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while generating maintenance tasks"}, 500

    return {"generated_count": len(generated), "items": generated}, None, 200
