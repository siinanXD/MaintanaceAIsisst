from datetime import datetime, timedelta, timezone

from flask import Blueprint, request

from app.extensions import db
from app.models import Employee, Role, VacationRequest
from app.responses import error_response, success_response
from app.security import current_user, dashboard_permission_required


vacations_bp = Blueprint("vacations", __name__)


def count_workdays(start, end):
    """Count Mon–Fri workdays between start and end (inclusive)."""
    count = 0
    d = start
    while d <= end:
        if d.weekday() < 5:
            count += 1
        d += timedelta(days=1)
    return count


def vacation_balance(employee_id, year):
    emp = db.session.get(Employee, employee_id)
    if not emp:
        return None
    used = db.session.query(db.func.sum(VacationRequest.days_used)).filter(
        VacationRequest.employee_id == employee_id,
        VacationRequest.status == "approved",
        db.extract("year", VacationRequest.start_date) == year,
    ).scalar() or 0
    total = emp.vacation_days_per_year
    return {"total": total, "used": int(used), "remaining": total - int(used)}


@vacations_bp.get("")
@dashboard_permission_required("employees", "view")
def list_vacations():
    """List vacation requests. Admins see all; others see their own employee's requests."""
    user = current_user()
    query = VacationRequest.query.order_by(VacationRequest.start_date.desc())
    if user.role != Role.MASTER_ADMIN:
        if not user.employee_id:
            return success_response([])
        query = query.filter(VacationRequest.employee_id == user.employee_id)
    return success_response([v.to_dict() for v in query.all()])


@vacations_bp.post("")
@dashboard_permission_required("employees", "view")
def create_vacation():
    """Submit a vacation request."""
    from app.shiftplans.services import parse_date
    data = request.get_json(silent=True) or {}
    user = current_user()

    try:
        employee_id = int(data.get("employee_id") or 0)
        start_date  = parse_date(data.get("start_date"))
        end_date    = parse_date(data.get("end_date"))
    except (TypeError, ValueError) as exc:
        return error_response(str(exc), 400)

    if not employee_id:
        return error_response("employee_id erforderlich", 400)
    if end_date < start_date:
        return error_response("Enddatum muss nach Startdatum liegen", 400)

    # Non-admins can only request for their own employee
    if user.role != Role.MASTER_ADMIN and user.employee_id != employee_id:
        return error_response("Fehlende Berechtigung", 403)

    emp = db.session.get(Employee, employee_id)
    if not emp:
        return error_response("Mitarbeiter nicht gefunden", 404)

    days = count_workdays(start_date, end_date)
    if days == 0:
        return error_response("Kein Werktag im gewählten Zeitraum", 400)

    vr = VacationRequest(
        employee_id  = employee_id,
        start_date   = start_date,
        end_date     = end_date,
        days_used    = days,
        status       = "pending",
        requested_by = user.id,
        notes        = str(data.get("notes") or "")[:500],
    )
    db.session.add(vr)
    db.session.commit()
    return success_response(vr.to_dict(), status_code=201, message="Urlaubsantrag gestellt")


@vacations_bp.delete("/<int:request_id>")
@dashboard_permission_required("employees", "view")
def delete_vacation(request_id):
    """Withdraw a pending vacation request."""
    vr   = VacationRequest.query.get_or_404(request_id)
    user = current_user()
    if vr.status != "pending":
        return error_response("Nur ausstehende Anträge können zurückgezogen werden", 409)
    if user.role != Role.MASTER_ADMIN and user.employee_id != vr.employee_id:
        return error_response("Fehlende Berechtigung", 403)
    db.session.delete(vr)
    db.session.commit()
    return "", 204


@vacations_bp.post("/<int:request_id>/approve")
@dashboard_permission_required("employees", "write")
def approve_vacation(request_id):
    """Approve a vacation request (MASTER_ADMIN only)."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren können Urlaubsanträge genehmigen", 403)
    vr = VacationRequest.query.get_or_404(request_id)
    if vr.status != "pending":
        return error_response("Antrag ist nicht mehr ausstehend", 409)
    vr.status      = "approved"
    vr.approved_by = current_user().id
    vr.decided_at  = datetime.now(timezone.utc)
    db.session.commit()
    return success_response(vr.to_dict(), message="Urlaubsantrag genehmigt")


@vacations_bp.post("/<int:request_id>/reject")
@dashboard_permission_required("employees", "write")
def reject_vacation(request_id):
    """Reject a vacation request (MASTER_ADMIN only)."""
    if current_user().role != Role.MASTER_ADMIN:
        return error_response("Nur Administratoren können Urlaubsanträge ablehnen", 403)
    vr = VacationRequest.query.get_or_404(request_id)
    if vr.status != "pending":
        return error_response("Antrag ist nicht mehr ausstehend", 409)
    vr.status      = "rejected"
    vr.approved_by = current_user().id
    vr.decided_at  = datetime.now(timezone.utc)
    db.session.commit()
    return success_response(vr.to_dict(), message="Urlaubsantrag abgelehnt")


@vacations_bp.get("/summary")
@dashboard_permission_required("employees", "view")
def vacation_summary():
    """Return vacation balance for all employees for a given year."""
    try:
        year = int(request.args.get("year") or datetime.now(timezone.utc).year)
    except (TypeError, ValueError):
        return error_response("year muss eine Zahl sein", 400)
    employees = Employee.query.order_by(Employee.name.asc()).all()
    result = []
    for emp in employees:
        bal = vacation_balance(emp.id, year)
        result.append({
            "employee_id": emp.id,
            "name": emp.name,
            "department": emp.department,
            **bal,
        })
    return success_response(result)
