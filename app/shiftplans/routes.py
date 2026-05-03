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
    """Return generated shift plans with their entries."""
    plans = ShiftPlan.query.order_by(ShiftPlan.created_at.desc()).all()
    access_level = employee_access_level(current_user())
    return jsonify([plan.to_dict(access_level) for plan in plans])


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
