from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.ai.services import ai_status, answer_chat, save_chat_message
from app.models import Role
from app.security import current_user, roles_required


ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/chat")
@jwt_required()
def chat():
    """Handle authenticated chat requests for the maintenance assistant."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "message is required"}), 400

    user = current_user()
    result = answer_chat(message, user)
    save_chat_message(user, message, result["answer"])

    return jsonify(result)


@ai_bp.get("/status")
@roles_required(Role.MASTER_ADMIN)
def status():
    """Return redacted AI configuration and last-error status."""
    return jsonify(ai_status())
