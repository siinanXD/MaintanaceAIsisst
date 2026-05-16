"""Machine API routes."""

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.machines.maintenance_services import (
    create_maintenance_plan,
    delete_maintenance_plan,
    generate_due_maintenance_tasks,
    get_visible_maintenance_plan,
    recommend_preventive_maintenance,
    update_maintenance_plan,
    visible_maintenance_plans_query,
)
from app.machines.services import answer_machine_assistant, build_machine_history
from app.models import InventoryMaterial, Machine, MaintenancePlan, ShiftPlanEntry
from app.responses import error_response, service_error_response, success_response
from app.security import current_user, dashboard_permission_required

machines_bp = Blueprint("machines", __name__)


def parse_required_employees(value):
    """Parse and validate the required employee count for a machine."""
    try:
        amount = int(1 if value in (None, "") else value)
    except (TypeError, ValueError) as exc:
        raise ValueError("required_employees must be a number") from exc
    if amount < 1:
        raise ValueError("required_employees must be at least 1")
    return amount


@machines_bp.get("")
@dashboard_permission_required("machines", "view")
def list_machines():
    """Return all machines for admin views and planning forms."""
    machines = Machine.query.order_by(Machine.name.asc()).all()
    return jsonify([machine.to_dict() for machine in machines])


@machines_bp.post("")
@dashboard_permission_required("machines", "write")
def create_machine():
    """Create a machine with production output and staffing requirement."""
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return error_response("name is required", 400)
    if Machine.query.filter_by(name=data["name"]).first():
        return error_response("machine already exists", 409)
    try:
        machine = Machine(
            name=data["name"].strip(),
            produced_item=data.get("produced_item", "").strip(),
            required_employees=parse_required_employees(data.get("required_employees")),
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    db.session.add(machine)
    db.session.commit()
    return jsonify(machine.to_dict()), 201


@machines_bp.get("/maintenance-plans")
@dashboard_permission_required("machines", "view")
def list_maintenance_plans():
    """Return visible recurring maintenance plans."""
    plans = (
        visible_maintenance_plans_query(current_user())
        .order_by(MaintenancePlan.next_due_date.asc(), MaintenancePlan.id.asc())
        .all()
    )
    return success_response(
        [plan.to_dict() for plan in plans],
        message="Maintenance plans loaded",
    )


@machines_bp.post("/maintenance-plans")
@dashboard_permission_required("machines", "write")
def add_maintenance_plan():
    """Create a recurring maintenance plan."""
    plan, error, status = create_maintenance_plan(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(plan.to_dict(), status, "Maintenance plan created")


@machines_bp.post("/maintenance-plans/generate-due")
@dashboard_permission_required("machines", "write")
def generate_due_maintenance():
    """Generate open tasks for due recurring maintenance plans."""
    result, error, status = generate_due_maintenance_tasks(current_user())
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Maintenance tasks generated")


@machines_bp.get("/maintenance-recommendations")
@dashboard_permission_required("machines", "view")
def preventive_maintenance_recommendations():
    """Return read-only preventive maintenance recommendations."""
    result, error, status = recommend_preventive_maintenance(
        current_user(),
        limit=request.args.get("limit", 5),
    )
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Maintenance recommendations loaded")


@machines_bp.put("/maintenance-plans/<int:plan_id>")
@dashboard_permission_required("machines", "write")
def edit_maintenance_plan(plan_id):
    """Update a visible recurring maintenance plan."""
    plan = get_visible_maintenance_plan(plan_id, current_user())
    if not plan:
        return error_response("Maintenance plan not found", 404)
    updated, error, status = update_maintenance_plan(
        plan,
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(updated.to_dict(), status, "Maintenance plan updated")


@machines_bp.delete("/maintenance-plans/<int:plan_id>")
@dashboard_permission_required("machines", "write")
def remove_maintenance_plan(plan_id):
    """Delete a visible recurring maintenance plan."""
    plan = get_visible_maintenance_plan(plan_id, current_user())
    if not plan:
        return error_response("Maintenance plan not found", 404)
    error, status = delete_maintenance_plan(plan)
    if error:
        return service_error_response(error, status)
    return "", status


@machines_bp.get("/<int:machine_id>/history")
@dashboard_permission_required("machines", "view")
def machine_history(machine_id):
    """Return a read-only history for one machine."""
    machine = db.get_or_404(Machine, machine_id)
    return success_response(
        build_machine_history(machine, current_user()),
        message="Machine history loaded",
    )


@machines_bp.post("/<int:machine_id>/assistant")
@dashboard_permission_required("machines", "view")
def machine_assistant(machine_id):
    """Answer a machine-specific maintenance question."""
    machine = db.get_or_404(Machine, machine_id)
    result, error, status = answer_machine_assistant(
        machine,
        current_user(),
        request.get_json(silent=True) or {},
    )
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Machine assistant response generated")


@machines_bp.put("/<int:machine_id>")
@dashboard_permission_required("machines", "write")
def update_machine(machine_id):
    """Update machine metadata used by inventory and shift planning."""
    machine = db.get_or_404(Machine, machine_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        machine.name = data["name"].strip()
    if "produced_item" in data:
        machine.produced_item = data["produced_item"].strip()
    if "required_employees" in data:
        try:
            machine.required_employees = parse_required_employees(data["required_employees"])
        except ValueError as exc:
            return error_response(str(exc), 400)
    db.session.commit()
    return jsonify(machine.to_dict())


@machines_bp.delete("/<int:machine_id>")
@dashboard_permission_required("machines", "write")
def delete_machine(machine_id):
    """Delete a machine and detach related inventory and plan entries."""
    machine = db.get_or_404(Machine, machine_id)
    InventoryMaterial.query.filter_by(machine_id=machine.id).update({"machine_id": None})
    ShiftPlanEntry.query.filter_by(machine_id=machine.id).update({"machine_id": None})
    db.session.delete(machine)
    db.session.commit()
    return "", 204
