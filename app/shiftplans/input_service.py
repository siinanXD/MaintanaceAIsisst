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


def department_employees(department):
    """Return employees assigned to a given department for shift planning."""
    return (
        Employee.query.filter(Employee.department.ilike(f"%{department}%"))
        .order_by(Employee.team.asc(), Employee.name.asc())
        .all()
    )


def selected_machines_for_request(data):
    """Return requested machines or all machines for legacy payloads."""
    all_machines = Machine.query.order_by(Machine.name.asc()).all()
    if "machine_ids" not in data:
        return all_machines, None
    raw_machine_ids = data.get("machine_ids")
    if not isinstance(raw_machine_ids, list) or not raw_machine_ids:
        return None, {"error": "Bitte mindestens eine Maschine auswaehlen."}
    try:
        requested_ids = {int(machine_id) for machine_id in raw_machine_ids}
    except (TypeError, ValueError):
        return None, {"error": "machine_ids muessen gueltige Maschinen-IDs enthalten."}
    machine_by_id = {machine.id: machine for machine in all_machines}
    missing_ids = sorted(requested_ids - set(machine_by_id))
    if missing_ids:
        return None, {
            "error": (
                "Unbekannte Maschine(n): "
                + ", ".join(str(machine_id) for machine_id in missing_ids)
            )
        }
    return [machine_by_id[machine_id] for machine_id in sorted(requested_ids)], None


def production_employees():
    """Backward-compatible wrapper: return production employees."""
    return department_employees("Produktion")


def employee_payload(employees):
    """Build the compact employee payload sent to the planner."""
    return [
        {
            "id": employee.id,
            "name": employee.name,
            "team": employee.team,
            "shift_model": employee.shift_model,
            "current_shift": employee.current_shift,
            "qualifications": employee.qualifications,
            "favorite_machine": employee.favorite_machine,
        }
        for employee in employees
    ]


def local_shift_entries(
    start_date,
    days,
    rhythm,
    employees,
    machines,
    unavailable=None,
    shift_model_value=None,
    preferences="",
):
    """Build a fair deterministic fallback plan without calling OpenAI.

    Uses a minimum-shift-count selection instead of round-robin so that
    no employee accumulates significantly more shifts than others.
    """
    return build_local_shift_entries(
        start_date,
        days,
        shift_model_value or rhythm,
        employees,
        machines,
        unavailable=unavailable,
        respect_active_weekdays=bool(shift_model_value),
        preferences=preferences,
    )


def local_shift_plan(
    start_date,
    days,
    rhythm,
    employees,
    machines,
    unavailable=None,
    shift_model_value=None,
    preferences="",
):
    """Build local entries with warnings and visible undercoverage slots."""
    return build_local_shift_plan(
        start_date,
        days,
        shift_model_value or rhythm,
        employees,
        machines,
        unavailable=unavailable,
        respect_active_weekdays=bool(shift_model_value),
        preferences=preferences,
    )


def _pick_fairest_employee(employees, shift_count, work_date, unavailable, assigned_today):
    """Return the available employee with the fewest shifts assigned so far."""
    blocked = unavailable.get(work_date, set())
    candidates = [
        emp for emp in employees if emp.id not in blocked and emp.id not in assigned_today
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda emp: (shift_count[emp.id], emp.id))


def parse_vacation_entries(data, employees, start_date, days):
    """Parse vacation payloads into shift plan entries and unavailable dates."""
    employee_ids = {employee.id for employee in employees}
    vacation_entries = []
    unavailable = {}
    raw_vacations = data.get("vacations") or []
    if not isinstance(raw_vacations, list):
        raise ValueError("vacations must be a list")

    for raw_vacation in raw_vacations:
        if not isinstance(raw_vacation, dict):
            raise ValueError("vacations entries must be objects")
        try:
            employee_id = int(raw_vacation["employee_id"])
            work_date = parse_date(raw_vacation["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("vacations require employee_id and date") from exc
        if employee_id not in employee_ids:
            raise ValueError("vacations contain an unknown production employee")
        if work_date < start_date or work_date >= start_date + timedelta(days=days):
            raise ValueError("vacation date must be within the shift plan range")
        unavailable.setdefault(work_date, set()).add(employee_id)
        vacation_entries.append(
            {
                "employee_id": employee_id,
                "machine_id": None,
                "work_date": work_date,
                "shift": "Urlaub",
                "start_time": "",
                "end_time": "",
                "notes": str(raw_vacation.get("notes") or "Urlaub")[:500],
            }
        )
    return vacation_entries, unavailable


def remove_unavailable_work_entries(entries, unavailable):
    """Return work entries excluding employees blocked by vacation."""
    filtered_entries = []
    for entry in entries:
        try:
            employee_id = int(entry["employee_id"])
            work_date = parse_date(entry["work_date"])
        except (KeyError, TypeError, ValueError):
            filtered_entries.append(entry)
            continue
        if employee_id in unavailable.get(work_date, set()):
            continue
        filtered_entries.append(entry)
    return filtered_entries


__all__ = [
    "department_employees",
    "selected_machines_for_request",
    "production_employees",
    "employee_payload",
    "local_shift_entries",
    "local_shift_plan",
    "_pick_fairest_employee",
    "parse_vacation_entries",
    "remove_unavailable_work_entries",
]
