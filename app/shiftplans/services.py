import json
import logging
from datetime import date, datetime, timedelta

from flask import current_app
from openai import OpenAI, OpenAIError

from app.extensions import db
from app.models import Employee, Machine, ShiftPlan, ShiftPlanEntry
from app.permissions import has_employee_access


SHIFT_WINDOWS = {
    "Frueh": ("06:00", "14:00"),
    "Spaet": ("14:00", "22:00"),
    "Nacht": ("22:00", "06:00"),
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


def parse_date(value):
    """Parse an ISO date string or default to today."""
    if not value:
        return date.today()
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("start_date must use YYYY-MM-DD") from exc


def parse_days(value):
    """Parse and clamp the shift plan duration in days."""
    try:
        days = int(value or 7)
    except (TypeError, ValueError) as exc:
        raise ValueError("days must be a number") from exc
    return min(max(days, 1), 31)


def production_employees():
    """Return employees assigned to production for shift planning."""
    return (
        Employee.query.filter(Employee.department.ilike("%produktion%"))
        .order_by(Employee.team.asc(), Employee.name.asc())
        .all()
    )


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


def parse_time(value):
    """Parse a HH:MM time value."""
    return datetime.strptime(value, "%H:%M").time()


def hours_between(start, end):
    """Calculate shift length in hours, supporting overnight shifts."""
    start_time = parse_time(start)
    end_time = parse_time(end)
    start_dt = datetime.combine(date.today(), start_time)
    end_dt = datetime.combine(date.today(), end_time)
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return (end_dt - start_dt).total_seconds() / 3600


def shift_datetimes(work_date, start, end):
    """Return start and end datetimes for one shift entry."""
    start_dt = datetime.combine(work_date, parse_time(start))
    end_dt = datetime.combine(work_date, parse_time(end))
    if end_dt <= start_dt:
        end_dt += timedelta(days=1)
    return start_dt, end_dt


def local_shift_entries(start_date, days, rhythm, employees, machines, unavailable=None):
    """Build a deterministic fallback plan without calling OpenAI."""
    entries = []
    warnings = []
    unavailable = unavailable or {}
    if not employees:
        return entries, warnings

    shift_names = (
        ["Frueh", "Spaet", "Nacht"]
        if "nacht" in rhythm.lower() or "3" in rhythm
        else ["Frueh", "Spaet"]
    )
    employee_index = 0
    machines_to_plan = machines or [None]

    for day_offset in range(days):
        work_date = start_date + timedelta(days=day_offset)
        for machine in machines_to_plan:
            required = (
                machine.required_employees
                if machine
                else max(1, len(employees) // len(shift_names))
            )
            for shift_index, shift in enumerate(shift_names):
                start_time, end_time = SHIFT_WINDOWS[shift]
                for _ in range(required):
                    employee, employee_index = next_available_employee(
                        employees,
                        employee_index,
                        work_date,
                        unavailable,
                    )
                    if not employee:
                        warnings.append(
                            {
                                "type": "coverage",
                                "severity": "critical",
                                "message": (
                                    f"Keine verfuegbaren Mitarbeitenden am "
                                    f"{work_date.isoformat()} fuer {shift}."
                                ),
                            }
                        )
                        continue
                    entries.append(
                        {
                            "employee_id": employee.id,
                            "machine_id": machine.id if machine else None,
                            "work_date": work_date.isoformat(),
                            "shift": shift,
                            "start_time": start_time,
                            "end_time": end_time,
                            "notes": (
                                "Automatisch geplant: max. 8h Schicht, "
                                "11h Ruhezeit als Planungsregel."
                            ),
                        }
                    )
    return entries, warnings


def next_available_employee(employees, start_index, work_date, unavailable):
    """Return the next employee not blocked on the given date."""
    if not employees:
        return None, start_index
    checked = 0
    employee_count = len(employees)
    while checked < employee_count:
        employee = employees[start_index % employee_count]
        start_index += 1
        checked += 1
        if employee.id not in unavailable.get(work_date, set()):
            return employee, start_index
    return None, start_index


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
    """Return warnings and coverage information for generated shift entries."""
    warnings = []
    employee_by_id = {employee.id: employee for employee in employees}
    machine_by_id = {machine.id: machine for machine in machines}
    coverage_summary = {
        "required_slots": 0,
        "assigned_slots": 0,
        "undercovered": 0,
        "machines": {},
    }

    warnings.extend(detect_duplicate_assignments(entries, employee_by_id))
    warnings.extend(detect_rest_time_conflicts(entries, employee_by_id))
    warnings.extend(detect_qualification_warnings(entries, employee_by_id, machine_by_id))
    warnings.extend(update_coverage_summary(entries, machines, coverage_summary))
    return warnings[:50], coverage_summary


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
            entry["start_time"],
            entry["end_time"],
        )
        seen.setdefault(key, 0)
        seen[key] += 1
    for key, count in seen.items():
        if count <= 1:
            continue
        employee = employee_by_id.get(key[0])
        warnings.append(
            {
                "type": "duplicate_assignment",
                "severity": "critical",
                "message": (
                    f"{employee.name if employee else 'Mitarbeiter'} ist am "
                    f"{key[1].isoformat()} {key[2]}-{key[3]} mehrfach geplant."
                ),
            }
        )
    return warnings


def detect_rest_time_conflicts(entries, employee_by_id):
    """Return warnings for entries with less than 11 hours rest time."""
    warnings = []
    by_employee = {}
    for entry in entries:
        if not entry.get("start_time") or not entry.get("end_time"):
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
                            "severity": "warning",
                            "message": (
                                f"{employee.name if employee else 'Mitarbeiter'} "
                                f"hat nur {round(rest_hours, 1)}h Ruhezeit."
                            ),
                        }
                    )
            previous_end = end_dt
    return warnings


def detect_qualification_warnings(entries, employee_by_id, machine_by_id):
    """Return warnings when machine preference or qualification is missing."""
    warnings = []
    for entry in entries:
        machine_id = entry.get("machine_id")
        if not machine_id:
            continue
        employee = employee_by_id.get(entry["employee_id"])
        machine = machine_by_id.get(machine_id)
        if not employee or not machine:
            continue
        skill_text = " ".join(
            [
                employee.qualifications or "",
                employee.favorite_machine or "",
            ]
        ).lower()
        if machine.name.lower() in skill_text:
            continue
        if machine.produced_item and machine.produced_item.lower() in skill_text:
            continue
        warnings.append(
            {
                "type": "qualification",
                "severity": "info",
                "message": (
                    f"{employee.name} hat keine erkennbare Qualifikation "
                    f"oder Favoritenangabe fuer {machine.name}."
                ),
            }
        )
    return warnings[:20]


def detect_vacation_assignment_warnings(entries, vacation_entries, employee_by_id):
    """Return warnings when a vacation day still contains working entries."""
    vacation_days = {
        (entry["employee_id"], entry["work_date"])
        for entry in vacation_entries
    }
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
    for entry in entries:
        if not entry.get("machine_id"):
            continue
        key = (entry["machine_id"], entry["work_date"], entry["shift"])
        assigned[key] = assigned.get(key, 0) + 1

    for machine in machines:
        machine_required = 0
        machine_assigned = 0
        for key, count in assigned.items():
            if key[0] != machine.id:
                continue
            machine_required += machine.required_employees
            machine_assigned += count
            if count < machine.required_employees:
                coverage_summary["undercovered"] += 1
                warnings.append(
                    {
                        "type": "coverage",
                        "severity": "critical",
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


def normalize_shift_name(value):
    """Return a supported display shift name for common German spellings."""
    normalized = str(value or "").strip().lower()
    return SHIFT_LABELS.get(normalized, str(value or "").strip())


def openai_shift_entries(start_date, days, rhythm, preferences, employees, machines):
    """Ask OpenAI for a JSON shift plan when a key is configured."""
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return None

    prompt = {
        "task": "Erstelle einen deutschen Produktions-Schichtplan als JSON.",
        "rules": [
            "Plane nur Mitarbeitende aus der Produktion.",
            (
                "Beruecksichtige Rhythmus, Praeferenzen, "
                "Qualifikationen und Lieblingsmaschine."
            ),
            "Nutze pro Maschine die benoetigte Mitarbeiterzahl.",
            (
                "Arbeitszeitgesetz: maximal 8 Stunden pro Schicht und "
                "mindestens 11 Stunden Ruhezeit zwischen Schichten."
            ),
            (
                "Antwortformat: {\"notes\":\"...\", \"entries\":["
                "{\"employee_id\":1,\"machine_id\":1,"
                "\"work_date\":\"YYYY-MM-DD\",\"shift\":\"Frueh\","
                "\"start_time\":\"06:00\",\"end_time\":\"14:00\","
                "\"notes\":\"...\"}]}"
            ),
        ],
        "start_date": start_date.isoformat(),
        "days": days,
        "rhythm": rhythm,
        "preferences": preferences,
        "employees": employee_payload(employees),
        "machines": [machine.to_dict() for machine in machines],
    }

    try:
        client = OpenAI(api_key=api_key)
        completion = client.chat.completions.create(
            model=current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Du bist ein vorsichtiger Schichtplaner "
                        "fuer deutsche Produktion."
                    ),
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=True)},
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        )
    except OpenAIError:
        logger.exception("ai_call_failed workflow=shift_planning")
        return None

    try:
        return json.loads(completion.choices[0].message.content)
    except (TypeError, json.JSONDecodeError):
        return None


def generate_shift_plan(data):
    """Generate, validate and save a shift plan from request data."""
    try:
        start_date = parse_date(data.get("start_date"))
        days = parse_days(data.get("days"))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400
    rhythm = data.get("rhythm", "2-Schicht Rhythmus")
    preferences = data.get("preferences", "")
    title = data.get("title") or f"Schichtplan ab {start_date.isoformat()}"

    employees = production_employees()
    machines = Machine.query.order_by(Machine.name.asc()).all()
    if not employees:
        return None, {"error": "Keine Produktionsmitarbeiter gefunden"}, 400
    try:
        vacation_entries, unavailable = parse_vacation_entries(
            data,
            employees,
            start_date,
            days,
        )
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    ai_result = openai_shift_entries(
        start_date,
        days,
        rhythm,
        preferences,
        employees,
        machines,
    )
    if ai_result and isinstance(ai_result.get("entries"), list):
        raw_entries = remove_unavailable_work_entries(ai_result["entries"], unavailable)
        notes = ai_result.get("notes", "")
        planning_warnings = []
    else:
        logger.warning("ai_fallback workflow=shift_planning reason=no_valid_ai_result")
        raw_entries, planning_warnings = local_shift_entries(
            start_date,
            days,
            rhythm,
            employees,
            machines,
            unavailable,
        )
        notes = (
            "Lokaler Fallback genutzt. Regeln: max. 8h je Schicht, "
            "11h Ruhezeit, Produktionsmitarbeiter und Maschinenbedarf."
        )

    entries = validate_entries(
        raw_entries + vacation_entries,
        employees,
        machines,
        start_date,
        days,
    )
    if not entries:
        return None, {"error": "Es konnte kein gueltiger Schichtplan erzeugt werden"}, 400
    warnings, coverage_summary = analyze_shift_plan(entries, employees, machines)
    employee_by_id = {employee.id: employee for employee in employees}
    warnings.extend(planning_warnings)
    warnings.extend(
        detect_vacation_assignment_warnings(entries, vacation_entries, employee_by_id)
    )

    plan = ShiftPlan(
        title=title,
        start_date=start_date,
        days=days,
        rhythm=rhythm,
        preferences=preferences,
        notes=notes,
    )
    db.session.add(plan)
    db.session.flush()

    for entry in entries:
        db.session.add(ShiftPlanEntry(plan=plan, **entry))

    db.session.commit()
    plan.warnings = warnings
    plan.coverage_summary = coverage_summary
    return plan, None, 201


def calendar_entries_for_user(user, employee_id=None, start_date=None, days=14, plan_id=None):
    """Return calendar entries for one employee and visible shift plans."""
    try:
        parsed_start_date = parse_date(start_date)
        parsed_days = parse_days(days)
        target_employee_id = int(employee_id) if employee_id not in (None, "") else None
    except (TypeError, ValueError) as exc:
        return None, {"error": str(exc)}, 400

    if not target_employee_id:
        if not user.employee_id:
            return {
                "employee": None,
                "start_date": parsed_start_date.isoformat(),
                "days": parsed_days,
                "entries": [],
                "message": "Kein Mitarbeiter mit diesem Benutzer verknuepft.",
            }, None, 200
        target_employee_id = user.employee_id

    if not can_read_calendar_for_employee(user, target_employee_id):
        return None, {"error": "Forbidden"}, 403

    employee = db.session.get(Employee, target_employee_id)
    if not employee:
        return None, {"error": "Mitarbeiter nicht gefunden"}, 404

    end_date = parsed_start_date + timedelta(days=parsed_days)
    query = ShiftPlanEntry.query.filter(
        ShiftPlanEntry.employee_id == target_employee_id,
        ShiftPlanEntry.work_date >= parsed_start_date,
        ShiftPlanEntry.work_date < end_date,
    )
    if plan_id not in (None, ""):
        try:
            query = query.filter(ShiftPlanEntry.plan_id == int(plan_id))
        except (TypeError, ValueError):
            return None, {"error": "plan_id must be a valid integer"}, 400

    entries = query.order_by(
        ShiftPlanEntry.work_date.asc(),
        ShiftPlanEntry.start_time.asc(),
        ShiftPlanEntry.id.asc(),
    ).all()
    payload_entries = [
        calendar_entry_payload(entry)
        for entry in entries
    ]
    occupied_dates = {entry.work_date for entry in entries}
    for day_offset in range(parsed_days):
        current_date = parsed_start_date + timedelta(days=day_offset)
        if current_date in occupied_dates:
            continue
        payload_entries.append(free_day_payload(current_date))

    payload_entries.sort(key=lambda item: (item["work_date"], item["start_time"]))
    return {
        "employee": employee.to_dict("basic"),
        "start_date": parsed_start_date.isoformat(),
        "days": parsed_days,
        "entries": payload_entries,
    }, None, 200


def can_read_calendar_for_employee(user, employee_id):
    """Return whether a user may read one employee calendar."""
    if user.is_admin:
        return True
    return user.employee_id == employee_id or has_employee_access(user, "shift")


def calendar_entry_payload(entry):
    """Return one serialized calendar entry with frontend color metadata."""
    shift = normalize_shift_name(entry.shift)
    return {
        "id": entry.id,
        "plan_id": entry.plan_id,
        "work_date": entry.work_date.isoformat(),
        "shift": shift,
        "start_time": entry.start_time,
        "end_time": entry.end_time,
        "machine": entry.machine.to_dict() if entry.machine else None,
        "notes": entry.notes,
        "color": shift_color(shift),
    }


def free_day_payload(work_date):
    """Return a derived free-day calendar entry."""
    return {
        "id": None,
        "plan_id": None,
        "work_date": work_date.isoformat(),
        "shift": "Frei",
        "start_time": "",
        "end_time": "",
        "machine": None,
        "notes": "Frei",
        "color": shift_color("Frei"),
    }


def shift_color(shift):
    """Return the configured calendar color key for a shift name."""
    colors = {
        "Frueh": "green",
        "Spaet": "blue",
        "Nacht": "red",
        "Frei": "violet",
        "Urlaub": "amber",
    }
    return colors.get(normalize_shift_name(shift), "slate")
