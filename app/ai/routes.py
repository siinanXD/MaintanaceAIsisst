from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.ai.services import ai_status, answer_chat, save_chat_message
from app.extensions import db
from app.models import AIFeedback, Role
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


@ai_bp.post("/feedback")
@jwt_required()
def feedback():
    """Store user feedback for an AI response."""
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating not in ("helpful", "not_helpful"):
        return jsonify({"error": "rating must be helpful or not_helpful"}), 400
    prompt = str(data.get("prompt") or "").strip()
    response = str(data.get("response") or "").strip()
    if not prompt or not response:
        return jsonify({"error": "prompt and response are required"}), 400

    feedback_entry = AIFeedback(
        user_id=current_user().id,
        prompt=prompt[:4000],
        response=response[:8000],
        rating=rating,
        comment=str(data.get("comment") or "").strip()[:1000],
    )
    db.session.add(feedback_entry)
    db.session.commit()
    return jsonify(feedback_entry.to_dict()), 201
