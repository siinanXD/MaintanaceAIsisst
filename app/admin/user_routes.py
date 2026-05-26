"""Admin API route registrations."""

# ruff: noqa: F401, F403, F405

from app.admin.blueprint import admin_bp
from app.admin.route_helpers import *


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


@admin_bp.get("/permissions/schema")
@roles_required(Role.MASTER_ADMIN)
def permissions_schema():
    """Return labels, groups and role defaults for the permission editor."""
    return jsonify(permission_schema())


@admin_bp.post("/users")
@roles_required(Role.MASTER_ADMIN)
def create_user():
    """Create a user and assign default permissions for the selected role."""
    actor = current_admin_user()
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
    create_audit_log(
        actor,
        "user.create",
        "user",
        user.id,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict()), 201


@admin_bp.put("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def update_user(user_id):
    """Update a user account and fill missing default permissions."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
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
    create_audit_log(
        actor,
        "user.update",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
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
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    data = request.get_json(silent=True) or {}
    try:
        replace_user_permissions(user, data)
    except ValueError as exc:
        return error_response(str(exc), 400)
    db.session.commit()
    create_audit_log(
        actor,
        "permissions.update",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/reset-password")
@roles_required(Role.MASTER_ADMIN)
def reset_password(user_id):
    """Reset a user's password."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    password = (request.get_json(silent=True) or {}).get("password")
    if not password:
        return error_response("password is required", 400)
    user.set_password(password)
    db.session.commit()
    create_audit_log(
        actor,
        "user.reset_password",
        "user",
        user.id,
        before={"id": user.id, "username": user.username},
        after={"password_reset": True},
        commit=True,
    )
    return jsonify({"message": "Password reset successful"})


@admin_bp.post("/users/<int:user_id>/lock")
@roles_required(Role.MASTER_ADMIN)
def lock_user(user_id):
    """Lock a user account."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    user.is_active = False
    db.session.commit()
    create_audit_log(
        actor,
        "user.lock",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/unlock")
@roles_required(Role.MASTER_ADMIN)
def unlock_user(user_id):
    """Unlock a user account."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    user.is_active = True
    db.session.commit()
    create_audit_log(
        actor,
        "user.unlock",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.delete("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_user(user_id):
    """Delete a user account."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    db.session.delete(user)
    db.session.commit()
    create_audit_log(
        actor,
        "user.delete",
        "user",
        user_id,
        before=before,
        commit=True,
    )
    return "", 204


__all__ = [
    "list_users",
    "permissions_schema",
    "create_user",
    "update_user",
    "get_user_permissions",
    "update_user_permissions",
    "reset_password",
    "lock_user",
    "unlock_user",
    "delete_user",
]
