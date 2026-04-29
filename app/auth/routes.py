from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.auth.services import authenticate, register_user
from app.security import current_user


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    user, error, status = register_user(request.get_json(silent=True) or {})
    if error:
        return jsonify(error), status
    return jsonify(user.to_dict()), status


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    login_value = data.get("login") or data.get("email") or data.get("username")
    password = data.get("password")
    if not login_value or not password:
        return jsonify({"error": "login/email/username and password are required"}), 400

    result = authenticate(login_value, password)
    if not result:
        return jsonify({"error": "Invalid credentials"}), 401
    if result.get("error"):
        return jsonify(result), 403
    return jsonify(result)


@auth_bp.get("/me")
@jwt_required()
def me():
    user = current_user()
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_dict())
