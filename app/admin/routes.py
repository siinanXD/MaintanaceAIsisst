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


admin_bp = Blueprint("admin", __name__)


def find_employee(employee_id):
    """Return an employee for an optional admin user payload value."""
    if employee_id in (None, ""):
        return None
    try:
        parsed_employee_id = int(employee_id)
    except (TypeError, ValueError):
        raise ValueError("employee_id must be a valid employee id")
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
        query = query.filter(
            db.or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%"))
        )
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


@admin_bp.post("/users")
@roles_required(Role.MASTER_ADMIN)
def create_user():
    """Create a user and assign default permissions for the selected role."""
    data = request.get_json(silent=True) or {}
    required = ["username", "email", "password", "role"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}", 400)

    existing_user = User.query.filter(
        (User.username == data["username"]) | (User.email == data["email"])
    ).first()
    if existing_user:
        return error_response("Username or email already exists", 409)

    try:
        role = parse_role(data.get("role"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    department = find_department(data.get("department_id"), data.get("department"))
    if role != Role.MASTER_ADMIN and not department:
        return error_response("department_id or department is required", 400)

    user = User(
        username=data["username"],
        email=data["email"],
        role=role,
        department=department,
        is_active=bool(data.get("is_active", True)),
    )
    try:
        user.employee = find_employee(data.get("employee_id"))
    except ValueError as exc:
        return error_response(str(exc), 400)
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
    user = User.query.get_or_404(user_id)
    data = request.get_json(silent=True) or {}

    if "username" in data:
        user.username = data["username"]
    if "email" in data:
        user.email = data["email"]
    if "role" in data:
        try:
            user.role = parse_role(data["role"])
        except ValueError as exc:
            return error_response(str(exc), 400)
    if "department_id" in data or "department" in data:
        user.department = find_department(data.get("department_id"), data.get("department"))
    if "employee_id" in data:
        try:
            user.employee = find_employee(data.get("employee_id"))
        except ValueError as exc:
            return error_response(str(exc), 400)
    if "is_active" in data:
        user.is_active = bool(data["is_active"])

    upsert_default_permissions(user)
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.get("/users/<int:user_id>/permissions")
@roles_required(Role.MASTER_ADMIN)
def get_user_permissions(user_id):
    """Return effective dashboard permissions for a user."""
    user = User.query.get_or_404(user_id)
    return jsonify(serialize_permissions(user))


@admin_bp.put("/users/<int:user_id>/permissions")
@roles_required(Role.MASTER_ADMIN)
def update_user_permissions(user_id):
    """Replace dashboard permissions for a user."""
    user = User.query.get_or_404(user_id)
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
    user = User.query.get_or_404(user_id)
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
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/unlock")
@roles_required(Role.MASTER_ADMIN)
def unlock_user(user_id):
    """Unlock a user account."""
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.delete("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_user(user_id):
    """Delete a user account."""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return "", 204
