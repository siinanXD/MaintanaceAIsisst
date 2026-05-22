"""Validation helpers for manual shift plan entry moves."""

from app.extensions import db
from app.models import ShiftPlanEntry, VacationRequest
from app.shiftplans.generator import qualification_map_for
from app.shiftplans.rules import validate_candidate_assignment
from app.shiftplans.services import is_known_shift_model_value
from app.shiftplans.templates import resolve_shift_template


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
