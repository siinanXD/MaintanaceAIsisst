from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.auth.services import authenticate, register_user
from app.responses import error_response, service_error_response
from app.security import current_user


auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/register")
def register():
    """Register a new user account."""
    user, error, status = register_user(request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    return jsonify(user.to_dict()), status


@auth_bp.post("/login")
def login():
    """Authenticate a user and return a JWT access token."""
    data = request.get_json(silent=True) or {}
    login_value = data.get("login") or data.get("email") or data.get("username")
    password = data.get("password")
    if not login_value or not password:
        return error_response("login/email/username and password are required", 400)

    result = authenticate(login_value, password)
    if not result:
        return error_response("Invalid credentials", 401)
    if result.get("error"):
        return service_error_response(result, 403)
    return jsonify(result)


@auth_bp.get("/me")
@jwt_required()
def me():
    """Return the current authenticated user."""
    user = current_user()
    if not user:
        return error_response("User not found", 404)
    return jsonify(user.to_dict())
