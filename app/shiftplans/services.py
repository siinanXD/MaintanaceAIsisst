import json
from datetime import date, datetime, timedelta

from flask import current_app
from openai import OpenAI, OpenAIError

from app.extensions import db
from app.models import Employee, Machine, ShiftPlan, ShiftPlanEntry


SHIFT_WINDOWS = {
    "Frueh": ("06:00", "14:00"),
    "Spaet": ("14:00", "22:00"),
    "Nacht": ("22:00", "06:00"),
}


def parse_date(value):
    """Parse an ISO date string or default to today."""
    if not value:
        return date.today()
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


def local_shift_entries(start_date, days, rhythm, employees, machines):
    """Build a deterministic fallback plan without calling OpenAI."""
    entries = []
    if not employees:
        return entries

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
                    employee = employees[employee_index % len(employees)]
                    employee_index += 1
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
    return entries


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
        if hours_between(start_time, end_time) > 8:
            continue

        validated.append(
            {
                "employee_id": employee_id,
                "machine_id": machine_id,
                "work_date": work_date,
                "shift": shift or "Schicht",
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
        current_app.logger.exception("OpenAI shift planning failed")
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

    ai_result = openai_shift_entries(
        start_date,
        days,
        rhythm,
        preferences,
        employees,
        machines,
    )
    if ai_result and isinstance(ai_result.get("entries"), list):
        raw_entries = ai_result["entries"]
        notes = ai_result.get("notes", "")
    else:
        raw_entries = local_shift_entries(start_date, days, rhythm, employees, machines)
        notes = (
            "Lokaler Fallback genutzt. Regeln: max. 8h je Schicht, "
            "11h Ruhezeit, Produktionsmitarbeiter und Maschinenbedarf."
        )

    entries = validate_entries(raw_entries, employees, machines, start_date, days)
    if not entries:
        return None, {"error": "Es konnte kein gueltiger Schichtplan erzeugt werden"}, 400
    warnings, coverage_summary = analyze_shift_plan(entries, employees, machines)

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
