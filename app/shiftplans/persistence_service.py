"""Shift planning generation and validation services."""
# ruff: noqa: F401, F821

import json
import logging
from datetime import date, timedelta

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import (
    Employee,
    EmployeeMachineQualification,
    Machine,
    ShiftPlan,
    ShiftPlanCoverageSlot,
    ShiftPlanEntry,
    VacationRequest,
)
from app.shiftplans.generator import build_local_shift_entries, build_local_shift_plan
from app.shiftplans.templates import (
    SHIFT_TEMPLATE_ALIASES,
    SHIFT_TEMPLATES,
    get_shift_model_template,
    normalize_template_value,
    resolve_shift_template,
)
from app.shiftplans.time_service import (
    hours_between,
    parse_date,
    parse_days,
    shift_datetimes,
)

SHIFT_WINDOWS = {
    shift.key: (shift.start_time, shift.end_time)
    for shift in get_shift_model_template("three_shift").shifts
}

SHIFT_LABELS = {
    "frueh": "Frueh",
    "früh": "Frueh",
    "spaet": "Spaet",
    "spät": "Spaet",
    "nacht": "Nacht",
    "frei": "Frei",
    "urlaub": "Urlaub",
}
logger = logging.getLogger(__name__)


def persist_shift_plan_from_draft(data, user=None):
    """Persist a generated shift plan draft and return the saved plan."""
    draft, error, status = build_shift_plan_draft(data)
    if error:
        return None, error, status

    notes = (
        "Regelbasierter Generator genutzt. Ungueltige Zuweisungen werden "
        "vor dem Speichern blockiert."
    )
    plan = ShiftPlan(
        title=draft["title"],
        start_date=draft["start_date"],
        days=draft["days"],
        rhythm=draft["rhythm"],
        preferences=draft["preferences"],
        notes=notes,
        department=draft["department"],
        created_by=user.id if user else None,
    )
    summary = conflict_summary(draft["warnings"])
    plan.coverage_percent = coverage_percent(draft["coverage_summary"])
    plan.conflict_count = summary["total"]
    plan.critical_conflict_count = summary["critical"]
    db.session.add(plan)
    db.session.flush()

    for entry in draft["entries"]:
        db.session.add(ShiftPlanEntry(plan=plan, **entry))
    db.session.flush()
    replace_plan_coverage_slots(plan, draft["unassigned_slots"])
    update_employee_rotation_state(draft["employees"])
    db.session.commit()

    plan.warnings = draft["warnings"]
    plan.coverage_summary = draft["coverage_summary"]
    plan.fairness_summary = draft["fairness_summary"]
    return plan, None, 201


def replace_plan_coverage_slots(plan, unassigned_slots):
    """Replace persisted undercoverage slots for a plan."""
    ShiftPlanCoverageSlot.query.filter_by(plan_id=plan.id).delete()
    for slot in unassigned_slots:
        db.session.add(
            ShiftPlanCoverageSlot(
                plan_id=plan.id,
                machine_id=slot.get("machine_id"),
                work_date=parse_date(slot.get("work_date")),
                shift=str(slot.get("shift") or "")[:80],
                required=int(slot.get("required") or 0),
                assigned=int(slot.get("assigned") or 0),
                missing=int(slot.get("missing") or 0),
                reason=str(slot.get("reason") or "")[:240],
                suggestion=str(slot.get("suggestion") or "")[:240],
            )
        )


def refresh_plan_coverage_slots(plan):
    """Recalculate and persist visible undercoverage slots for a plan."""
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
    return coverage_summary, unassigned_slots


def update_employee_rotation_state(employees):
    """Update last, current, and next planned shift values for employees."""
    today = date.today()
    for employee in employees:
        entries = (
            ShiftPlanEntry.query.filter_by(employee_id=employee.id)
            .filter(ShiftPlanEntry.shift.notin_(("Urlaub", "Frei", "")))
            .order_by(ShiftPlanEntry.work_date.asc(), ShiftPlanEntry.start_time.asc())
            .all()
        )
        past_entries = [entry for entry in entries if entry.work_date < today]
        upcoming_entries = [entry for entry in entries if entry.work_date >= today]
        employee.last_shift = past_entries[-1].shift if past_entries else ""
        employee.current_shift = upcoming_entries[0].shift if upcoming_entries else ""
        employee.next_shift = upcoming_entries[1].shift if len(upcoming_entries) > 1 else ""
        employee.rotation_state_updated_at = utc_now()


def generate_shift_plan(data, user=None):
    """Generate, validate and save a shift plan from request data.

    Args:
        data: Parsed JSON request body.
        user: The User object of the requesting user (for audit trail).

    """
    return persist_shift_plan_from_draft(data, user)


__all__ = [
    "persist_shift_plan_from_draft",
    "replace_plan_coverage_slots",
    "refresh_plan_coverage_slots",
    "update_employee_rotation_state",
    "generate_shift_plan",
]
