"""Services for structured employee-machine qualifications."""

from datetime import date

from app.extensions import db
from app.models import Employee, EmployeeMachineQualification, Machine

QUALIFICATION_LEVELS = {"basic", "trained", "expert", "trainer"}


def qualification_matrix():
    """Return employees, machines, and structured machine qualification rows."""
    employees = Employee.query.order_by(Employee.name.asc()).all()
    machines = Machine.query.order_by(Machine.name.asc()).all()
    qualifications = EmployeeMachineQualification.query.order_by(
        EmployeeMachineQualification.employee_id.asc(),
        EmployeeMachineQualification.machine_id.asc(),
    ).all()
    return {
        "employees": [employee.to_dict("basic") for employee in employees],
        "machines": [machine.to_dict() for machine in machines],
        "qualifications": [qualification.to_dict() for qualification in qualifications],
        "levels": sorted(QUALIFICATION_LEVELS),
    }


def update_employee_qualifications(employee, data):
    """Replace all structured machine qualifications for one employee."""
    raw_items = data if isinstance(data, list) else data.get("qualifications", [])
    if not isinstance(raw_items, list):
        return None, {"error": "qualifications must be a list"}, 400

    machine_ids = {machine.id for machine in Machine.query.all()}
    seen_machine_ids = set()
    normalized_items = []
    for raw_item in raw_items:
        item, error = normalize_qualification_item(raw_item, machine_ids)
        if error:
            return None, {"error": error}, 400
        if item["machine_id"] in seen_machine_ids:
            return None, {"error": "machine_id darf pro Mitarbeiter nur einmal vorkommen"}, 400
        seen_machine_ids.add(item["machine_id"])
        normalized_items.append(item)

    EmployeeMachineQualification.query.filter_by(employee_id=employee.id).delete()
    for item in normalized_items:
        db.session.add(
            EmployeeMachineQualification(
                employee_id=employee.id,
                machine_id=item["machine_id"],
                level=item["level"],
                valid_until=item["valid_until"],
                notes=item["notes"],
            )
        )
    db.session.commit()
    return employee_qualification_payload(employee), None, 200


def employee_qualification_payload(employee):
    """Return one employee with structured qualification rows."""
    db.session.refresh(employee)
    return {
        "employee": employee.to_dict("shift"),
        "qualifications": [
            qualification.to_dict() for qualification in employee.machine_qualifications
        ],
    }


def normalize_qualification_item(raw_item, machine_ids):
    """Validate and normalize one qualification input row."""
    if not isinstance(raw_item, dict):
        return None, "qualification entries must be objects"
    try:
        machine_id = int(raw_item.get("machine_id"))
    except (TypeError, ValueError):
        return None, "machine_id must be a valid integer"
    if machine_id not in machine_ids:
        return None, "machine_id does not exist"

    level = str(raw_item.get("level") or "trained").strip().lower()
    if level not in QUALIFICATION_LEVELS:
        return None, "level must be one of: " + ", ".join(sorted(QUALIFICATION_LEVELS))

    valid_until, error = parse_optional_date(raw_item.get("valid_until"))
    if error:
        return None, error

    return (
        {
            "machine_id": machine_id,
            "level": level,
            "valid_until": valid_until,
            "notes": str(raw_item.get("notes") or "")[:500],
        },
        None,
    )


def parse_optional_date(value):
    """Parse an optional ISO date value."""
    if value in (None, ""):
        return None, None
    if isinstance(value, date):
        return value, None
    try:
        return date.fromisoformat(str(value)), None
    except ValueError:
        return None, "valid_until must use YYYY-MM-DD"
