from flask import Blueprint, jsonify, request

from app.auth.services import find_department, parse_role
from app.extensions import db
from app.models import Role, User
from app.security import roles_required


admin_bp = Blueprint("admin", __name__)


@admin_bp.get("/users")
@roles_required(Role.MASTER_ADMIN)
def list_users():
    users = User.query.order_by(User.id.asc()).all()
    return jsonify([user.to_dict() for user in users])


@admin_bp.post("/users")
@roles_required(Role.MASTER_ADMIN)
def create_user():
    data = request.get_json(silent=True) or {}
    required = ["username", "email", "password", "role"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    if User.query.filter((User.username == data["username"]) | (User.email == data["email"])).first():
        return jsonify({"error": "Username or email already exists"}), 409

    try:
        role = parse_role(data.get("role"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    department = find_department(data.get("department_id"), data.get("department"))
    if role != Role.MASTER_ADMIN and not department:
        return jsonify({"error": "department_id or department is required"}), 400

    user = User(
        username=data["username"],
        email=data["email"],
        role=role,
        department=department,
        is_active=bool(data.get("is_active", True)),
    )
    user.set_password(data["password"])
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


@admin_bp.put("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def update_user(user_id):
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
            return jsonify({"error": str(exc)}), 400
    if "department_id" in data or "department" in data:
        user.department = find_department(data.get("department_id"), data.get("department"))
    if "is_active" in data:
        user.is_active = bool(data["is_active"])

    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/reset-password")
@roles_required(Role.MASTER_ADMIN)
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    password = (request.get_json(silent=True) or {}).get("password")
    if not password:
        return jsonify({"error": "password is required"}), 400
    user.set_password(password)
    db.session.commit()
    return jsonify({"message": "Password reset successful"})


@admin_bp.post("/users/<int:user_id>/lock")
@roles_required(Role.MASTER_ADMIN)
def lock_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = False
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/unlock")
@roles_required(Role.MASTER_ADMIN)
def unlock_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_active = True
    db.session.commit()
    return jsonify(user.to_dict())


@admin_bp.delete("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return "", 204
