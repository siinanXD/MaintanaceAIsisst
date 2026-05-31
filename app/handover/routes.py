"""Shift handover API routes."""

from flask import Blueprint, request

from app.handover.services import (
    complete_shift_handover,
    create_shift_handover,
    summarize_shift_handover,
    update_shift_handover,
    visible_handovers_query,
)
from app.models import ShiftHandover
from app.responses import error_response, success_response
from app.security import current_user, dashboard_permission_required

handover_bp = Blueprint("handover", __name__)


@handover_bp.get("")
@dashboard_permission_required("shiftplans", "view")
def list_handovers():
    """Return shift handover records, optionally filtered."""
    query = visible_handovers_query(current_user()).order_by(
        ShiftHandover.shift_date.desc(),
        ShiftHandover.id.desc(),
    )
    if dept := request.args.get("department"):
        query = query.filter(ShiftHandover.department == dept)
    if date_str := request.args.get("date"):
        from app.shiftplans.services import parse_date

        try:
            query = query.filter(ShiftHandover.shift_date == parse_date(date_str))
        except ValueError:
            pass
    if shift_type := request.args.get("shift_type"):
        query = query.filter(ShiftHandover.shift_type == shift_type)
    if status := request.args.get("status"):
        query = query.filter(ShiftHandover.status == status)
    if machine_id := request.args.get("machine_id"):
        try:
            query = query.filter(ShiftHandover.machine_id == int(machine_id))
        except (TypeError, ValueError):
            return error_response("machine_id muss eine Zahl sein", 400)
    return success_response([handover.to_dict() for handover in query.all()])


@handover_bp.post("")
@dashboard_permission_required("shiftplans", "write")
def create_handover():
    """Create a new shift handover record."""
    handover, error, status = create_shift_handover(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return error_response(error["error"], status)
    return success_response(handover.to_dict(), status_code=201, message="Übergabe erstellt")


@handover_bp.get("/<int:handover_id>")
@dashboard_permission_required("shiftplans", "view")
def get_handover(handover_id):
    """Return one visible handover record by id."""
    handover = visible_handovers_query(current_user()).filter_by(id=handover_id).first_or_404()
    return success_response(handover.to_dict())


@handover_bp.get("/<int:handover_id>/summary")
@dashboard_permission_required("shiftplans", "view")
def handover_summary(handover_id):
    """Return an AI-ready summary for one visible shift handover."""
    user = current_user()
    handover = visible_handovers_query(user).filter_by(id=handover_id).first_or_404()
    return success_response(
        summarize_shift_handover(handover, user),
        message="Handover summary generated",
    )


@handover_bp.patch("/<int:handover_id>")
@dashboard_permission_required("shiftplans", "write")
def update_handover(handover_id):
    """Update an open handover record."""
    handover = visible_handovers_query(current_user()).filter_by(id=handover_id).first_or_404()
    updated, error, status = update_shift_handover(
        handover,
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return error_response(error["error"], status)
    return success_response(updated.to_dict(), message="Aktualisiert")


@handover_bp.post("/<int:handover_id>/complete")
@dashboard_permission_required("shiftplans", "write")
def complete_handover(handover_id):
    """Mark a handover as completed."""
    handover = visible_handovers_query(current_user()).filter_by(id=handover_id).first_or_404()
    updated, error, status = complete_shift_handover(handover, current_user())
    if error:
        return error_response(error["error"], status)
    return success_response(updated.to_dict(), message="Übergabe abgeschlossen")
