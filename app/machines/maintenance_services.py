"""Service helpers for recurring machine maintenance plans."""

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import ErrorEntry, Machine, MaintenancePlan, Priority, Role, Task, TaskStatus
from app.security import has_dashboard_permission
from app.services.error_service import visible_errors_query
from app.services.recurring_issue_service import analyze_recurring_issues
from app.services.retrieval_service import knowledge_context_for_chat
from app.services.task_service import (
    get_department_for_payload,
    parse_date,
    parse_enum,
    visible_tasks_query,
)


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


def recommend_preventive_maintenance(user, limit=5):
    """Return read-only preventive maintenance recommendations from visible history."""
    if not has_dashboard_permission(user, "machines", "view"):
        return None, {"error": "machines view permission is required"}, 403
    try:
        limit_value = min(max(1, int(limit)), 20)
    except (TypeError, ValueError):
        return None, {"error": "limit must be an integer between 1 and 20"}, 400

    machine_signals = _machine_signal_map(user)
    recurring_trends = analyze_recurring_issues(user, days=30, min_occurrences=2, limit=20)
    recommendations = [
        _preventive_recommendation(
            machine,
            signals,
            user,
            _matching_recurring_trend(machine, recurring_trends.get("items", [])),
        )
        for machine, signals in machine_signals.items()
        if _signal_score(signals) >= 2
        or _matching_recurring_trend(machine, recurring_trends.get("items", []))
    ]
    recommendations.sort(
        key=lambda item: (item["score"], item["source_counts"]["errors"]),
        reverse=True,
    )
    return (
        {
            "items": recommendations[:limit_value],
            "count": min(len(recommendations), limit_value),
            "total_candidates": len(recommendations),
            "recurring_issues": recurring_trends,
        },
        None,
        200,
    )


def _machine_signal_map(user):
    """Return visible recurring maintenance signals grouped by machine."""
    signals = {}
    machines = Machine.query.order_by(Machine.name.asc()).all()
    for machine in machines:
        signals[machine] = {"tasks": [], "errors": []}

    if has_dashboard_permission(user, "tasks", "view"):
        tasks = visible_tasks_query(user).order_by(Task.updated_at.desc()).limit(200).all()
        for task in tasks:
            machine = _matching_machine(task.title, task.description, machines=machines)
            if machine:
                signals.setdefault(machine, {"tasks": [], "errors": []})["tasks"].append(task)

    if has_dashboard_permission(user, "errors", "view"):
        errors = visible_errors_query(user).order_by(ErrorEntry.created_at.desc()).limit(200).all()
        for entry in errors:
            machine = _matching_machine(entry.machine, entry.title, machines=machines)
            if machine:
                signals.setdefault(machine, {"tasks": [], "errors": []})["errors"].append(entry)
    return signals


def _matching_machine(*values, machines):
    """Return the first machine referenced by text values."""
    text = " ".join(str(value or "").lower() for value in values)
    return next((machine for machine in machines if machine.name.lower() in text), None)


def _signal_score(signals):
    """Return a simple recurrence score for task and error signals."""
    return len(signals["tasks"]) + (len(signals["errors"]) * 2)


def _preventive_recommendation(machine, signals, user, recurring_trend=None):
    """Return one preventive maintenance recommendation for a machine."""
    recurring_score = (recurring_trend or {}).get("occurrence_count", 0) * 15
    score = min(100, (_signal_score(signals) * 20) + recurring_score)
    query = f"{machine.name} Wartung Stoerung Fehler wiederkehrend"
    _context, rag_sources = knowledge_context_for_chat(query, user, limit=3)
    return {
        "machine": machine.to_dict(),
        "score": score,
        "risk_level": _preventive_risk_level(score),
        "reason": _preventive_reason(signals, recurring_trend),
        "recommended_action": _preventive_action(machine, signals, recurring_trend),
        "source_counts": {
            "tasks": len(signals["tasks"]),
            "errors": len(signals["errors"]),
            "rag_sources": len(rag_sources),
            "recurring_issues": 1 if recurring_trend else 0,
        },
        "evidence": _preventive_evidence(signals),
        "sources": rag_sources,
        "recurring_issue": recurring_trend,
    }


def _preventive_risk_level(score):
    """Return a risk level for a preventive recommendation score."""
    if score >= 80:
        return "critical"
    if score >= 60:
        return "high"
    if score >= 40:
        return "medium"
    return "low"


def _preventive_reason(signals, recurring_trend=None):
    """Return a concise German reason for recurring signals."""
    if recurring_trend:
        return (
            f"{recurring_trend['occurrence_count']} Vorkommen im Fehlertrend plus "
            f"{len(signals['tasks'])} Tasks und {len(signals['errors'])} Fehler."
        )
    return (
        f"{len(signals['tasks'])} sichtbare Tasks und "
        f"{len(signals['errors'])} Fehler deuten auf wiederkehrende Themen hin."
    )


def _preventive_action(machine, signals, recurring_trend=None):
    """Return a practical next action for preventive maintenance."""
    if recurring_trend:
        return recurring_trend["recommendation"]
    if signals["errors"]:
        return (
            f"Wartungsplan fuer {machine.name} pruefen: Fehlerursachen buendeln, "
            "Inspektionsintervall festlegen und Ersatzteile abgleichen."
        )
    return (
        f"Tasks zu {machine.name} auswerten und bei wiederkehrenden Symptomen "
        "einen praeventiven Wartungsplan anlegen."
    )


def _preventive_evidence(signals):
    """Return compact evidence entries for a recommendation."""
    task_items = [
        {
            "type": "task",
            "id": task.id,
            "title": task.title,
            "status": task.status.value,
            "date": task.updated_at.isoformat(),
        }
        for task in signals["tasks"][:3]
    ]
    error_items = [
        {
            "type": "error",
            "id": entry.id,
            "title": f"{entry.error_code} - {entry.title}",
            "machine": entry.machine,
            "date": entry.created_at.isoformat(),
        }
        for entry in signals["errors"][:3]
    ]
    return task_items + error_items


def _matching_recurring_trend(machine, trends):
    """Return a recurring trend matching the machine, if available."""
    machine_name = machine.name.strip().lower()
    for trend in trends:
        if trend.get("machine_id") == machine.id:
            return trend
        if str(trend.get("affected_machine") or "").strip().lower() == machine_name:
            return trend
    return None
