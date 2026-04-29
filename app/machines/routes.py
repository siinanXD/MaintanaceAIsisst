from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import InventoryMaterial, Machine, Role, ShiftPlanEntry
from app.security import roles_required


machines_bp = Blueprint("machines", __name__)


def parse_required_employees(value):
    """Parse and validate the required employee count for a machine."""
    try:
        amount = int(value or 1)
    except (TypeError, ValueError) as exc:
        raise ValueError("required_employees must be a number") from exc
    if amount < 1:
        raise ValueError("required_employees must be at least 1")
    return amount


@machines_bp.get("")
@roles_required(Role.MASTER_ADMIN)
def list_machines():
    """Return all machines for admin views and planning forms."""
    machines = Machine.query.order_by(Machine.name.asc()).all()
    return jsonify([machine.to_dict() for machine in machines])


@machines_bp.post("")
@roles_required(Role.MASTER_ADMIN)
def create_machine():
    """Create a machine with production output and staffing requirement."""
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    if Machine.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "machine already exists"}), 409
    try:
        machine = Machine(
            name=data["name"].strip(),
            produced_item=data.get("produced_item", "").strip(),
            required_employees=parse_required_employees(data.get("required_employees")),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.add(machine)
    db.session.commit()
    return jsonify(machine.to_dict()), 201


@machines_bp.put("/<int:machine_id>")
@roles_required(Role.MASTER_ADMIN)
def update_machine(machine_id):
    """Update machine metadata used by inventory and shift planning."""
    machine = Machine.query.get_or_404(machine_id)
    data = request.get_json(silent=True) or {}
    if "name" in data:
        machine.name = data["name"].strip()
    if "produced_item" in data:
        machine.produced_item = data["produced_item"].strip()
    if "required_employees" in data:
        try:
            machine.required_employees = parse_required_employees(data["required_employees"])
        except ValueError as exc:
            return jsonify({"error": str(exc)}), 400
    db.session.commit()
    return jsonify(machine.to_dict())


@machines_bp.delete("/<int:machine_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_machine(machine_id):
    """Delete a machine and detach related inventory and plan entries."""
    machine = Machine.query.get_or_404(machine_id)
    InventoryMaterial.query.filter_by(machine_id=machine.id).update({"machine_id": None})
    ShiftPlanEntry.query.filter_by(machine_id=machine.id).update({"machine_id": None})
    db.session.delete(machine)
    db.session.commit()
    return "", 204
