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
    return date.fromisoformat(value)


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


def local_shift_entries(start_date, days, rhythm, employees, machines):
    """Build a deterministic fallback plan without calling OpenAI."""
    entries = []
    if not employees:
        return entries

    shift_names = ["Frueh", "Spaet", "Nacht"] if "nacht" in rhythm.lower() or "3" in rhythm else ["Frueh", "Spaet"]
    employee_index = 0
    machines_to_plan = machines or [None]

    for day_offset in range(days):
        work_date = start_date + timedelta(days=day_offset)
        for machine in machines_to_plan:
            required = machine.required_employees if machine else max(1, len(employees) // len(shift_names))
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
                            "notes": "Automatisch geplant: max. 8h Schicht, 11h Ruhezeit als Planungsregel.",
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


def openai_shift_entries(start_date, days, rhythm, preferences, employees, machines):
    """Ask OpenAI for a JSON shift plan when a key is configured."""
    api_key = current_app.config.get("OPENAI_API_KEY")
    if not api_key:
        return None

    prompt = {
        "task": "Erstelle einen deutschen Produktions-Schichtplan als JSON.",
        "rules": [
            "Plane nur Mitarbeitende aus der Produktion.",
            "Beruecksichtige Rhythmus, Praeferenzen, Qualifikationen und Lieblingsmaschine.",
            "Nutze pro Maschine die benoetigte Mitarbeiterzahl.",
            "Arbeitszeitgesetz: maximal 8 Stunden pro Schicht und mindestens 11 Stunden Ruhezeit zwischen Schichten.",
            "Antwortformat: {\"notes\":\"...\", \"entries\":[{\"employee_id\":1,\"machine_id\":1,\"work_date\":\"YYYY-MM-DD\",\"shift\":\"Frueh\",\"start_time\":\"06:00\",\"end_time\":\"14:00\",\"notes\":\"...\"}]}",
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
                {"role": "system", "content": "Du bist ein vorsichtiger Schichtplaner fuer deutsche Produktion."},
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
    start_date = parse_date(data.get("start_date"))
    days = int(data.get("days") or 7)
    days = min(max(days, 1), 31)
    rhythm = data.get("rhythm", "2-Schicht Rhythmus")
    preferences = data.get("preferences", "")
    title = data.get("title") or f"Schichtplan ab {start_date.isoformat()}"

    employees = production_employees()
    machines = Machine.query.order_by(Machine.name.asc()).all()
    if not employees:
        return None, {"error": "Keine Produktionsmitarbeiter gefunden"}, 400

    ai_result = openai_shift_entries(start_date, days, rhythm, preferences, employees, machines)
    if ai_result and isinstance(ai_result.get("entries"), list):
        raw_entries = ai_result["entries"]
        notes = ai_result.get("notes", "")
    else:
        raw_entries = local_shift_entries(start_date, days, rhythm, employees, machines)
        notes = "Lokaler Fallback genutzt. Regeln: max. 8h je Schicht, 11h Ruhezeit, Produktionsmitarbeiter und Maschinenbedarf."

    entries = validate_entries(raw_entries, employees, machines, start_date, days)
    if not entries:
        return None, {"error": "Es konnte kein gueltiger Schichtplan erzeugt werden"}, 400

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
    return plan, None, 201
