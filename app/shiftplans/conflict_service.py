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


def conflicts_for_plan(plan):
    """Return structured conflicts and coverage summary for a persisted plan."""
    employees = employees_for_entries(plan.entries)
    machines = machines_for_plan(plan)
    coverage_summary, unassigned_slots = build_template_coverage_summary(
        list(plan.entries),
        machines,
        plan.start_date,
        plan.days,
        plan.rhythm,
        respect_active_weekdays=is_known_shift_model_value(plan.rhythm),
    )
    conflicts = detect_shift_plan_conflicts(
        list(plan.entries),
        employees,
        machines,
        coverage_summary=empty_coverage_summary(),
        include_coverage=False,
    )
    conflicts.extend(coverage_warnings_from_slots(unassigned_slots))
    return {
        "plan_id": plan.id,
        "conflicts": conflicts,
        "summary": conflict_summary(conflicts),
        "coverage_summary": coverage_summary,
        "unassigned_slots": unassigned_slots,
    }


def machines_for_plan(plan):
    """Return machines that belong to a plan's entries or coverage slots."""
    machine_ids = {entry.machine_id for entry in plan.entries if entry.machine_id is not None}
    machine_ids.update(
        slot.machine_id for slot in plan.coverage_slots if slot.machine_id is not None
    )
    if not machine_ids:
        return Machine.query.order_by(Machine.name.asc()).all()
    return Machine.query.filter(Machine.id.in_(machine_ids)).order_by(Machine.name.asc()).all()


def validate_shiftplan_payload(data):
    """Validate an ad-hoc shift plan payload or an existing plan id."""
    if data.get("plan_id"):
        plan = db.session.get(ShiftPlan, int(data["plan_id"]))
        if not plan:
            return None, {"error": "Schichtplan nicht gefunden"}, 404
        return conflicts_for_plan(plan), None, 200

    raw_entries = data.get("entries") or []
    if not isinstance(raw_entries, list):
        return None, {"error": "entries must be a list"}, 400

    entries = []
    for raw_entry in raw_entries:
        entry, error = normalize_validation_entry(raw_entry)
        if error:
            return None, {"error": error}, 400
        entries.append(entry)

    employees = employees_for_entries(entries)
    machines = Machine.query.order_by(Machine.name.asc()).all()
    coverage_summary = {
        "required_slots": 0,
        "assigned_slots": 0,
        "undercovered": 0,
        "machines": {},
    }
    conflicts = detect_shift_plan_conflicts(
        entries,
        employees,
        machines,
        coverage_summary=coverage_summary,
    )
    return (
        {
            "plan_id": None,
            "conflicts": conflicts,
            "summary": conflict_summary(conflicts),
            "coverage_summary": coverage_summary,
        },
        None,
        200,
    )


def normalize_validation_entry(raw_entry):
    """Validate one ad-hoc validation entry."""
    if not isinstance(raw_entry, dict):
        return None, "entries must contain objects"
    try:
        return (
            {
                "id": raw_entry.get("id"),
                "employee_id": int(raw_entry["employee_id"]),
                "machine_id": (
                    int(raw_entry["machine_id"]) if raw_entry.get("machine_id") else None
                ),
                "work_date": parse_date(raw_entry["work_date"]),
                "shift": normalize_shift_name(raw_entry.get("shift") or "Schicht"),
                "start_time": str(raw_entry.get("start_time") or "")[:5],
                "end_time": str(raw_entry.get("end_time") or "")[:5],
                "notes": str(raw_entry.get("notes") or "")[:500],
            },
            None,
        )
    except (KeyError, TypeError, ValueError):
        return None, "entries require employee_id, work_date and valid values"


def employees_for_entries(entries):
    """Return employee records referenced by entries."""
    employee_ids = sorted(
        {entry_employee_id(entry) for entry in entries if entry_employee_id(entry)}
    )
    if not employee_ids:
        return []
    return Employee.query.filter(Employee.id.in_(employee_ids)).all()


def entry_employee_id(entry):
    """Return the employee id from a model or dict entry."""
    return entry.employee_id if isinstance(entry, ShiftPlanEntry) else entry.get("employee_id")


def conflict_summary(conflicts):
    """Return grouped conflict counts."""
    summary = {"total": len(conflicts), "critical": 0, "warning": 0, "by_type": {}}
    for conflict in conflicts:
        severity = conflict.get("severity")
        if severity in summary:
            summary[severity] += 1
        conflict_type = conflict.get("type") or "unknown"
        summary["by_type"][conflict_type] = summary["by_type"].get(conflict_type, 0) + 1
    return summary


__all__ = [
    "conflicts_for_plan",
    "machines_for_plan",
    "validate_shiftplan_payload",
    "normalize_validation_entry",
    "employees_for_entries",
    "entry_employee_id",
    "conflict_summary",
]
