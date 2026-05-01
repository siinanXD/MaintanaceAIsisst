from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import ShiftPlan
from app.responses import service_error_response
from app.security import (
    current_user,
    dashboard_permission_required,
    employee_access_level,
    employee_access_required,
)
from app.shiftplans.services import generate_shift_plan


shiftplans_bp = Blueprint("shiftplans", __name__)


@shiftplans_bp.get("")
@dashboard_permission_required("shiftplans", "view")
def list_shiftplans():
    """Return generated shift plans with their entries."""
    plans = ShiftPlan.query.order_by(ShiftPlan.created_at.desc()).all()
    access_level = employee_access_level(current_user())
    return jsonify([plan.to_dict(access_level) for plan in plans])


@shiftplans_bp.post("/generate")
@dashboard_permission_required("shiftplans", "write")
@employee_access_required("shift")
def generate():
    """Generate and persist a production shift plan."""
    plan, error, status = generate_shift_plan(request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    access_level = employee_access_level(current_user())
    payload = plan.to_dict(access_level)
    payload["warnings"] = getattr(plan, "warnings", [])
    payload["coverage_summary"] = getattr(plan, "coverage_summary", {})
    return jsonify(payload), status


@shiftplans_bp.delete("/<int:plan_id>")
@dashboard_permission_required("shiftplans", "write")
def delete_shiftplan(plan_id):
    """Delete a generated shift plan and its entries."""
    plan = ShiftPlan.query.get_or_404(plan_id)
    db.session.delete(plan)
    db.session.commit()
    return "", 204
