from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.ai.services import ai_status, answer_chat, daily_briefing, save_chat_message
from app.extensions import db
from app.models import AIFeedback, Role
from app.responses import error_response, service_error_response, success_response
from app.security import current_user, has_dashboard_permission, roles_required


ai_bp = Blueprint("ai", __name__)


@ai_bp.post("/chat")
@jwt_required()
def chat():
    """Handle authenticated chat requests for the maintenance assistant."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return error_response("message is required", 400)

    user = current_user()
    result = answer_chat(message, user)
    save_chat_message(user, message, result["answer"])

    return success_response(result, message="AI response generated")


@ai_bp.get("/status")
@roles_required(Role.MASTER_ADMIN)
def status():
    """Return redacted AI configuration and last-error status."""
    return success_response(ai_status(), message="AI status loaded")


@ai_bp.get("/daily-briefing")
@jwt_required()
def briefing():
    """Return a daily maintenance briefing for the current user."""
    return success_response(daily_briefing(current_user()), message="Daily briefing loaded")


@ai_bp.post("/error-assistant")
@jwt_required()
def error_assistant():
    """Search the error catalog and return causes and fixes for a fault description.

    Request body (JSON):
        query (str, required): Free-text fault description, e.g.
            "Maschine 3 zeigt Fehler E42 und macht Geraeusche."
        limit (int, optional): Maximum number of catalog matches to return (1–20,
            default 5).

    Response ``data`` keys:
        query        — the original query string
        matches      — scored catalog entries (entry, score, reason)
        causes       — deduplicated list of possible-cause strings
        fixes        — deduplicated list of solution strings
        diagnostics  — search metadata and ai_enhanced flag
    """
    from app.services.error_assistant_service import run_error_assistant

    user = current_user()
    if not has_dashboard_permission(user, "errors", "view"):
        return error_response("Keine Berechtigung fuer den Fehlerkatalog", 403)

    data = request.get_json(silent=True) or {}
    result, error, status = run_error_assistant(data, user)
    if error:
        return service_error_response(error, status)
    return success_response(result, message="Error assistant result")


@ai_bp.post("/feedback")
@jwt_required()
def feedback():
    """Store user feedback for an AI response."""
    data = request.get_json(silent=True) or {}
    rating = data.get("rating")
    if rating not in ("helpful", "not_helpful"):
        return error_response("rating must be helpful or not_helpful", 400)
    prompt = str(data.get("prompt") or "").strip()
    response = str(data.get("response") or "").strip()
    if not prompt or not response:
        return error_response("prompt and response are required", 400)

    feedback_entry = AIFeedback(
        user_id=current_user().id,
        prompt=prompt[:4000],
        response=response[:8000],
        rating=rating,
        comment=str(data.get("comment") or "").strip()[:1000],
    )
    db.session.add(feedback_entry)
    db.session.commit()
    return success_response(
        feedback_entry.to_dict(),
        201,
        "Feedback saved",
    )
