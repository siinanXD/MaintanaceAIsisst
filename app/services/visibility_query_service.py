"""Permission-safe query helpers for AI-visible reference data."""

from sqlalchemy import false

from app.models import Employee, InventoryMaterial, Machine, ShiftPlan
from app.security import employee_access_level, has_dashboard_permission


def visible_machines_query(user):
    """Return machines visible to a user with machine dashboard access."""
    query = Machine.query
    if not has_dashboard_permission(user, "machines", "view"):
        return query.filter(false())
    return query


def visible_inventory_materials_query(user):
    """Return inventory materials visible to a user with inventory dashboard access."""
    query = InventoryMaterial.query
    if not has_dashboard_permission(user, "inventory", "view"):
        return query.filter(false())
    return query


def visible_employees_query(user):
    """Return employee rows visible to the user's employee dashboard access level."""
    query = Employee.query
    if (
        not has_dashboard_permission(user, "employees", "view")
        or employee_access_level(user) == "none"
    ):
        return query.filter(false())
    if getattr(user, "is_admin", False):
        return query
    department = getattr(getattr(user, "department", None), "name", "")
    if department:
        return query.filter(Employee.department == department)
    return query.filter(false())


def visible_shiftplans_query(user):
    """Return shift plans visible to a user with shift planning dashboard access."""
    query = ShiftPlan.query
    if not has_dashboard_permission(user, "shiftplans", "view"):
        return query.filter(false())
    if getattr(user, "is_admin", False):
        return query
    department = getattr(getattr(user, "department", None), "name", "")
    if department:
        return query.filter(ShiftPlan.status == "published", ShiftPlan.department == department)
    return query.filter(false())
