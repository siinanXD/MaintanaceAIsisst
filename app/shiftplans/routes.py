from datetime import datetime

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Role, ShiftPlan, ShiftPlanChangeLog, ShiftPlanEntry
from app.responses import error_response, service_error_response, success_response
from app.security import (
    current_user,
    dashboard_permission_required,
    employee_access_level,
    employee_access_required,
    roles_required,
)
from app.shiftplans.services import (
    calendar_entries_for_user,
    generate_shift_plan,
    hours_between,
)


shiftplans_bp = Blueprint("shiftplans", __name__)


@shiftplans_bp.get("")
@dashboard_permission_required("shiftplans", "view")
def list_shiftplans():
    """Return shift plans — admins see all, others see only published."""
    user = current_user()
    query = ShiftPlan.query.order_by(ShiftPlan.created_at.desc())
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(ShiftPlan.status == "published")
    plans = query.all()
    access_level = employee_access_level(user)
    return jsonify([plan.to_dict(access_level) for plan in plans])


@shiftplans_bp.patch("/<int:plan_id>/publish")
@dashboard_permission_required("shiftplans", "write")
def publish_shiftplan(plan_id):
    """Toggle a shift plan between draft and published."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren koennen Plaene veroeffentlichen", 403)
    plan = ShiftPlan.query.get_or_404(plan_id)
    if plan.is_published:
        plan.status = "draft"
        plan.published_at = None
    else:
        plan.status = "published"
        plan.published_at = datetime.utcnow()
    db.session.add(
        ShiftPlanChangeLog(
            plan_id=plan.id,
            user_id=current_user().id,
            action="publish" if plan.is_published else "unpublish",
        )
    )
    db.session.commit()
    access_level = employee_access_level(current_user())
    return success_response(plan.to_dict(access_level), message="Status aktualisiert")


@shiftplans_bp.get("/calendar")
@dashboard_permission_required("dashboard", "view")
def shiftplan_calendar():
    """Return the current user's or selected employee's shift calendar."""
    payload, error, status = calendar_entries_for_user(
        current_user(),
        employee_id=request.args.get("employee_id"),
        start_date=request.args.get("start_date"),
        days=request.args.get("days", 14),
        plan_id=request.args.get("plan_id"),
    )
    if error:
        return service_error_response(error, status)
    return jsonify(payload), status


@shiftplans_bp.post("/generate")
@dashboard_permission_required("shiftplans", "write")
@employee_access_required("shift")
def generate():
    """Generate and persist a shift plan for the selected department."""
    plan, error, status = generate_shift_plan(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    access_level = employee_access_level(current_user())
    payload = plan.to_dict(access_level)
    payload["warnings"] = getattr(plan, "warnings", [])
    payload["coverage_summary"] = getattr(plan, "coverage_summary", {})
    return jsonify(payload), status


@shiftplans_bp.delete("/<int:plan_id>")
@dashboard_permission_required("shiftplans", "write")
def delete_shiftplan(plan_id):
    """Delete a generated shift plan and its entries."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren koennen Schichtplaene loeschen", 403)
    plan = ShiftPlan.query.get_or_404(plan_id)
    db.session.delete(plan)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# Entry-level editing endpoints
# ---------------------------------------------------------------------------


@shiftplans_bp.patch("/entries/<int:entry_id>")
@dashboard_permission_required("shiftplans", "write")
def update_entry(entry_id):
    """Manually update a single shift plan entry and log the change."""
    entry = ShiftPlanEntry.query.get_or_404(entry_id)
    data = request.get_json(silent=True) or {}
    user = current_user()

    allowed_fields = {"shift", "start_time", "end_time", "notes", "machine_id"}
    changes = []
    for field in allowed_fields:
        if field not in data:
            continue
        old_value = str(getattr(entry, field))
        setattr(entry, field, data[field])
        changes.append((field, old_value, str(data[field])))

    if not changes:
        return error_response("Keine Felder zum Aktualisieren angegeben", 400)

    if entry.shift not in ("Frei", "Urlaub") and entry.start_time and entry.end_time:
        try:
            h = hours_between(entry.start_time, entry.end_time)
        except ValueError:
            return error_response("Ungueltige Start- oder Endzeit", 400)
        if h > 10:
            return error_response(
                "Max. 10 Stunden pro Schicht erlaubt (ArbZG §3)", 400
            )

    for field_name, old_val, new_val in changes:
        db.session.add(
            ShiftPlanChangeLog(
                entry_id=entry.id,
                plan_id=entry.plan_id,
                user_id=user.id,
                action="update",
                field_name=field_name,
                old_value=old_val,
                new_value=new_val,
            )
        )

    db.session.commit()
    return success_response(entry.to_dict(), message="Eintrag aktualisiert")


@shiftplans_bp.patch("/entries/<int:entry_id>/move")
@dashboard_permission_required("shiftplans", "write")
def move_entry(entry_id):
    """Move or swap a shift entry. Chip-to-chip uses target_entry_id for deterministic swap."""
    from app.shiftplans.services import SHIFT_WINDOWS, parse_date
    entry = ShiftPlanEntry.query.get_or_404(entry_id)
    data = request.get_json(silent=True) or {}
    user = current_user()

    target_entry_id = data.get("target_entry_id")
    if target_entry_id:
        existing = db.session.get(ShiftPlanEntry, int(target_entry_id))
        if not existing:
            return error_response("Ziel-Eintrag nicht gefunden", 404)
        if existing.plan_id != entry.plan_id:
            return error_response("Einträge gehören zu verschiedenen Plänen", 400)
        if existing.id == entry.id:
            return success_response(
                db.session.get(ShiftPlan, entry.plan_id).to_dict(employee_access_level(user)),
                message="Kein Tausch nötig",
            )
    else:
        try:
            target_date = parse_date(data.get("target_date"))
        except ValueError as exc:
            return error_response(str(exc), 400)
        target_shift = str(data.get("target_shift") or "").strip()
        if not target_shift:
            return error_response("target_shift erforderlich", 400)

        existing = ShiftPlanEntry.query.filter(
            ShiftPlanEntry.plan_id   == entry.plan_id,
            ShiftPlanEntry.work_date == target_date,
            ShiftPlanEntry.shift     == target_shift,
            ShiftPlanEntry.id        != entry.id,
        ).first()

    if existing:
        # Swap the slot (date+shift+times) between the two entries while keeping employee_ids.
        # This avoids the (plan_id, employee_id, work_date) unique constraint violation.
        old_emp_a = entry.employee_id
        old_emp_b = existing.employee_id
        # Swap slot data: entry moves to existing's slot, existing moves to entry's slot
        old_date_a, old_shift_a = entry.work_date, entry.shift
        old_start_a, old_end_a = entry.start_time, entry.end_time
        entry.work_date   = existing.work_date
        entry.shift       = existing.shift
        entry.start_time  = existing.start_time
        entry.end_time    = existing.end_time
        existing.work_date  = old_date_a
        existing.shift      = old_shift_a
        existing.start_time = old_start_a
        existing.end_time   = old_end_a
        db.session.flush()
        db.session.add(ShiftPlanChangeLog(
            entry_id=entry.id, plan_id=entry.plan_id, user_id=user.id,
            action="swap", field_name="employee_id",
            old_value=str(old_emp_a), new_value=str(old_emp_b),
        ))
        db.session.add(ShiftPlanChangeLog(
            entry_id=existing.id, plan_id=existing.plan_id, user_id=user.id,
            action="swap", field_name="employee_id",
            old_value=str(old_emp_b), new_value=str(old_emp_a),
        ))
    else:
        # Check if the entry's employee already has an entry on the target date (different shift)
        conflict = ShiftPlanEntry.query.filter(
            ShiftPlanEntry.plan_id     == entry.plan_id,
            ShiftPlanEntry.employee_id == entry.employee_id,
            ShiftPlanEntry.work_date   == target_date,
            ShiftPlanEntry.id          != entry.id,
        ).first()
        if conflict:
            return error_response(
                "Mitarbeiter hat bereits einen Eintrag an diesem Tag", 409
            )
        old_val = f"{entry.work_date.isoformat()} {entry.shift}"
        entry.work_date = target_date
        entry.shift     = target_shift
        if target_shift in SHIFT_WINDOWS:
            entry.start_time, entry.end_time = SHIFT_WINDOWS[target_shift]
        db.session.flush()
        db.session.add(ShiftPlanChangeLog(
            entry_id=entry.id, plan_id=entry.plan_id, user_id=user.id,
            action="move", old_value=old_val,
            new_value=f"{target_date.isoformat()} {target_shift}",
        ))

    db.session.commit()
    plan = db.session.get(ShiftPlan, entry.plan_id)
    return success_response(plan.to_dict(employee_access_level(user)), message="Eintrag verschoben")


@shiftplans_bp.delete("/entries/<int:entry_id>")
@dashboard_permission_required("shiftplans", "write")
def delete_entry(entry_id):
    """Delete a single shift plan entry (admin only) and log the action."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren koennen Eintraege loeschen", 403)
    entry = ShiftPlanEntry.query.get_or_404(entry_id)
    db.session.add(
        ShiftPlanChangeLog(
            entry_id=entry.id,
            plan_id=entry.plan_id,
            user_id=current_user().id,
            action="delete",
            old_value=f"{entry.shift} {entry.work_date.isoformat()}",
        )
    )
    db.session.delete(entry)
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@shiftplans_bp.get("/<int:plan_id>/changelog")
@roles_required(Role.MASTER_ADMIN)
def plan_changelog(plan_id):
    """Return the full change history for a shift plan (admin only)."""
    ShiftPlan.query.get_or_404(plan_id)
    logs = (
        ShiftPlanChangeLog.query
        .filter_by(plan_id=plan_id)
        .order_by(ShiftPlanChangeLog.changed_at.desc())
        .all()
    )
    return success_response([log.to_dict() for log in logs], message="Changelog geladen")
