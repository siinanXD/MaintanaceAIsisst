from datetime import datetime, timezone

from flask import Blueprint, request

from app.extensions import db
from app.models import ShiftHandover
from app.responses import error_response, success_response
from app.security import current_user, dashboard_permission_required


handover_bp = Blueprint("handover", __name__)


@handover_bp.get("")
@dashboard_permission_required("shiftplans", "view")
def list_handovers():
    """Return shift handover records, optionally filtered."""
    query = ShiftHandover.query.order_by(ShiftHandover.shift_date.desc(), ShiftHandover.id.desc())
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
    return success_response([h.to_dict() for h in query.all()])


@handover_bp.post("")
@dashboard_permission_required("shiftplans", "write")
def create_handover():
    """Create a new shift handover record."""
    from app.shiftplans.services import parse_date
    data = request.get_json(silent=True) or {}
    try:
        shift_date = parse_date(data.get("shift_date"))
    except ValueError as exc:
        return error_response(str(exc), 400)
    shift_type = str(data.get("shift_type") or "").strip()
    department = str(data.get("department") or "").strip()
    if not shift_type or not department:
        return error_response("shift_type und department erforderlich", 400)

    handover = ShiftHandover(
        plan_id       = data.get("plan_id"),
        department    = department,
        shift_date    = shift_date,
        shift_type    = shift_type,
        content       = str(data.get("content") or "")[:2000],
        open_tasks    = str(data.get("open_tasks") or "")[:2000],
        machine_notes = str(data.get("machine_notes") or "")[:2000],
        next_notes    = str(data.get("next_notes") or "")[:2000],
        handed_over_by= current_user().id,
    )
    db.session.add(handover)
    db.session.commit()
    return success_response(handover.to_dict(), status_code=201, message="Übergabe erstellt")


@handover_bp.get("/<int:handover_id>")
@dashboard_permission_required("shiftplans", "view")
def get_handover(handover_id):
    handover = ShiftHandover.query.get_or_404(handover_id)
    return success_response(handover.to_dict())


@handover_bp.patch("/<int:handover_id>")
@dashboard_permission_required("shiftplans", "write")
def update_handover(handover_id):
    """Update an open handover record."""
    handover = ShiftHandover.query.get_or_404(handover_id)
    if handover.status == "completed":
        return error_response("Abgeschlossene Übergaben können nicht bearbeitet werden", 403)
    data = request.get_json(silent=True) or {}
    for field in ("content", "open_tasks", "machine_notes", "next_notes"):
        if field in data:
            setattr(handover, field, str(data[field])[:2000])
    db.session.commit()
    return success_response(handover.to_dict(), message="Aktualisiert")


@handover_bp.post("/<int:handover_id>/complete")
@dashboard_permission_required("shiftplans", "write")
def complete_handover(handover_id):
    """Mark a handover as completed."""
    handover = ShiftHandover.query.get_or_404(handover_id)
    if handover.status == "completed":
        return error_response("Übergabe bereits abgeschlossen", 409)
    handover.status         = "completed"
    handover.handed_over_at = datetime.now(timezone.utc)
    db.session.commit()
    return success_response(handover.to_dict(), message="Übergabe abgeschlossen")
