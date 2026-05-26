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


def is_work_entry(entry):
    """Return whether an entry represents planned work."""
    shift = normalize_shift_name(entry.get("shift"))
    return bool(
        shift not in {"Urlaub", "Frei", ""} and entry.get("start_time") and entry.get("end_time")
    )


def generated_work_entries(entries):
    """Return persisted entry payloads that represent generated work."""
    return [entry for entry in entries if is_work_entry(entry)]


def normalize_shift_name(value):
    """Return a supported display shift name for common German spellings."""
    normalized = str(value or "").strip().lower()
    return SHIFT_LABELS.get(normalized, str(value or "").strip())


def normalize_preferences(value):
    """Return preferences as bounded text for storage and scoring."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict | list):
        return json.dumps(value, ensure_ascii=True, sort_keys=True)
    return str(value).strip()


def is_known_shift_model_value(value):
    """Return whether a value is a supported model key or explicit alias."""
    raw_value = str(value or "").strip()
    if raw_value in SHIFT_TEMPLATES:
        return True
    normalized = normalize_template_value(value)
    normalized_aliases = {
        normalize_template_value(alias): key for alias, key in SHIFT_TEMPLATE_ALIASES.items()
    }
    return normalized in SHIFT_TEMPLATES or normalized in normalized_aliases


def resolve_explicit_shift_model_key(data):
    """Return the canonical explicit shift model key or a validation error."""
    if "shift_model_key" in data:
        explicit_value = data.get("shift_model_key")
    elif "shift_model" in data:
        explicit_value = data.get("shift_model")
    else:
        return None, None
    if not str(explicit_value or "").strip():
        return None, {
            "error": (
                "shift_model_key darf nicht leer sein. Bitte ein Modell aus "
                "/api/v1/shiftplans/models verwenden."
            )
        }
    if not is_known_shift_model_value(explicit_value):
        return None, {
            "error": (
                "Unbekanntes Schichtmodell. Bitte ein Modell aus "
                "/api/v1/shiftplans/models verwenden."
            )
        }
    raw_value = str(explicit_value or "").strip()
    if raw_value in SHIFT_TEMPLATES:
        return raw_value, None
    normalized = normalize_template_value(explicit_value)
    normalized_aliases = {
        normalize_template_value(alias): key for alias, key in SHIFT_TEMPLATE_ALIASES.items()
    }
    canonical_key = normalized_aliases.get(normalized, normalized)
    return canonical_key, None


def build_shift_plan_draft(data):
    """Build a validated shift plan draft without persisting database rows."""
    department = (data.get("department") or "").strip()
    if not department:
        return None, {"error": "Abteilung ist erforderlich"}, 400

    try:
        start_date = parse_date(data.get("start_date"))
        days = parse_days(data.get("days"))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400
    shift_model_value, shift_model_error = resolve_explicit_shift_model_key(data)
    if shift_model_error:
        return None, shift_model_error, 400
    rhythm = shift_model_value or data.get("rhythm", "2-Schicht Rhythmus")
    preferences = normalize_preferences(data.get("preferences", ""))
    title = data.get("title") or f"Schichtplan {department} ab {start_date.isoformat()}"

    employees = department_employees(department)
    machines, machine_error = selected_machines_for_request(data)
    if machine_error:
        return None, machine_error, 400
    if not employees:
        return None, {"error": f"Keine Mitarbeitenden in Abteilung '{department}' gefunden"}, 400

    try:
        vacation_entries, unavailable = parse_vacation_entries(
            data,
            employees,
            start_date,
            days,
        )
    except ValueError as exc:
        return None, {"error": str(exc)}, 400
    import_approved_vacations(employees, vacation_entries, unavailable, start_date, days)

    raw_entries, planning_warnings, generator_unassigned = local_shift_plan(
        start_date,
        days,
        rhythm,
        employees,
        machines,
        unavailable,
        shift_model_value=shift_model_value,
        preferences=preferences,
    )
    entries = validate_entries(
        raw_entries + vacation_entries,
        employees,
        machines,
        start_date,
        days,
    )
    if not entries and not planning_warnings:
        return None, {"error": "Es konnte kein gueltiger Schichtplan erzeugt werden"}, 400
    if not generated_work_entries(entries):
        return (
            None,
            {
                "error": (
                    "Kein Plan erzeugt. Bitte Maschinenqualifikationen pflegen "
                    "oder Mitarbeiterdaten pruefen."
                ),
                "warnings": planning_warnings,
                "unassigned_slots": generator_unassigned,
            },
            422,
        )

    try:
        arbzg_warnings = validate_arbzg(
            [entry for entry in entries if entry.get("shift") not in ("Urlaub", "Frei", "")]
        )
    except ValueError as exc:
        return None, {"error": str(exc)}, 422

    coverage_summary, unassigned_slots = build_template_coverage_summary(
        entries,
        machines,
        start_date,
        days,
        shift_model_value or rhythm,
        respect_active_weekdays=bool(shift_model_value),
    )
    warnings = detect_shift_plan_conflicts(
        entries,
        employees,
        machines,
        coverage_summary=empty_coverage_summary(),
        include_coverage=False,
    )[:50]
    employee_by_id = {employee.id: employee for employee in employees}
    warnings.extend(coverage_warnings_from_slots(unassigned_slots))
    warnings.extend(arbzg_warnings)
    warnings.extend(detect_vacation_assignment_warnings(entries, vacation_entries, employee_by_id))
    return (
        {
            "title": title,
            "department": department,
            "start_date": start_date,
            "days": days,
            "rhythm": rhythm,
            "shift_model_value": shift_model_value,
            "preferences": preferences,
            "employees": employees,
            "machines": machines,
            "entries": entries,
            "warnings": warnings,
            "coverage_summary": coverage_summary,
            "unassigned_slots": unassigned_slots,
            "fairness_summary": fairness_summary(entries, employees),
        },
        None,
        200,
    )


def import_approved_vacations(employees, vacation_entries, unavailable, start_date, days):
    """Append approved vacation requests to generated planning inputs."""
    try:
        employee_ids = [employee.id for employee in employees]
        period_end = start_date + timedelta(days=days - 1)
        approved_vacations = VacationRequest.query.filter(
            VacationRequest.employee_id.in_(employee_ids),
            VacationRequest.status == "approved",
            VacationRequest.start_date <= period_end,
            VacationRequest.end_date >= start_date,
        ).all()
        for vacation in approved_vacations:
            current_date = max(vacation.start_date, start_date)
            while current_date <= min(vacation.end_date, period_end):
                if current_date.weekday() < 5:
                    key = (vacation.employee_id, current_date)
                    existing_keys = {
                        (entry["employee_id"], entry["work_date"])
                        for entry in vacation_entries
                        if isinstance(entry["work_date"], type(current_date))
                    }
                    if key not in existing_keys:
                        vacation_entries.append(
                            {
                                "employee_id": vacation.employee_id,
                                "machine_id": None,
                                "work_date": current_date,
                                "shift": "Urlaub",
                                "start_time": "",
                                "end_time": "",
                                "notes": f"Genehmigter Urlaub (Antrag #{vacation.id})",
                            }
                        )
                        unavailable.setdefault(current_date, set()).add(vacation.employee_id)
                current_date += timedelta(days=1)
    except Exception:
        logger.exception("Vacation import failed; continuing plan generation")


def preview_shift_plan(data):
    """Return a generated shift plan preview without saving it."""
    draft, error, status = build_shift_plan_draft(data)
    if error:
        return None, error, status
    return preview_payload(draft), None, 200


def preview_payload(draft):
    """Return API payload for a generated shift plan draft."""
    return {
        "id": None,
        "is_preview": True,
        "title": draft["title"],
        "start_date": draft["start_date"].isoformat(),
        "days": draft["days"],
        "rhythm": draft["rhythm"],
        "preferences": draft["preferences"],
        "notes": "Vorschau ohne Speicherung.",
        "department": draft["department"],
        "status": "preview",
        "coverage_percent": coverage_percent(draft["coverage_summary"]),
        "conflict_count": conflict_summary(draft["warnings"])["total"],
        "critical_conflict_count": conflict_summary(draft["warnings"])["critical"],
        "change_count": 0,
        "created_by": None,
        "entries": serialize_entry_payloads(
            draft["entries"],
            draft["employees"],
            draft["machines"],
        ),
        "warnings": draft["warnings"],
        "conflicts": draft["warnings"],
        "coverage_summary": draft["coverage_summary"],
        "unassigned_slots": draft["unassigned_slots"],
        "fairness_summary": draft["fairness_summary"],
        "required_employee_count": draft["coverage_summary"].get("required_slots", 0),
    }


def coverage_percent(coverage_summary):
    """Return a percentage for assigned versus required slots."""
    required_slots = coverage_summary.get("required_slots") or 0
    assigned_slots = coverage_summary.get("assigned_slots") or 0
    return round((assigned_slots / required_slots) * 100, 2) if required_slots else 0


def serialize_entry_payloads(entries, employees, machines):
    """Return plan-like JSON entries for preview payloads."""
    employee_by_id = {employee.id: employee for employee in employees}
    machine_by_id = {machine.id: machine for machine in machines}
    payload = []
    for index, entry in enumerate(entries, start=1):
        employee = employee_by_id.get(entry["employee_id"])
        machine = machine_by_id.get(entry.get("machine_id"))
        payload.append(
            {
                "id": None,
                "preview_id": index,
                "employee": employee.to_dict("confidential") if employee else None,
                "machine": machine.to_dict() if machine else None,
                "work_date": (
                    entry["work_date"].isoformat()
                    if isinstance(entry["work_date"], date)
                    else entry["work_date"]
                ),
                "shift": entry["shift"],
                "start_time": entry["start_time"],
                "end_time": entry["end_time"],
                "notes": entry.get("notes", ""),
                "created_at": None,
            }
        )
    return payload


def fairness_summary(entries, employees):
    """Return compact fairness counters for a generated draft."""
    by_employee = {
        employee.id: {
            "employee_id": employee.id,
            "name": employee.name,
            "shifts": 0,
            "night_shifts": 0,
            "weekend_shifts": 0,
            "hours": 0.0,
        }
        for employee in employees
    }
    for entry in entries:
        if not is_work_entry(entry):
            continue
        employee_id = int(entry["employee_id"])
        item = by_employee.get(employee_id)
        if not item:
            continue
        work_date = entry["work_date"]
        if isinstance(work_date, str):
            work_date = date.fromisoformat(work_date)
        item["shifts"] += 1
        item["hours"] += hours_between(entry["start_time"], entry["end_time"])
        if entry["shift"] == "Nacht":
            item["night_shifts"] += 1
        if work_date.weekday() >= 5:
            item["weekend_shifts"] += 1
    return {"employees": list(by_employee.values())}


__all__ = [
    "is_work_entry",
    "generated_work_entries",
    "normalize_shift_name",
    "normalize_preferences",
    "is_known_shift_model_value",
    "resolve_explicit_shift_model_key",
    "build_shift_plan_draft",
    "import_approved_vacations",
    "preview_shift_plan",
    "preview_payload",
    "coverage_percent",
    "serialize_entry_payloads",
    "fairness_summary",
]
