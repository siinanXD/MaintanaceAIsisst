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
from app.shiftplans.services import calendar_entries_for_user, generate_shift_plan


shiftplans_bp = Blueprint("shiftplans", __name__)


@shiftplans_bp.get("")
@dashboard_permission_required("shiftplans", "view")
def list_shiftplans():
    """Return generated shift plans with their entries."""
    plans = ShiftPlan.query.order_by(ShiftPlan.created_at.desc()).all()
    access_level = employee_access_level(current_user())
    return jsonify([plan.to_dict(access_level) for plan in plans])


@shiftplans_bp.get("/calendar")
@dashboard_permission_required("dashboard", "view")
def shiftplan_calendar():
    """Return the current user's or selected employee's shift calendar."""
    payload, error, status = calendar_entries_for_user(
        current_user(),
        employee_id=request.args.get("employee_id"),
        start_date=request.args.get("start_date"),
        days=request.args.get("days", 14),
        plan_id=request.args.get("plan_id"),
    )
    if error:
        return service_error_response(error, status)
    return jsonify(payload), status


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
