"""Shift planning API routes."""

from datetime import UTC, datetime
from io import BytesIO

from flask import Blueprint, jsonify, request, send_file

from app.extensions import db
from app.models import (
    Department,
    Machine,
    Role,
    ShiftPlan,
    ShiftPlanChangeLog,
    ShiftPlanEntry,
    VacationRequest,
)
from app.responses import error_response, service_error_response, success_response
from app.security import (
    current_user,
    dashboard_permission_required,
    employee_access_level,
    employee_access_required,
    roles_required,
)
from app.services.audit_service import create_audit_log
from app.services.in_app_notification_service import notify_shiftplan_change
from app.services.operations_tracking_service import record_event
from app.shiftplans.generator import qualification_map_for
from app.shiftplans.rules import validate_candidate_assignment
from app.shiftplans.services import (
    build_template_coverage_summary,
    calendar_entries_for_user,
    conflict_summary,
    conflicts_for_plan,
    export_shiftplan_xlsx,
    generate_shift_plan,
    hours_between,
    is_known_shift_model_value,
    machines_for_plan,
    preview_shift_plan,
    refresh_plan_coverage_slots,
    replace_plan_coverage_slots,
    update_employee_rotation_state,
    validate_shiftplan_payload,
)
from app.shiftplans.templates import list_shift_templates, resolve_shift_template

shiftplans_bp = Blueprint("shiftplans", __name__)


def department_for_plan(plan):
    """Return the department model matching a shift plan's department name."""
    if not plan or not plan.department:
        return None
    return Department.query.filter_by(name=plan.department).first()


def refresh_plan_operations_metrics(plan):
    """Refresh persisted conflict and coverage counters for a shift plan."""
    payload = conflicts_for_plan(plan)
    summary = payload.get("summary") or {}
    coverage = payload.get("coverage_summary") or {}
    required_slots = coverage.get("required_slots") or 0
    assigned_slots = coverage.get("assigned_slots") or 0
    plan.coverage_percent = (
        round((assigned_slots / required_slots) * 100, 2) if required_slots else 0
    )
    plan.conflict_count = int(summary.get("total") or 0)
    plan.critical_conflict_count = int(summary.get("critical") or 0)
    return payload


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


def visible_plan_or_404(plan_id, user):
    """Return a plan when the current user may see it."""
    plan = db.get_or_404(ShiftPlan, plan_id)
    if user.role != Role.MASTER_ADMIN and not plan.is_published:
        return None
    return plan


@shiftplans_bp.get("/models")
@dashboard_permission_required("shiftplans", "view")
def list_shiftplan_models():
    """Return supported shift model templates for future frontend selection."""
    return success_response(
        [template.to_dict() for template in list_shift_templates()],
        message="Schichtmodelle geladen",
    )


@shiftplans_bp.patch("/<int:plan_id>/publish")
@dashboard_permission_required("shiftplans", "write")
def publish_shiftplan(plan_id):
    """Toggle a shift plan between draft and published."""
    user = current_user()
    if user.role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren koennen Plaene veroeffentlichen", 403)
    plan = db.get_or_404(ShiftPlan, plan_id)
    before = {
        "id": plan.id,
        "status": plan.status,
        "published_at": plan.published_at.isoformat() if plan.published_at else None,
    }
    if plan.is_published:
        plan.status = "draft"
        plan.published_at = None
    else:
        plan.status = "published"
        plan.published_at = datetime.now(UTC)
    db.session.add(
        ShiftPlanChangeLog(
            plan_id=plan.id,
            user_id=user.id,
            action="publish" if plan.is_published else "unpublish",
        )
    )
    notify_shiftplan_change(
        plan,
        user,
        "publish" if plan.is_published else "unpublish",
    )
    plan.change_count = (plan.change_count or 0) + 1
    refresh_plan_operations_metrics(plan)
    record_event(
        "shiftplan.published" if plan.is_published else "shiftplan.unpublished",
        "workforce",
        entity_type="shift_plan",
        entity_id=plan.id,
        user=user,
        department=department_for_plan(plan),
        source="shiftplans",
        metadata={
            "status": plan.status,
            "coverage_percent": plan.coverage_percent,
            "conflict_count": plan.conflict_count,
        },
    )
    db.session.commit()
    create_audit_log(
        user,
        "shiftplan.publish" if plan.is_published else "shiftplan.unpublish",
        "shiftplan",
        plan.id,
        before=before,
        after={
            "id": plan.id,
            "status": plan.status,
            "published_at": plan.published_at.isoformat() if plan.published_at else None,
        },
        commit=True,
    )
    access_level = employee_access_level(user)
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


@shiftplans_bp.get("/<int:plan_id>/conflicts")
@dashboard_permission_required("shiftplans", "view")
def plan_conflicts(plan_id):
    """Return structured conflicts for a persisted shift plan."""
    plan = visible_plan_or_404(plan_id, current_user())
    if not plan:
        return error_response("Forbidden", 403)
    return success_response(conflicts_for_plan(plan), message="Konflikte geladen")


@shiftplans_bp.post("/validate")
@dashboard_permission_required("shiftplans", "view")
def validate_shiftplan():
    """Validate an existing or ad-hoc shift plan payload."""
    payload, error, status = validate_shiftplan_payload(request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    return success_response(payload, status, "Schichtplan validiert")


@shiftplans_bp.get("/<int:plan_id>/export.xlsx")
@dashboard_permission_required("shiftplans", "view")
def export_shiftplan(plan_id):
    """Download a shift plan as an XLSX workbook."""
    plan = visible_plan_or_404(plan_id, current_user())
    if not plan:
        return error_response("Forbidden", 403)
    workbook_bytes = export_shiftplan_xlsx(plan)
    filename = f"schichtplan_{plan.id}.xlsx"
    return send_file(
        BytesIO(workbook_bytes),
        mimetype=("application/vnd.openxmlformats-officedocument." "spreadsheetml.sheet"),
        as_attachment=True,
        download_name=filename,
    )


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
    record_event(
        "shiftplan.generated",
        "workforce",
        entity_type="shift_plan",
        entity_id=plan.id,
        user=current_user(),
        department=department_for_plan(plan),
        source="shiftplans",
        metadata={
            "days": plan.days,
            "coverage_percent": plan.coverage_percent,
            "conflict_count": plan.conflict_count,
            "critical_conflict_count": plan.critical_conflict_count,
        },
        commit=True,
    )
    access_level = employee_access_level(current_user())
    payload = plan.to_dict(access_level)
    payload["warnings"] = getattr(plan, "warnings", [])
    payload["conflicts"] = getattr(plan, "warnings", [])
    payload["coverage_summary"] = getattr(plan, "coverage_summary", {})
    payload["unassigned_slots"] = [slot.to_dict() for slot in plan.coverage_slots]
    payload["fairness_summary"] = getattr(plan, "fairness_summary", {})
    return jsonify(payload), status


@shiftplans_bp.post("/preview")
@dashboard_permission_required("shiftplans", "write")
@employee_access_required("shift")
def preview():
    """Generate a dry-run shift plan without persisting it."""
    payload, error, status = preview_shift_plan(request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    return success_response(payload, status, "Schichtplan-Vorschau erstellt")


@shiftplans_bp.delete("/<int:plan_id>")
@dashboard_permission_required("shiftplans", "write")
def delete_shiftplan(plan_id):
    """Delete a generated shift plan and its entries."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren koennen Schichtplaene loeschen", 403)
    user = current_user()
    plan = db.get_or_404(ShiftPlan, plan_id)
    record_event(
        "shiftplan.deleted",
        "workforce",
        entity_type="shift_plan",
        entity_id=plan.id,
        user=user,
        department=department_for_plan(plan),
        source="shiftplans",
        metadata={"title": plan.title, "status": plan.status},
    )
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
    entry = db.get_or_404(ShiftPlanEntry, entry_id)
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
            return error_response("Max. 10 Stunden pro Schicht erlaubt (ArbZG §3)", 400)

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

    plan = db.session.get(ShiftPlan, entry.plan_id)
    notify_shiftplan_change(plan, user, "update", entry=entry)
    plan.change_count = (plan.change_count or 0) + len(changes)
    conflict_payload = refresh_plan_operations_metrics(plan)
    refresh_plan_coverage_slots(plan)
    update_employee_rotation_state([entry.employee])
    record_event(
        "shiftplan.entry_updated",
        "workforce",
        entity_type="shift_plan_entry",
        entity_id=entry.id,
        user=user,
        department=department_for_plan(plan),
        machine_id=entry.machine_id,
        source="shiftplans",
        metadata={
            "plan_id": plan.id,
            "fields": [field_name for field_name, _old, _new in changes],
            "conflict_count": plan.conflict_count,
        },
    )
    db.session.commit()
    payload = plan.to_dict(employee_access_level(user))
    payload["conflicts"] = conflict_payload
    return success_response(payload, message="Eintrag aktualisiert")


@shiftplans_bp.patch("/entries/<int:entry_id>/move")
@dashboard_permission_required("shiftplans", "write")
def move_entry(entry_id):
    """Move or swap a shift entry. Chip-to-chip uses target_entry_id for deterministic swap."""
    from app.shiftplans.services import SHIFT_WINDOWS, parse_date

    entry = db.get_or_404(ShiftPlanEntry, entry_id)
    data = request.get_json(silent=True) or {}
    user = current_user()
    return move_entry_without_swap(entry, data, user)

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
            ShiftPlanEntry.plan_id == entry.plan_id,
            ShiftPlanEntry.work_date == target_date,
            ShiftPlanEntry.shift == target_shift,
            ShiftPlanEntry.id != entry.id,
        ).first()

    if existing:
        # Swap the slot (date+shift+times) between the two entries while keeping employee_ids.
        # This avoids the (plan_id, employee_id, work_date) unique constraint violation.
        old_emp_a = entry.employee_id
        old_emp_b = existing.employee_id
        # Swap slot data: entry moves to existing's slot, existing moves to entry's slot
        old_date_a, old_shift_a = entry.work_date, entry.shift
        old_start_a, old_end_a = entry.start_time, entry.end_time
        entry.work_date = existing.work_date
        entry.shift = existing.shift
        entry.start_time = existing.start_time
        entry.end_time = existing.end_time
        existing.work_date = old_date_a
        existing.shift = old_shift_a
        existing.start_time = old_start_a
        existing.end_time = old_end_a
        db.session.flush()
        db.session.add(
            ShiftPlanChangeLog(
                entry_id=entry.id,
                plan_id=entry.plan_id,
                user_id=user.id,
                action="swap",
                field_name="employee_id",
                old_value=str(old_emp_a),
                new_value=str(old_emp_b),
            )
        )
        db.session.add(
            ShiftPlanChangeLog(
                entry_id=existing.id,
                plan_id=existing.plan_id,
                user_id=user.id,
                action="swap",
                field_name="employee_id",
                old_value=str(old_emp_b),
                new_value=str(old_emp_a),
            )
        )
        notify_shiftplan_change(
            db.session.get(ShiftPlan, entry.plan_id),
            user,
            "swap",
            entry=entry,
        )
        notify_shiftplan_change(
            db.session.get(ShiftPlan, existing.plan_id),
            user,
            "swap",
            entry=existing,
        )
    else:
        # Check if the entry's employee already has an entry on the target date (different shift)
        conflict = ShiftPlanEntry.query.filter(
            ShiftPlanEntry.plan_id == entry.plan_id,
            ShiftPlanEntry.employee_id == entry.employee_id,
            ShiftPlanEntry.work_date == target_date,
            ShiftPlanEntry.id != entry.id,
        ).first()
        if conflict:
            return error_response("Mitarbeiter hat bereits einen Eintrag an diesem Tag", 409)
        old_val = f"{entry.work_date.isoformat()} {entry.shift}"
        entry.work_date = target_date
        entry.shift = target_shift
        if target_shift in SHIFT_WINDOWS:
            entry.start_time, entry.end_time = SHIFT_WINDOWS[target_shift]
        db.session.flush()
        db.session.add(
            ShiftPlanChangeLog(
                entry_id=entry.id,
                plan_id=entry.plan_id,
                user_id=user.id,
                action="move",
                old_value=old_val,
                new_value=f"{target_date.isoformat()} {target_shift}",
            )
        )
        notify_shiftplan_change(
            db.session.get(ShiftPlan, entry.plan_id),
            user,
            "move",
            entry=entry,
        )

    plan = db.session.get(ShiftPlan, entry.plan_id)
    plan.change_count = (plan.change_count or 0) + (2 if existing else 1)
    conflict_payload = refresh_plan_operations_metrics(plan)
    record_event(
        "shiftplan.entry_swapped" if existing else "shiftplan.entry_moved",
        "workforce",
        entity_type="shift_plan_entry",
        entity_id=entry.id,
        user=user,
        department=department_for_plan(plan),
        machine_id=entry.machine_id,
        source="shiftplans",
        metadata={
            "plan_id": plan.id,
            "target_entry_id": getattr(existing, "id", None),
            "conflict_count": plan.conflict_count,
        },
    )
    db.session.commit()
    payload = plan.to_dict(employee_access_level(user))
    payload["conflicts"] = conflict_payload
    return success_response(payload, message="Eintrag verschoben")


def move_entry_without_swap(entry, data, user):
    """Move a shift entry into a target slot without swapping occupants."""
    from app.shiftplans.services import SHIFT_WINDOWS, parse_date

    plan = db.session.get(ShiftPlan, entry.plan_id)
    try:
        target_entry = move_target_entry(data, entry)
        target_date, target_shift, target_machine_id = move_target_slot(
            data,
            entry,
            target_entry,
            parse_date,
        )
    except ValueError as exc:
        return error_response(str(exc), 400)

    if target_shift not in SHIFT_WINDOWS:
        return error_response("target_shift ist kein gueltiger Arbeitsschicht-Key", 400)
    target_machine = db.session.get(Machine, target_machine_id) if target_machine_id else None
    capacity_error = target_slot_capacity_error(
        plan,
        entry,
        target_date,
        target_shift,
        target_machine,
    )
    if capacity_error:
        return error_response(capacity_error, 409)
    rule_error = manual_move_rule_error(
        entry,
        plan,
        target_date,
        target_shift,
        target_machine,
    )
    if rule_error:
        return error_response(rule_error, 409)

    old_val = f"{entry.work_date.isoformat()} {entry.shift}"
    entry.work_date = target_date
    entry.shift = target_shift
    entry.machine_id = target_machine_id
    entry.start_time, entry.end_time = SHIFT_WINDOWS[target_shift]
    db.session.flush()
    db.session.add(
        ShiftPlanChangeLog(
            entry_id=entry.id,
            plan_id=entry.plan_id,
            user_id=user.id,
            action="move",
            old_value=old_val,
            new_value=f"{target_date.isoformat()} {target_shift}",
        )
    )
    notify_shiftplan_change(plan, user, "move", entry=entry)
    plan.change_count = (plan.change_count or 0) + 1
    machines = machines_for_plan(plan)
    coverage_summary, unassigned_slots = build_template_coverage_summary(
        list(plan.entries),
        machines,
        plan.start_date,
        plan.days,
        plan.rhythm,
        respect_active_weekdays=is_known_shift_model_value(plan.rhythm),
    )
    replace_plan_coverage_slots(plan, unassigned_slots)
    conflict_payload = conflicts_for_plan(plan)
    summary = conflict_summary(conflict_payload["conflicts"])
    plan.coverage_percent = (
        round(
            (coverage_summary["assigned_slots"] / coverage_summary["required_slots"]) * 100,
            2,
        )
        if coverage_summary["required_slots"]
        else 0
    )
    plan.conflict_count = summary["total"]
    plan.critical_conflict_count = summary["critical"]
    update_employee_rotation_state([entry.employee])
    record_event(
        "shiftplan.entry_moved",
        "workforce",
        entity_type="shift_plan_entry",
        entity_id=entry.id,
        user=user,
        department=department_for_plan(plan),
        machine_id=entry.machine_id,
        source="shiftplans",
        metadata={
            "plan_id": plan.id,
            "target_entry_id": getattr(target_entry, "id", None),
            "conflict_count": plan.conflict_count,
        },
    )
    db.session.commit()
    payload = plan.to_dict(employee_access_level(user))
    payload["conflicts"] = conflict_payload
    payload["warnings"] = conflict_payload["conflicts"]
    payload["coverage_summary"] = coverage_summary
    payload["unassigned_slots"] = [slot.to_dict() for slot in plan.coverage_slots]
    return success_response(payload, message="Eintrag verschoben")


def move_target_entry(data, entry):
    """Return an optional target entry used only to derive a move destination."""
    target_entry_id = data.get("target_entry_id")
    if not target_entry_id:
        return None
    target_entry = db.session.get(ShiftPlanEntry, int(target_entry_id))
    if not target_entry:
        raise ValueError("Ziel-Eintrag nicht gefunden")
    if target_entry.plan_id != entry.plan_id:
        raise ValueError("Eintraege gehoeren zu verschiedenen Plaenen")
    if target_entry.id == entry.id:
        raise ValueError("Quelle und Ziel sind identisch")
    return target_entry


def move_target_slot(data, entry, target_entry, parse_date_func):
    """Return target date, shift, and machine id for a move request."""
    if target_entry:
        return target_entry.work_date, target_entry.shift, target_entry.machine_id
    try:
        target_date = parse_date_func(data.get("target_date"))
    except ValueError as exc:
        raise ValueError(str(exc)) from exc
    target_shift = str(data.get("target_shift") or "").strip()
    if not target_shift:
        raise ValueError("target_shift erforderlich")
    raw_machine_id = data.get("target_machine_id", entry.machine_id)
    target_machine_id = int(raw_machine_id) if raw_machine_id not in (None, "") else None
    return target_date, target_shift, target_machine_id


def target_slot_capacity_error(plan, entry, target_date, target_shift, target_machine):
    """Return an error message when the destination machine slot is full."""
    if not target_machine:
        return None
    current_count = ShiftPlanEntry.query.filter(
        ShiftPlanEntry.plan_id == plan.id,
        ShiftPlanEntry.machine_id == target_machine.id,
        ShiftPlanEntry.work_date == target_date,
        ShiftPlanEntry.shift == target_shift,
        ShiftPlanEntry.id != entry.id,
    ).count()
    if current_count >= int(target_machine.required_employees):
        return "Zielslot ist bereits voll besetzt."
    return None


def manual_move_rule_error(entry, plan, target_date, target_shift, target_machine):
    """Return the first hard-rule error for a manual move."""
    duplicate = ShiftPlanEntry.query.filter(
        ShiftPlanEntry.plan_id == plan.id,
        ShiftPlanEntry.employee_id == entry.employee_id,
        ShiftPlanEntry.work_date == target_date,
        ShiftPlanEntry.id != entry.id,
    ).first()
    if duplicate:
        return "Mitarbeiter hat bereits einen Eintrag an diesem Tag."

    template = resolve_shift_template("three_shift")
    start_time, end_time = template.shift_times.get(target_shift, ("", ""))
    candidate = {
        "employee_id": entry.employee_id,
        "machine_id": target_machine.id if target_machine else None,
        "work_date": target_date,
        "shift": target_shift,
        "start_time": start_time,
        "end_time": end_time,
    }
    existing_entries = [
        plan_entry for plan_entry in plan.entries if plan_entry.id != entry.id
    ]
    qualification_map = qualification_map_for(
        [entry.employee],
        [target_machine] if target_machine else [],
    )
    violations = validate_candidate_assignment(
        candidate,
        existing_entries,
        approved_vacation_days(entry.employee_id, target_date),
        qualification_map,
        template,
        enforce_active_weekdays=is_known_shift_model_value(plan.rhythm),
    )
    if violations:
        return violations[0].message
    return None


def approved_vacation_days(employee_id, work_date):
    """Return approved vacation days for one employee and one date."""
    vacation = VacationRequest.query.filter(
        VacationRequest.employee_id == employee_id,
        VacationRequest.status == "approved",
        VacationRequest.start_date <= work_date,
        VacationRequest.end_date >= work_date,
    ).first()
    return {(employee_id, work_date)} if vacation else set()


@shiftplans_bp.delete("/entries/<int:entry_id>")
@dashboard_permission_required("shiftplans", "write")
def delete_entry(entry_id):
    """Delete a single shift plan entry (admin only) and log the action."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren koennen Eintraege loeschen", 403)
    entry = db.get_or_404(ShiftPlanEntry, entry_id)
    db.session.add(
        ShiftPlanChangeLog(
            entry_id=entry.id,
            plan_id=entry.plan_id,
            user_id=current_user().id,
            action="delete",
            old_value=f"{entry.shift} {entry.work_date.isoformat()}",
        )
    )
    plan = db.session.get(ShiftPlan, entry.plan_id)
    notify_shiftplan_change(plan, current_user(), "delete", entry=entry)
    plan.change_count = (plan.change_count or 0) + 1
    record_event(
        "shiftplan.entry_deleted",
        "workforce",
        entity_type="shift_plan_entry",
        entity_id=entry.id,
        user=current_user(),
        department=department_for_plan(plan),
        machine_id=entry.machine_id,
        source="shiftplans",
        metadata={
            "plan_id": plan.id,
            "shift": entry.shift,
            "work_date": entry.work_date.isoformat(),
        },
    )
    db.session.delete(entry)
    db.session.flush()
    refresh_plan_operations_metrics(plan)
    refresh_plan_coverage_slots(plan)
    update_employee_rotation_state([entry.employee])
    db.session.commit()
    return "", 204


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@shiftplans_bp.get("/<int:plan_id>/changelog")
@roles_required(Role.MASTER_ADMIN)
def plan_changelog(plan_id):
    """Return the full change history for a shift plan (admin only)."""
    db.get_or_404(ShiftPlan, plan_id)
    logs = (
        ShiftPlanChangeLog.query.filter_by(plan_id=plan_id)
        .order_by(ShiftPlanChangeLog.changed_at.desc())
        .all()
    )
    return success_response([log.to_dict() for log in logs], message="Changelog geladen")
