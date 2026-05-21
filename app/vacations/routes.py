"""Vacation workflow API routes."""

from flask import Blueprint, request

from app.responses import service_error_response, success_response
from app.security import current_user, dashboard_permission_required
from app.vacations.services import (
    build_vacation_impact_response,
    cancel_vacation_request,
    create_vacation_request,
    decide_vacation_request,
    delete_vacation_request,
    list_vacation_requests,
    vacation_summary_for_user,
)

vacations_bp = Blueprint("vacations", __name__)


@vacations_bp.get("")
@dashboard_permission_required("employees", "view")
def list_vacations():
    """List vacation requests with optional status, employee and year filters."""
    data, error, status = list_vacation_requests(request.args, current_user())
    if error:
        return service_error_response(error, status)
    return success_response(data)


@vacations_bp.get("/impact")
@dashboard_permission_required("employees", "view")
def vacation_impact():
    """Preview vacation balance, shift and staffing impact for a date range."""
    data, error, status = build_vacation_impact_response(request.args, current_user())
    if error:
        return service_error_response(error, status)
    return success_response(data)


@vacations_bp.post("")
@dashboard_permission_required("employees", "view")
def create_vacation():
    """Submit a vacation request after validating overlap and balance rules."""
    data, error, status = create_vacation_request(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(data, status_code=status, message="Urlaubsantrag gestellt")


@vacations_bp.delete("/<int:request_id>")
@dashboard_permission_required("employees", "view")
def delete_vacation(request_id):
    """Withdraw a pending vacation request."""
    _data, error, status = delete_vacation_request(request_id, current_user())
    if error:
        return service_error_response(error, status)
    return "", status


@vacations_bp.post("/<int:request_id>/cancel")
@dashboard_permission_required("employees", "view")
def cancel_vacation(request_id):
    """Cancel a pending or approved vacation request without deleting history."""
    data, error, status = cancel_vacation_request(request_id, current_user())
    if error:
        return service_error_response(error, status)
    return success_response(data, message="Urlaubsantrag storniert")


@vacations_bp.post("/<int:request_id>/approve")
@dashboard_permission_required("employees", "write")
def approve_vacation(request_id):
    """Approve a vacation request when the user is allowed to decide it."""
    data, error, status = decide_vacation_request(request_id, current_user(), "approved")
    if error:
        return service_error_response(error, status)
    return success_response(data, message="Urlaubsantrag genehmigt")


@vacations_bp.post("/<int:request_id>/reject")
@dashboard_permission_required("employees", "write")
def reject_vacation(request_id):
    """Reject a vacation request when the user is allowed to decide it."""
    data, error, status = decide_vacation_request(request_id, current_user(), "rejected")
    if error:
        return service_error_response(error, status)
    return success_response(data, message="Urlaubsantrag abgelehnt")


@vacations_bp.get("/summary")
@dashboard_permission_required("employees", "view")
def vacation_summary():
    """Return vacation balance for visible employees for a given year."""
    data, error, status = vacation_summary_for_user(request.args, current_user())
    if error:
        return service_error_response(error, status)
    return success_response(data)
