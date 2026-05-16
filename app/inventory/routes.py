"""Inventory API routes."""

from flask import Blueprint, jsonify, request
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.extensions import db
from app.inventory.services import forecast_inventory_risks
from app.models import InventoryMaterial, Machine, Site
from app.responses import (
    error_response,
    optional_paginated_response,
    service_error_response,
    success_response,
)
from app.security import current_user, dashboard_permission_required
from app.services.operations_tracking_service import record_event

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
    return db.session.get(Machine, int(data["machine_id"]))


def site_for_payload(data, machine=None):
    """Resolve an optional site reference from request data or linked machine."""
    if data.get("site_id"):
        return db.session.get(Site, int(data["site_id"]))
    return machine.site if machine and machine.site else None


@inventory_bp.get("")
@dashboard_permission_required("inventory", "view")
def list_materials():
    """Return inventory materials, optionally paginated for large stock catalogs."""
    query = (
        InventoryMaterial.query.options(selectinload(InventoryMaterial.machine))
        .order_by(InventoryMaterial.name.asc(), InventoryMaterial.id.asc())
    )
    site_id = request.args.get("site_id", type=int)
    if site_id is not None:
        query = query.filter(InventoryMaterial.site_id == site_id)
    machine_id = request.args.get("machine_id", type=int)
    if machine_id is not None:
        query = query.filter(InventoryMaterial.machine_id == machine_id)
    return optional_paginated_response(
        query,
        lambda material: material.to_dict(),
        message="Inventory materials loaded",
        default_limit=100,
        max_limit=200,
    )


@inventory_bp.get("/summary")
@dashboard_permission_required("inventory", "view")
def inventory_summary():
    """Return inventory totals, with optional material rows for legacy clients."""
    include_materials = str(request.args.get("include_materials", "true")).lower() not in {
        "0",
        "false",
        "no",
        "off",
    }
    totals_query = db.session.query(
        func.count(InventoryMaterial.id),
        func.coalesce(func.sum(InventoryMaterial.quantity), 0),
        func.coalesce(func.sum(InventoryMaterial.quantity * InventoryMaterial.unit_cost), 0.0),
    )
    site_id = request.args.get("site_id", type=int)
    if site_id is not None:
        totals_query = totals_query.filter(InventoryMaterial.site_id == site_id)
    machine_id = request.args.get("machine_id", type=int)
    if machine_id is not None:
        totals_query = totals_query.filter(InventoryMaterial.machine_id == machine_id)
    totals = totals_query.one()
    payload = {
        "material_count": int(totals[0] or 0),
        "total_quantity": int(totals[1] or 0),
        "total_value": round(float(totals[2] or 0.0), 2),
    }
    if include_materials:
        materials = (
            InventoryMaterial.query.options(selectinload(InventoryMaterial.machine))
            .order_by(InventoryMaterial.name.asc(), InventoryMaterial.id.asc())
        )
        if site_id is not None:
            materials = materials.filter(InventoryMaterial.site_id == site_id)
        if machine_id is not None:
            materials = materials.filter(InventoryMaterial.machine_id == machine_id)
        materials = materials.all()
        payload["materials"] = [material.to_dict() for material in materials]
    return jsonify(payload)


@inventory_bp.post("/forecast")
@dashboard_permission_required("inventory", "view")
@dashboard_permission_required("tasks", "view")
def inventory_forecast():
    """Return spare-part forecasts for visible tasks and linked inventory."""
    forecast, error, status = forecast_inventory_risks(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(forecast, status, "Inventory forecast loaded")


@inventory_bp.post("")
@dashboard_permission_required("inventory", "write")
def create_material():
    """Create an inventory material and link it to a machine if provided."""
    data = request.get_json(silent=True) or {}
    if not data.get("name"):
        return error_response("name is required", 400)
    try:
        machine = machine_for_payload(data)
        material = InventoryMaterial(
            name=data["name"].strip(),
            unit_cost=parse_float(data.get("unit_cost"), "unit_cost"),
            quantity=parse_int(data.get("quantity"), "quantity"),
            min_quantity=parse_int(data.get("min_quantity"), "min_quantity"),
            criticality=str(data.get("criticality") or "normal").strip(),
            lead_time_days=parse_int(data.get("lead_time_days"), "lead_time_days"),
            manufacturer=data.get("manufacturer", "").strip(),
            site=site_for_payload(data, machine=machine),
            machine=machine,
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    db.session.add(material)
    db.session.flush()
    record_event(
        "inventory.created",
        "inventory",
        entity_type="inventory_material",
        entity_id=material.id,
        user=current_user(),
        machine=material.machine,
        site_id=material.site_id,
        metadata={
            "name": material.name,
            "quantity": material.quantity,
            "min_quantity": material.min_quantity,
            "criticality": material.criticality,
        },
    )
    db.session.commit()
    return jsonify(material.to_dict()), 201


@inventory_bp.put("/<int:material_id>")
@dashboard_permission_required("inventory", "write")
def update_material(material_id):
    """Update an inventory material including cost, quantity and machine."""
    material = db.get_or_404(InventoryMaterial, material_id)
    data = request.get_json(silent=True) or {}
    try:
        old_quantity = material.quantity
        if "name" in data:
            material.name = data["name"].strip()
        if "unit_cost" in data:
            material.unit_cost = parse_float(data["unit_cost"], "unit_cost")
        if "quantity" in data:
            material.quantity = parse_int(data["quantity"], "quantity")
        if "min_quantity" in data:
            material.min_quantity = parse_int(data["min_quantity"], "min_quantity")
        if "criticality" in data:
            material.criticality = str(data.get("criticality") or "normal").strip()
        if "lead_time_days" in data:
            material.lead_time_days = parse_int(data["lead_time_days"], "lead_time_days")
        if "manufacturer" in data:
            material.manufacturer = data["manufacturer"].strip()
        if "machine_id" in data:
            material.machine = machine_for_payload(data)
        if "site_id" in data or "machine_id" in data:
            material.site = site_for_payload(data, machine=material.machine)
    except ValueError as exc:
        return error_response(str(exc), 400)
    event_type = (
        "inventory.quantity_changed"
        if old_quantity != material.quantity
        else "inventory.updated"
    )
    record_event(
        event_type,
        "inventory",
        entity_type="inventory_material",
        entity_id=material.id,
        user=current_user(),
        machine=material.machine,
        site_id=material.site_id,
        metadata={
            "name": material.name,
            "old_quantity": old_quantity,
            "new_quantity": material.quantity,
            "delta": material.quantity - old_quantity,
            "min_quantity": material.min_quantity,
            "criticality": material.criticality,
        },
    )
    db.session.commit()
    return jsonify(material.to_dict())


@inventory_bp.delete("/<int:material_id>")
@dashboard_permission_required("inventory", "write")
def delete_material(material_id):
    """Delete an inventory material from the lager."""
    material = db.get_or_404(InventoryMaterial, material_id)
    record_event(
        "inventory.deleted",
        "inventory",
        entity_type="inventory_material",
        entity_id=material.id,
        user=current_user(),
        machine=material.machine,
        site_id=material.site_id,
        metadata={"name": material.name, "quantity": material.quantity},
    )
    db.session.delete(material)
    db.session.commit()
    return "", 204
