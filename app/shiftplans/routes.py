from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Role, ShiftPlan
from app.security import roles_required
from app.shiftplans.services import generate_shift_plan


shiftplans_bp = Blueprint("shiftplans", __name__)


@shiftplans_bp.get("")
@roles_required(Role.MASTER_ADMIN)
def list_shiftplans():
    """Return generated shift plans with their entries."""
    plans = ShiftPlan.query.order_by(ShiftPlan.created_at.desc()).all()
    return jsonify([plan.to_dict() for plan in plans])


@shiftplans_bp.post("/generate")
@roles_required(Role.MASTER_ADMIN)
def generate():
    """Generate and persist a production shift plan."""
    plan, error, status = generate_shift_plan(request.get_json(silent=True) or {})
    if error:
        return jsonify(error), status
    return jsonify(plan.to_dict()), status


@shiftplans_bp.delete("/<int:plan_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_shiftplan(plan_id):
    """Delete a generated shift plan and its entries."""
    plan = ShiftPlan.query.get_or_404(plan_id)
    db.session.delete(plan)
    db.session.commit()
    return "", 204
