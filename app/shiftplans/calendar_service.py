"""Calendar payload services for shift planning."""

from datetime import timedelta

from app.extensions import db
from app.models import Employee, ShiftPlanEntry
from app.permissions import has_employee_access
from app.shiftplans.services import normalize_shift_name, parse_date, parse_days


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
            return (
                {
                    "employee": None,
                    "start_date": parsed_start_date.isoformat(),
                    "days": parsed_days,
                    "entries": [],
                    "message": "Kein Mitarbeiter mit diesem Benutzer verknuepft.",
                },
                None,
                200,
            )
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
    payload_entries = [calendar_entry_payload(entry) for entry in entries]
    occupied_dates = {entry.work_date for entry in entries}
    for day_offset in range(parsed_days):
        current_date = parsed_start_date + timedelta(days=day_offset)
        if current_date in occupied_dates:
            continue
        payload_entries.append(free_day_payload(current_date))

    payload_entries.sort(key=lambda item: (item["work_date"], item["start_time"]))
    return (
        {
            "employee": employee.to_dict("basic"),
            "start_date": parsed_start_date.isoformat(),
            "days": parsed_days,
            "entries": payload_entries,
        },
        None,
        200,
    )


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
