"""Admin API routes for user and audit management."""

from flask import Blueprint, jsonify, request

from app.auth.services import find_department, parse_role
from app.extensions import db
from app.models import Employee, Role, User
from app.permissions import (
    replace_user_permissions,
    serialize_permissions,
    upsert_default_permissions,
)
from app.responses import error_response
from app.security import roles_required
from app.services.ai_audit_service import ai_analytics_summary

admin_bp = Blueprint("admin", __name__)


def parse_optional_bool(value, default=True):
    """Parse optional JSON booleans and common string values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError("is_active must be a boolean")


def find_user_conflict(username=None, email=None, exclude_user_id=None):
    """Return an existing user with the same username or email, if any."""
    filters = []
    if username:
        filters.append(User.username == username)
    if email:
        filters.append(User.email == email)
    if not filters:
        return None

    query = User.query.filter(db.or_(*filters))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first()


def validate_user_department(role, department):
    """Raise when a non-admin user has no department assignment."""
    if role != Role.MASTER_ADMIN and not department:
        raise ValueError("department_id or department is required")


def find_employee(employee_id):
    """Return an employee for an optional admin user payload value."""
    if employee_id in (None, ""):
        return None
    try:
        parsed_employee_id = int(employee_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("employee_id must be a valid employee id") from exc
    employee = db.session.get(Employee, parsed_employee_id)
    if not employee:
        raise ValueError("employee_id does not reference an existing employee")
    return employee


@admin_bp.get("/users")
@roles_required(Role.MASTER_ADMIN)
def list_users():
    """Return users filtered by optional query parameters: q, role, status."""
    q = request.args.get("q", "").strip()
    role_param = request.args.get("role", "").strip()
    status_param = request.args.get("status", "").strip()

    query = User.query
    if q:
        query = query.filter(db.or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if role_param:
        try:
            query = query.filter(User.role == Role(role_param))
        except ValueError:
            return error_response(f"Invalid role: {role_param}", 400)
    if status_param == "active":
        query = query.filter(User.is_active.is_(True))
    elif status_param == "inactive":
        query = query.filter(User.is_active.is_(False))

    users = query.order_by(User.id.asc()).all()
    return jsonify([user.to_dict() for user in users])


@admin_bp.get("/ai/summary")
@roles_required(Role.MASTER_ADMIN)
def ai_summary():
    """Return AI audit and feedback analytics for administrators."""
    try:
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError):
        return error_response("days must be an integer between 1 and 90", 400)
    if days < 1 or days > 90:
        return error_response("days must be an integer between 1 and 90", 400)
    return jsonify(ai_analytics_summary(days))


@admin_bp.post("/users")
@roles_required(Role.MASTER_ADMIN)
def create_user():
    """Create a user and assign default permissions for the selected role."""
    data = request.get_json(silent=True) or {}
    required = ["username", "email", "password", "role"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}", 400)

    if find_user_conflict(data["username"], data["email"]):
        return error_response("Username or email already exists", 409)

    try:
        role = parse_role(data.get("role"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    department = find_department(data.get("department_id"), data.get("department"))
    try:
        validate_user_department(role, department)
        is_active = parse_optional_bool(data.get("is_active"), default=True)
        employee = find_employee(data.get("employee_id"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    user = User(
        username=data["username"],
        email=data["email"],
        role=role,
        department=department,
        is_active=is_active,
    )
    user.employee = employee
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()
    upsert_default_permissions(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@admin_bp.put("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def update_user(user_id):
    """Update a user account and fill missing default permissions."""
    user = db.get_or_404(User, user_id)
    data = request.get_json(silent=True) or {}

    username = data.get("username", user.username)
    email = data.get("email", user.email)
    if find_user_conflict(username, email, exclude_user_id=user.id):
        return error_response("Username or email already exists", 409)

    role = user.role
    if "role" in data:
        try:
            role = parse_role(data["role"])
        except ValueError as exc:
            return error_response(str(exc), 400)
    department = user.department
    if "department_id" in data or "department" in data:
        department = find_department(data.get("department_id"), data.get("department"))
    is_active = user.is_active
    if "is_active" in data:
        try:
            is_active = parse_optional_bool(data["is_active"])
        except ValueError as exc:
            return error_response(str(exc), 400)
    employee = user.employee
    if "employee_id" in data:
        try:
            employee = find_employee(data.get("employee_id"))
        except ValueError as exc:
            return error_response(str(exc), 400)
    try:
        validate_user_department(role, department)
    except ValueError as exc:
        return error_response(str(exc), 400)

    user.username = username
    user.email = email
    user.role = role
    user.department = department
    user.employee = employee
    user.is_active = is_active

    upsert_default_permissions(user)
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.get("/users/<int:user_id>/permissions")
@roles_required(Role.MASTER_ADMIN)
def get_user_permissions(user_id):
    """Return effective dashboard permissions for a user."""
    user = db.get_or_404(User, user_id)
    return jsonify(serialize_permissions(user))


@admin_bp.put("/users/<int:user_id>/permissions")
@roles_required(Role.MASTER_ADMIN)
def update_user_permissions(user_id):
    """Replace dashboard permissions for a user."""
    user = db.get_or_404(User, user_id)
    data = request.get_json(silent=True) or {}
    try:
        replace_user_permissions(user, data)
    except ValueError as exc:
        return error_response(str(exc), 400)
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/reset-password")
@roles_required(Role.MASTER_ADMIN)
def reset_password(user_id):
    """Reset a user's password."""
    user = db.get_or_404(User, user_id)
    password = (request.get_json(silent=True) or {}).get("password")
    if not password:
        return error_response("password is required", 400)
    user.set_password(password)
    db.session.commit()
    return jsonify({"message": "Password reset successful"})


@admin_bp.post("/users/<int:user_id>/lock")
@roles_required(Role.MASTER_ADMIN)
def lock_user(user_id):
    """Lock a user account."""
    user = db.get_or_404(User, user_id)
    user.is_active = False
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/unlock")
@roles_required(Role.MASTER_ADMIN)
def unlock_user(user_id):
    """Unlock a user account."""
    user = db.get_or_404(User, user_id)
    user.is_active = True
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.delete("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_user(user_id):
    """Delete a user account."""
    user = db.get_or_404(User, user_id)
    db.session.delete(user)
    db.session.commit()
    return "", 204
