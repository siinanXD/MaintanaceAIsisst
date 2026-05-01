from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import InventoryMaterial, Machine
from app.security import dashboard_permission_required


inventory_bp = Blueprint("inventory", __name__)


def parse_int(value, field_name, default=0):
    """Parse a non-negative integer from an inventory payload field."""
    try:
        amount = int(value if value not in (None, "") else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if amount < 0:
        raise ValueError(f"{field_name} must not be negative")
    return amount


def parse_float(value, field_name, default=0):
    """Parse a non-negative float from an inventory payload field."""
    try:
        amount = float(value if value not in (None, "") else default)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc
    if amount < 0:
        raise ValueError(f"{field_name} must not be negative")
    return amount


def machine_for_payload(data):
    """Resolve the optional machine reference from request data."""
    if not data.get("machine_id"):
        return None
    return Machine.query.get(data["machine_id"])


@inventory_bp.get("")
@dashboard_permission_required("inventory", "view")
def list_materials():
    """Return all inventory materials for the admin lager view."""
    materials = InventoryMaterial.query.order_by(InventoryMaterial.name.asc()).all()
    return jsonify([material.to_dict() for material in materials])


@inventory_bp.get("/summary")
@dashboard_permission_required("inventory", "view")
def inventory_summary():
    """Return material count, quantity and total inventory value."""
    materials = InventoryMaterial.query.order_by(InventoryMaterial.name.asc()).all()
    return jsonify(
        {
            "material_count": len(materials),
            "total_quantity": sum(material.quantity for material in materials),
            "total_value": round(sum(material.total_value for material in materials), 2),
            "materials": [material.to_dict() for material in materials],
        }
    )


@inventory_bp.post("")
@dashboard_permission_required("inventory", "write")
def create_material():
    """Create an inventory material and link it to a machine if provided."""
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return jsonify({"error": "name is required"}), 400
    try:
        material = InventoryMaterial(
            name=data["name"].strip(),
            unit_cost=parse_float(data.get("unit_cost"), "unit_cost"),
            quantity=parse_int(data.get("quantity"), "quantity"),
            manufacturer=data.get("manufacturer", "").strip(),
            machine=machine_for_payload(data),
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.add(material)
    db.session.commit()
    return jsonify(material.to_dict()), 201


@inventory_bp.put("/<int:material_id>")
@dashboard_permission_required("inventory", "write")
def update_material(material_id):
    """Update an inventory material including cost, quantity and machine."""
    material = InventoryMaterial.query.get_or_404(material_id)
    data = request.get_json(silent=True) or {}
    try:
        if "name" in data:
            material.name = data["name"].strip()
        if "unit_cost" in data:
            material.unit_cost = parse_float(data["unit_cost"], "unit_cost")
        if "quantity" in data:
            material.quantity = parse_int(data["quantity"], "quantity")
        if "manufacturer" in data:
            material.manufacturer = data["manufacturer"].strip()
        if "machine_id" in data:
            material.machine = machine_for_payload(data)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    db.session.commit()
    return jsonify(material.to_dict())


@inventory_bp.delete("/<int:material_id>")
@dashboard_permission_required("inventory", "write")
def delete_material(material_id):
    """Delete an inventory material from the lager."""
    material = InventoryMaterial.query.get_or_404(material_id)
    db.session.delete(material)
    db.session.commit()
    return "", 204
