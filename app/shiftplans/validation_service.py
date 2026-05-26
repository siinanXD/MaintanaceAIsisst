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


def validate_arbzg(entries):
    """Check Arbeitszeitgesetz (ArbZG) rules on a list of entry dicts.

    Returns a list of warning dicts for soft violations.
    Raises ValueError only for hard violations that make the plan invalid.

    Hard errors (plan rejected):
    - One shift per day per employee
    - Max 10 h per shift (§3 Satz 2 — absolute limit)
    - Min 11 h rest between consecutive shifts (§5)

    Soft warnings (plan allowed, admin sees hint):
    - >48 h/week (§3 — average over reference period, not a per-week hard cap)
    - >6 consecutive working days (§9 — depends on employer agreement)
    """
    work_shifts = {"Frueh", "Spaet", "Nacht"}
    warnings = []

    # Collect work entries per employee
    by_employee = {}
    seen_day = set()
    for entry in entries:
        shift = str(entry.get("shift") or "")
        if shift not in work_shifts:
            continue
        emp_id = int(entry["employee_id"])
        work_date = entry["work_date"]
        if isinstance(work_date, str):
            work_date = date.fromisoformat(work_date)

        # HARD: One shift per day per employee
        key = (emp_id, work_date)
        if key in seen_day:
            raise ValueError(
                f"Mitarbeiter {emp_id} hat am {work_date.isoformat()} "
                "mehr als eine Schicht geplant (ArbZG §3)."
            )
        seen_day.add(key)
        by_employee.setdefault(emp_id, []).append(
            {
                "work_date": work_date,
                "start_time": entry["start_time"],
                "end_time": entry["end_time"],
            }
        )

    for emp_id, emp_entries in by_employee.items():
        emp_entries_sorted = sorted(emp_entries, key=lambda e: e["work_date"])

        prev_end_dt = None
        prev_date = None
        consecutive = 0
        weekly_hours = {}

        for e in emp_entries_sorted:
            work_date = e["work_date"]
            start_dt, end_dt = shift_datetimes(work_date, e["start_time"], e["end_time"])
            duration = (end_dt - start_dt).total_seconds() / 3600

            # HARD: Max 10 h per shift (ArbZG §3 Satz 2)
            if duration > 10:
                raise ValueError(
                    f"Mitarbeiter {emp_id}: Schicht am {work_date.isoformat()} "
                    f"dauert {duration:.1f}h — max. 10 Stunden erlaubt (ArbZG §3)."
                )

            # HARD: 11 h rest between shifts (ArbZG §5)
            if prev_end_dt is not None:
                rest_hours = (start_dt - prev_end_dt).total_seconds() / 3600
                if rest_hours < 11:
                    raise ValueError(
                        f"Mitarbeiter {emp_id}: Nur {rest_hours:.1f}h Ruhezeit zwischen "
                        f"{prev_end_dt.date().isoformat()} und {work_date.isoformat()} "
                        "— min. 11 Stunden erforderlich (ArbZG §5)."
                    )

            # SOFT: 48 h/week (ArbZG §3 — Durchschnittswert, kein wöchentliches Maximum)
            week_key = work_date.isocalendar()[:2]
            weekly_hours[week_key] = weekly_hours.get(week_key, 0) + duration
            if weekly_hours[week_key] > 48:
                warnings.append(
                    {
                        "type": "arbzg_weekly_hours",
                        "severity": "warning",
                        "message": (
                            f"Mitarbeiter {emp_id}: {weekly_hours[week_key]:.0f}h in KW "
                            f"{week_key[1]} — Richtwert 48h/Woche ueberschritten (ArbZG §3)."
                        ),
                    }
                )

            # SOFT: 6 consecutive working days (ArbZG §9 — Ausnahmen per Tarifvertrag moeglich)
            if prev_date is not None and (work_date - prev_date).days == 1:
                consecutive += 1
            else:
                consecutive = 1
            if consecutive > 6:
                warnings.append(
                    {
                        "type": "arbzg_consecutive_days",
                        "severity": "warning",
                        "message": (
                            f"Mitarbeiter {emp_id}: {consecutive} aufeinanderfolgende "
                            f"Arbeitstage bis {work_date.isoformat()} (Empfehlung: max. 6)."
                        ),
                    }
                )

            prev_end_dt = end_dt
            prev_date = work_date

    return warnings


def validate_entries(entries, employees, machines, start_date, days):
    """Validate generated entries before they are persisted."""
    employee_ids = {employee.id for employee in employees}
    machine_ids = {machine.id for machine in machines}
    validated = []

    for entry in entries:
        try:
            employee_id = int(entry["employee_id"])
            machine_id = int(entry["machine_id"]) if entry.get("machine_id") else None
            work_date = parse_date(entry["work_date"])
            shift = str(entry.get("shift") or "").strip()[:80]
            start_time = str(entry["start_time"])[:5]
            end_time = str(entry["end_time"])[:5]
        except (KeyError, TypeError, ValueError):
            continue

        if employee_id not in employee_ids:
            continue
        if machine_id and machine_id not in machine_ids:
            continue
        if work_date < start_date or work_date >= start_date + timedelta(days=days):
            continue
        if normalize_shift_name(shift) == "Urlaub":
            validated.append(
                {
                    "employee_id": employee_id,
                    "machine_id": None,
                    "work_date": work_date,
                    "shift": "Urlaub",
                    "start_time": "",
                    "end_time": "",
                    "notes": str(entry.get("notes") or "Urlaub")[:500],
                }
            )
            continue
        if hours_between(start_time, end_time) > 8:
            continue

        validated.append(
            {
                "employee_id": employee_id,
                "machine_id": machine_id,
                "work_date": work_date,
                "shift": normalize_shift_name(shift) or "Schicht",
                "start_time": start_time,
                "end_time": end_time,
                "notes": str(entry.get("notes") or "")[:500],
            }
        )

    return validated


def analyze_shift_plan(entries, employees, machines):
    """Return conflicts and coverage information for generated shift entries."""
    coverage_summary = empty_coverage_summary()
    conflicts = detect_shift_plan_conflicts(
        entries,
        employees,
        machines,
        coverage_summary=coverage_summary,
    )
    return conflicts[:50], coverage_summary


def detect_shift_plan_conflicts(
    entries,
    employees,
    machines,
    coverage_summary=None,
    include_coverage=True,
):
    """Return structured conflicts for shift plan entries."""
    normalized_entries = normalize_conflict_entries(entries)
    employee_by_id = {employee.id: employee for employee in employees}
    machine_by_id = {machine.id: machine for machine in machines}
    conflicts = []
    conflicts.extend(detect_duplicate_assignments(normalized_entries, employee_by_id))
    conflicts.extend(detect_vacation_conflicts(normalized_entries, employee_by_id))
    conflicts.extend(
        detect_missing_machine_qualifications(
            normalized_entries,
            employee_by_id,
            machine_by_id,
        )
    )
    conflicts.extend(detect_rest_time_conflicts(normalized_entries, employee_by_id))
    conflicts.extend(detect_weekly_hours_conflicts(normalized_entries, employee_by_id))
    conflicts.extend(detect_consecutive_day_conflicts(normalized_entries, employee_by_id))
    if include_coverage:
        conflicts.extend(
            update_coverage_summary(
                normalized_entries,
                machines,
                coverage_summary or empty_coverage_summary(),
            )
        )
    return conflicts


def empty_coverage_summary():
    """Return an empty coverage summary payload."""
    return {
        "required_slots": 0,
        "assigned_slots": 0,
        "undercovered": 0,
        "machines": {},
    }


def normalize_conflict_entries(entries):
    """Return dict-based entries for conflict detection."""
    normalized = []
    for entry in entries:
        if isinstance(entry, ShiftPlanEntry):
            normalized.append(
                {
                    "id": entry.id,
                    "employee_id": entry.employee_id,
                    "machine_id": entry.machine_id,
                    "work_date": entry.work_date,
                    "shift": entry.shift,
                    "start_time": entry.start_time,
                    "end_time": entry.end_time,
                    "notes": entry.notes,
                }
            )
            continue
        item = dict(entry)
        if isinstance(item.get("work_date"), str):
            try:
                item["work_date"] = date.fromisoformat(item["work_date"])
            except ValueError:
                pass
        normalized.append(item)
    return normalized


def detect_duplicate_assignments(entries, employee_by_id):
    """Return warnings for employees assigned more than once in a shift window."""
    seen = {}
    warnings = []
    for entry in entries:
        if not entry.get("start_time") or not entry.get("end_time"):
            continue
        key = (
            entry["employee_id"],
            entry["work_date"],
        )
        seen.setdefault(key, []).append(entry)
    for key, key_entries in seen.items():
        if len(key_entries) <= 1:
            continue
        employee = employee_by_id.get(key[0])
        warnings.append(
            {
                "type": "duplicate_assignment",
                "severity": "critical",
                "employee_id": key[0],
                "work_date": key[1].isoformat(),
                "entry_ids": [entry.get("id") for entry in key_entries if entry.get("id")],
                "message": (
                    f"{employee.name if employee else 'Mitarbeiter'} ist am "
                    f"{key[1].isoformat()} mehrfach geplant."
                ),
            }
        )
    return warnings


def detect_vacation_conflicts(entries, employee_by_id):
    """Return conflicts for work entries during approved vacations."""
    employee_ids = {entry.get("employee_id") for entry in entries if entry.get("employee_id")}
    dates = [
        entry.get("work_date") for entry in entries if isinstance(entry.get("work_date"), date)
    ]
    if not employee_ids or not dates:
        return []
    approved_vacations = VacationRequest.query.filter(
        VacationRequest.employee_id.in_(employee_ids),
        VacationRequest.status == "approved",
        VacationRequest.start_date <= max(dates),
        VacationRequest.end_date >= min(dates),
    ).all()
    vacation_days = {}
    for vacation in approved_vacations:
        current = vacation.start_date
        while current <= vacation.end_date:
            vacation_days[(vacation.employee_id, current)] = vacation
            current += timedelta(days=1)

    conflicts = []
    for entry in entries:
        if not is_work_entry(entry):
            continue
        vacation = vacation_days.get((entry.get("employee_id"), entry.get("work_date")))
        if not vacation:
            continue
        employee = employee_by_id.get(entry.get("employee_id"))
        conflicts.append(
            {
                "type": "vacation_conflict",
                "severity": "critical",
                "employee_id": entry.get("employee_id"),
                "entry_id": entry.get("id"),
                "vacation_request_id": vacation.id,
                "work_date": entry["work_date"].isoformat(),
                "message": (
                    f"{employee.name if employee else 'Mitarbeiter'} ist am "
                    f"{entry['work_date'].isoformat()} trotz genehmigtem Urlaub geplant."
                ),
            }
        )
    return conflicts


def detect_rest_time_conflicts(entries, employee_by_id):
    """Return warnings for entries with less than 11 hours rest time."""
    warnings = []
    by_employee = {}
    for entry in entries:
        if not is_work_entry(entry):
            continue
        by_employee.setdefault(entry["employee_id"], []).append(entry)
    for employee_id, employee_entries in by_employee.items():
        sorted_entries = sorted(
            employee_entries,
            key=lambda item: shift_datetimes(
                item["work_date"],
                item["start_time"],
                item["end_time"],
            )[0],
        )
        previous_end = None
        for entry in sorted_entries:
            start_dt, end_dt = shift_datetimes(
                entry["work_date"],
                entry["start_time"],
                entry["end_time"],
            )
            if previous_end:
                rest_hours = (start_dt - previous_end).total_seconds() / 3600
                if rest_hours < 11:
                    employee = employee_by_id.get(employee_id)
                    warnings.append(
                        {
                            "type": "rest_time",
                            "severity": "critical",
                            "employee_id": employee_id,
                            "entry_id": entry.get("id"),
                            "work_date": entry["work_date"].isoformat(),
                            "message": (
                                f"{employee.name if employee else 'Mitarbeiter'} "
                                f"hat nur {round(rest_hours, 1)}h Ruhezeit."
                            ),
                        }
                    )
            previous_end = end_dt
    return warnings


def detect_missing_machine_qualifications(entries, employee_by_id, machine_by_id):
    """Return conflicts when structured machine qualification is missing."""
    conflicts = []
    employee_ids = {entry.get("employee_id") for entry in entries if entry.get("employee_id")}
    machine_ids = {entry.get("machine_id") for entry in entries if entry.get("machine_id")}
    qualifications = EmployeeMachineQualification.query.filter(
        EmployeeMachineQualification.employee_id.in_(employee_ids or {0}),
        EmployeeMachineQualification.machine_id.in_(machine_ids or {0}),
    ).all()
    qualification_map = {
        (qualification.employee_id, qualification.machine_id): qualification
        for qualification in qualifications
    }
    if not qualifications and entries_use_legacy_qualification_mode(entries):
        return []
    for entry in entries:
        machine_id = entry.get("machine_id")
        if not machine_id or not is_work_entry(entry):
            continue
        employee = employee_by_id.get(entry["employee_id"])
        machine = machine_by_id.get(machine_id)
        if not employee or not machine:
            continue
        qualification = qualification_map.get((employee.id, machine_id))
        if qualification and qualification.is_valid_for(entry["work_date"]):
            continue
        conflicts.append(
            {
                "type": "missing_qualification",
                "severity": "critical",
                "employee_id": employee.id,
                "machine_id": machine_id,
                "entry_id": entry.get("id"),
                "work_date": entry["work_date"].isoformat(),
                "message": (
                    f"{employee.name} hat keine gueltige Maschinenfreigabe " f"fuer {machine.name}."
                ),
            }
        )
    return conflicts[:50]


def entries_use_legacy_qualification_mode(entries):
    """Return whether generated entries intentionally used legacy qualification data."""
    work_entries = [entry for entry in entries if is_work_entry(entry)]
    if not work_entries:
        return False
    return all("Legacy-" in str(entry.get("notes") or "") for entry in work_entries)


def detect_weekly_hours_conflicts(entries, employee_by_id):
    """Return conflicts for weekly working hours above 48 hours."""
    weekly_hours = {}
    for entry in entries:
        if not is_work_entry(entry):
            continue
        week_key = (entry["employee_id"], entry["work_date"].isocalendar()[:2])
        weekly_hours[week_key] = weekly_hours.get(week_key, 0) + hours_between(
            entry["start_time"],
            entry["end_time"],
        )
    conflicts = []
    for (employee_id, week_key), hours in weekly_hours.items():
        if hours <= 48:
            continue
        employee = employee_by_id.get(employee_id)
        conflicts.append(
            {
                "type": "weekly_hours",
                "severity": "warning",
                "employee_id": employee_id,
                "calendar_week": week_key[1],
                "hours": round(hours, 2),
                "message": (
                    f"{employee.name if employee else 'Mitarbeiter'} ist in KW "
                    f"{week_key[1]} mit {hours:.1f}h geplant."
                ),
            }
        )
    return conflicts


def detect_consecutive_day_conflicts(entries, employee_by_id):
    """Return conflicts for more than six consecutive working days."""
    by_employee = {}
    for entry in entries:
        if is_work_entry(entry):
            by_employee.setdefault(entry["employee_id"], set()).add(entry["work_date"])
    conflicts = []
    for employee_id, work_dates in by_employee.items():
        consecutive = 0
        previous_date = None
        for work_date in sorted(work_dates):
            if previous_date and (work_date - previous_date).days == 1:
                consecutive += 1
            else:
                consecutive = 1
            if consecutive > 6:
                employee = employee_by_id.get(employee_id)
                conflicts.append(
                    {
                        "type": "consecutive_days",
                        "severity": "warning",
                        "employee_id": employee_id,
                        "work_date": work_date.isoformat(),
                        "days": consecutive,
                        "message": (
                            f"{employee.name if employee else 'Mitarbeiter'} ist "
                            f"{consecutive} Tage in Folge geplant."
                        ),
                    }
                )
            previous_date = work_date
    return conflicts


def detect_vacation_assignment_warnings(entries, vacation_entries, employee_by_id):
    """Return warnings when a vacation day still contains working entries."""
    vacation_days = {(entry["employee_id"], entry["work_date"]) for entry in vacation_entries}
    warnings = []
    for entry in entries:
        if normalize_shift_name(entry.get("shift")) == "Urlaub":
            continue
        key = (entry["employee_id"], entry["work_date"])
        if key not in vacation_days:
            continue
        employee = employee_by_id.get(entry["employee_id"])
        warnings.append(
            {
                "type": "vacation_conflict",
                "severity": "critical",
                "message": (
                    f"{employee.name if employee else 'Mitarbeiter'} ist am "
                    f"{entry['work_date'].isoformat()} trotz Urlaub geplant."
                ),
            }
        )
    return warnings


def update_coverage_summary(entries, machines, coverage_summary):
    """Update coverage summary and return undercoverage warnings."""
    warnings = []
    assigned = {}
    work_dates = sorted(
        {entry["work_date"] for entry in entries if isinstance(entry.get("work_date"), date)}
    )
    work_shifts = sorted(
        {entry["shift"] for entry in entries if is_work_entry(entry)} or {"Frueh", "Spaet"}
    )
    for entry in entries:
        if not entry.get("machine_id") or not is_work_entry(entry):
            continue
        key = (entry["machine_id"], entry["work_date"], entry["shift"])
        assigned[key] = assigned.get(key, 0) + 1

    for machine in machines:
        machine_required = 0
        machine_assigned = 0
        for work_date in work_dates:
            for shift in work_shifts:
                key = (machine.id, work_date, shift)
                count = assigned.get(key, 0)
                machine_required += machine.required_employees
                machine_assigned += count
                if count < machine.required_employees:
                    coverage_summary["undercovered"] += 1
                    warnings.append(
                        {
                            "type": "coverage",
                            "severity": "critical",
                            "machine_id": machine.id,
                            "work_date": key[1].isoformat(),
                            "shift": key[2],
                            "required": machine.required_employees,
                            "assigned": count,
                            "message": (
                                f"{machine.name} ist am {key[1].isoformat()} "
                                f"in {key[2]} unterbesetzt."
                            ),
                        }
                    )
        coverage_summary["machines"][machine.name] = {
            "required_slots": machine_required,
            "assigned_slots": machine_assigned,
        }
        coverage_summary["required_slots"] += machine_required
        coverage_summary["assigned_slots"] += machine_assigned
    return warnings


def build_template_coverage_summary(
    entries,
    machines,
    start_date,
    days,
    shift_model_value,
    respect_active_weekdays=True,
):
    """Return coverage summary and undercoverage slots for a template plan."""
    template = resolve_shift_template(shift_model_value)
    normalized_entries = normalize_conflict_entries(entries)
    assigned = {}
    for entry in normalized_entries:
        if not entry.get("machine_id") or not is_work_entry(entry):
            continue
        key = (entry["machine_id"], entry["work_date"], entry["shift"])
        assigned[key] = assigned.get(key, 0) + 1

    coverage_summary = empty_coverage_summary()
    unassigned_slots = []
    for machine in machines:
        machine_required = 0
        machine_assigned = 0
        for day_offset in range(days):
            work_date = start_date + timedelta(days=day_offset)
            if respect_active_weekdays and not template.is_active_on(work_date):
                continue
            for shift_window in template.shifts:
                key = (machine.id, work_date, shift_window.key)
                required = int(machine.required_employees)
                count = assigned.get(key, 0)
                missing = max(0, required - count)
                machine_required += required
                machine_assigned += count
                if missing:
                    coverage_summary["undercovered"] += 1
                    unassigned_slots.append(
                        undercoverage_slot_payload(
                            machine,
                            work_date,
                            shift_window.key,
                            required,
                            count,
                            missing,
                        )
                    )
        coverage_summary["machines"][machine.name] = {
            "required_slots": machine_required,
            "assigned_slots": machine_assigned,
        }
        coverage_summary["required_slots"] += machine_required
        coverage_summary["assigned_slots"] += machine_assigned
    return coverage_summary, unassigned_slots


def undercoverage_slot_payload(machine, work_date, shift, required, assigned, missing):
    """Return a visible undercoverage payload for one machine shift."""
    return {
        "work_date": work_date.isoformat(),
        "shift": shift,
        "machine_id": machine.id if machine else None,
        "machine_name": machine.name if machine else None,
        "required": required,
        "assigned": assigned,
        "missing": missing,
        "reason": "Keine regelkonforme Besetzung moeglich",
        "suggestion": (
            "Maschinenqualifikationen pflegen oder zusaetzliche " "Mitarbeitende freigeben"
        ),
    }


def coverage_warnings_from_slots(unassigned_slots):
    """Return critical coverage warnings for visible undercoverage slots."""
    warnings = []
    for slot in unassigned_slots:
        machine_text = f" an {slot['machine_name']}" if slot.get("machine_name") else ""
        warnings.append(
            {
                "type": "coverage",
                "severity": "critical",
                "machine_id": slot.get("machine_id"),
                "machine_name": slot.get("machine_name"),
                "work_date": slot.get("work_date"),
                "shift": slot.get("shift"),
                "required": slot.get("required"),
                "assigned": slot.get("assigned"),
                "missing": slot.get("missing"),
                "message": (
                    f"Keine regelkonforme Besetzung am {slot.get('work_date')} "
                    f"fuer {slot.get('shift')}{machine_text}."
                ),
            }
        )
    return warnings


__all__ = [
    "validate_arbzg",
    "validate_entries",
    "analyze_shift_plan",
    "detect_shift_plan_conflicts",
    "empty_coverage_summary",
    "normalize_conflict_entries",
    "detect_duplicate_assignments",
    "detect_vacation_conflicts",
    "detect_rest_time_conflicts",
    "detect_missing_machine_qualifications",
    "entries_use_legacy_qualification_mode",
    "detect_weekly_hours_conflicts",
    "detect_consecutive_day_conflicts",
    "detect_vacation_assignment_warnings",
    "update_coverage_summary",
    "build_template_coverage_summary",
    "undercoverage_slot_payload",
    "coverage_warnings_from_slots",
]
