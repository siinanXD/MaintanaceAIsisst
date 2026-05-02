import logging
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from app.auth.services import authenticate, register_user
from app.core.logging import safe_identifier
from app.extensions import db
from app.models import TokenBlocklist
from app.responses import error_response, service_error_response
from app.security import current_user


auth_bp = Blueprint("auth", __name__)
logger = logging.getLogger(__name__)


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
        logger.warning("login_failed reason=missing_credentials")
        return error_response("login/email/username and password are required", 400)

    result = authenticate(login_value, password)
    if not result:
        logger.warning(
            "login_failed reason=invalid_credentials identifier_hash=%s",
            safe_identifier(login_value),
        )
        return error_response("Invalid credentials", 401)
    if result.get("error"):
        logger.warning(
            "login_failed reason=locked_user identifier_hash=%s",
            safe_identifier(login_value),
        )
        return service_error_response(result, 403)
    logger.info("login_success user_id=%s", result["user"]["id"])
    return jsonify(result)


@auth_bp.post("/logout")
@jwt_required()
def logout():
    """Revoke the current JWT so it can no longer be used."""
    jti = get_jwt()["jti"]
    db.session.add(TokenBlocklist(jti=jti, revoked_at=datetime.now(timezone.utc)))
    db.session.commit()
    logger.info("logout_success user_id=%s jti=%s", current_user() and current_user().id, jti)
    return jsonify({"message": "Logged out"}), 200


@auth_bp.get("/me")
@jwt_required()
def me():
    """Return the current authenticated user."""
    user = current_user()
    if not user:
        return error_response("User not found", 404)
    return jsonify(user.to_dict())
