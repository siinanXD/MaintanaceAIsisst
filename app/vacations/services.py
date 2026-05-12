"""Vacation workflow service helpers."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import false

from app.extensions import db
from app.models import Employee, Role, VacationRequest
from app.security import has_dashboard_permission
from app.shiftplans.services import parse_date

VALID_VACATION_STATUSES = {"pending", "approved", "rejected"}


def count_workdays(start, end):
    """Count Monday through Friday workdays between start and end, inclusive."""
    count = 0
    day = start
    while day <= end:
        if day.weekday() < 5:
            count += 1
        day += timedelta(days=1)
    return count


def parse_year_arg(value=None):
    """Parse a vacation year query argument or return the current year."""
    raw_year = value or datetime.now(UTC).year
    try:
        year = int(raw_year)
    except (TypeError, ValueError) as exc:
        raise ValueError("year muss eine Zahl sein") from exc
    if year < 1900 or year > 2200:
        raise ValueError("year liegt ausserhalb des erlaubten Bereichs")
    return year


def employee_in_user_department(user, employee):
    """Return whether an employee belongs to the current user's department."""
    if not user or not employee or not user.department:
        return False
    return employee.department == user.department.name


def can_manage_department_vacations(user):
    """Return whether a user can manage vacation requests for their department."""
    return bool(
        user
        and user.role != Role.MASTER_ADMIN
        and user.department
        and has_dashboard_permission(user, "employees", "write")
    )


def can_create_vacation_for_employee(user, employee):
    """Return whether a user can submit a vacation request for an employee."""
    if not user or not employee:
        return False
    if user.role == Role.MASTER_ADMIN:
        return True
    if user.employee_id == employee.id:
        return True
    return can_manage_department_vacations(user) and employee_in_user_department(
        user,
        employee,
    )


def can_decide_vacation(user, vacation_request):
    """Return whether a user can approve or reject a vacation request."""
    if not user or not vacation_request:
        return False
    if user.role == Role.MASTER_ADMIN:
        return True
    return can_manage_department_vacations(user) and employee_in_user_department(
        user,
        vacation_request.employee,
    )


def visible_vacation_query(user):
    """Return the vacation query scoped to the current user's visibility."""
    query = VacationRequest.query
    if not user:
        return query.filter(false())
    if user.role == Role.MASTER_ADMIN:
        return query
    if can_manage_department_vacations(user):
        return query.join(Employee).filter(Employee.department == user.department.name)
    if user.employee_id:
        return query.filter(VacationRequest.employee_id == user.employee_id)
    return query.filter(false())


def visible_employee_query(user):
    """Return employees visible in vacation summaries for the current user."""
    query = Employee.query
    if not user:
        return query.filter(false())
    if user.role == Role.MASTER_ADMIN:
        return query
    if can_manage_department_vacations(user):
        return query.filter(Employee.department == user.department.name)
    if user.employee_id:
        return query.filter(Employee.id == user.employee_id)
    return query.filter(false())


def vacation_days_for_statuses(employee_id, year, statuses, exclude_request_id=None):
    """Return summed vacation days for one employee, year and status set."""
    query = db.session.query(db.func.sum(VacationRequest.days_used)).filter(
        VacationRequest.employee_id == employee_id,
        VacationRequest.status.in_(statuses),
        db.extract("year", VacationRequest.start_date) == year,
    )
    if exclude_request_id is not None:
        query = query.filter(VacationRequest.id != exclude_request_id)
    return int(query.scalar() or 0)


def vacation_balance(employee_id, year):
    """Return vacation entitlement, used days and reserved pending days."""
    employee = db.session.get(Employee, employee_id)
    if not employee:
        return None
    used = vacation_days_for_statuses(employee_id, year, ("approved",))
    pending = vacation_days_for_statuses(employee_id, year, ("pending",))
    total = employee.vacation_days_per_year
    remaining = total - used
    return {
        "total": total,
        "used": used,
        "remaining": remaining,
        "pending": pending,
        "available": remaining - pending,
    }


def has_overlapping_active_request(employee_id, start_date, end_date):
    """Return whether an active vacation request overlaps the given range."""
    return (
        VacationRequest.query.filter(
            VacationRequest.employee_id == employee_id,
            VacationRequest.status.in_(("pending", "approved")),
            VacationRequest.start_date <= end_date,
            VacationRequest.end_date >= start_date,
        ).first()
        is not None
    )


def list_vacation_requests(args, user):
    """Return visible vacation requests filtered by query arguments."""
    query = visible_vacation_query(user)

    status = (args.get("status") or "").strip()
    if status:
        if status not in VALID_VACATION_STATUSES:
            return None, {"error": "status ist ungueltig"}, 400
        query = query.filter(VacationRequest.status == status)

    employee_id = (args.get("employee_id") or "").strip()
    if employee_id:
        try:
            query = query.filter(VacationRequest.employee_id == int(employee_id))
        except (TypeError, ValueError):
            return None, {"error": "employee_id muss eine Zahl sein"}, 400

    year = (args.get("year") or "").strip()
    if year:
        try:
            parsed_year = parse_year_arg(year)
        except ValueError as exc:
            return None, {"error": str(exc)}, 400
        query = query.filter(
            db.extract("year", VacationRequest.start_date) == parsed_year,
        )

    vacations = query.order_by(VacationRequest.start_date.desc()).all()
    return [vacation.to_dict() for vacation in vacations], None, 200


def create_vacation_request(data, user):
    """Create a pending vacation request after validating business rules."""
    try:
        employee_id = int(data.get("employee_id") or 0)
        start_date = parse_date(data.get("start_date"))
        end_date = parse_date(data.get("end_date"))
    except (TypeError, ValueError) as exc:
        return None, {"error": str(exc)}, 400

    if not employee_id:
        return None, {"error": "employee_id erforderlich"}, 400
    if end_date < start_date:
        return None, {"error": "Enddatum muss nach Startdatum liegen"}, 400

    employee = db.session.get(Employee, employee_id)
    if not employee:
        return None, {"error": "Mitarbeiter nicht gefunden"}, 404
    if not can_create_vacation_for_employee(user, employee):
        return None, {"error": "Fehlende Berechtigung"}, 403

    days = count_workdays(start_date, end_date)
    if days == 0:
        return None, {"error": "Kein Werktag im gewaehlten Zeitraum"}, 400
    if has_overlapping_active_request(employee_id, start_date, end_date):
        return (
            None,
            {"error": "Urlaubsantrag ueberschneidet sich mit einem aktiven Antrag"},
            409,
        )

    balance = vacation_balance(employee_id, start_date.year)
    if not balance or days > balance["available"]:
        return None, {"error": "Nicht genug verfuegbarer Resturlaub"}, 409

    vacation = VacationRequest(
        employee_id=employee_id,
        start_date=start_date,
        end_date=end_date,
        days_used=days,
        status="pending",
        requested_by=user.id,
        notes=str(data.get("notes") or "")[:500],
    )
    db.session.add(vacation)
    db.session.commit()
    return vacation.to_dict(), None, 201


def delete_vacation_request(request_id, user):
    """Delete a pending vacation request if the user may withdraw it."""
    vacation = db.session.get(VacationRequest, request_id)
    if not vacation:
        return None, {"error": "Urlaubsantrag nicht gefunden"}, 404
    if vacation.status != "pending":
        return None, {"error": "Nur ausstehende Antraege koennen zurueckgezogen werden"}, 409
    if user.role != Role.MASTER_ADMIN and user.employee_id != vacation.employee_id:
        return None, {"error": "Fehlende Berechtigung"}, 403
    db.session.delete(vacation)
    db.session.commit()
    return None, None, 204


def decide_vacation_request(request_id, user, status):
    """Approve or reject a vacation request."""
    vacation = db.session.get(VacationRequest, request_id)
    if not vacation:
        return None, {"error": "Urlaubsantrag nicht gefunden"}, 404
    if not can_decide_vacation(user, vacation):
        return None, {"error": "Fehlende Berechtigung"}, 403
    if vacation.status != "pending":
        return None, {"error": "Antrag ist nicht mehr ausstehend"}, 409

    if status == "approved":
        total = vacation.employee.vacation_days_per_year
        used_without_request = vacation_days_for_statuses(
            vacation.employee_id,
            vacation.start_date.year,
            ("approved",),
            exclude_request_id=vacation.id,
        )
        if used_without_request + vacation.days_used > total:
            return None, {"error": "Nicht genug verfuegbarer Resturlaub"}, 409

    vacation.status = status
    vacation.approved_by = user.id
    vacation.decided_at = datetime.now(UTC)
    db.session.commit()
    return vacation.to_dict(), None, 200


def vacation_summary_for_user(args, user):
    """Return vacation balances for employees visible to the user."""
    try:
        year = parse_year_arg(args.get("year"))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    employees = visible_employee_query(user).order_by(Employee.name.asc()).all()
    result = []
    for employee in employees:
        balance = vacation_balance(employee.id, year)
        result.append(
            {
                "employee_id": employee.id,
                "name": employee.name,
                "department": employee.department,
                **balance,
            }
        )
    return result, None, 200
