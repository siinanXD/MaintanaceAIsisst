"""AI API routes for chat, briefings, and assistants."""

from flask import Blueprint, request
from flask_jwt_extended import jwt_required

from app.ai.services import ai_status, answer_chat, daily_briefing, save_chat_message
from app.extensions import db
from app.models import Role
from app.responses import error_response, service_error_response, success_response
from app.security import current_user, has_dashboard_permission, roles_required
from app.services.ai_feedback_service import record_ai_feedback
from app.services.ai_history_service import paginated_chat_history
from app.services.chat_template_service import chat_templates_for_user
from app.services.conversation_context_service import normalize_session_id
from app.services.error_assistant_service import run_error_assistant
from app.services.incident_timeline_service import incident_timeline
from app.services.knowledge_gap_service import maybe_track_knowledge_gap
from app.services.operations_tracking_service import record_event
from app.services.order_planning_service import plan_order

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
    session_id = normalize_session_id(data.get("session_id"))
    result = answer_chat(message, user, session_id=session_id)
    chat_message = save_chat_message(user, message, result, session_id=session_id)
    if chat_message:
        result["chat_message_id"] = chat_message.id
    maybe_track_knowledge_gap(message, user, result)
    diagnostics = result.get("diagnostics") or {}
    record_event(
        "ai.chat",
        "ai",
        entity_type="chat_message",
        user=user,
        department=user.department,
        source="ai",
        metadata={
            "response_type": result.get("response_type"),
            "source_count": len(result.get("sources") or []),
            "audit_event_id": diagnostics.get("audit_event_id"),
        },
        commit=True,
    )

    return success_response(result, message="AI response generated")


@ai_bp.get("/chat/history")
@jwt_required()
def chat_history():
    """Return the current user's searchable AI chat history."""
    try:
        result = paginated_chat_history(current_user(), request.args)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(result, message="Chat history loaded")


@ai_bp.get("/chat/templates")
@jwt_required()
def chat_templates():
    """Return permission-aware chat templates for the current user."""
    return success_response(
        chat_templates_for_user(current_user()),
        message="Chat templates loaded",
    )


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


@ai_bp.get("/incident-timeline")
@jwt_required()
def incident_timeline_view():
    """Return a permission-aware incident timeline for the current user."""
    return success_response(
        incident_timeline(current_user(), request.args),
        message="Incident timeline loaded",
    )


@ai_bp.post("/order-plan")
@jwt_required()
def order_plan():
    """Return a RAG-supported production order planning preview."""
    user = current_user()
    result, error, status_code = plan_order(request.get_json(silent=True) or {}, user)
    if error:
        return service_error_response(error, status_code)
    record_event(
        "ai.order_plan",
        "ai",
        entity_type="order_plan",
        user=user,
        department=user.department,
        source="ai",
        metadata={
            "source_count": len(result.get("sources") or []) if isinstance(result, dict) else 0,
        },
        commit=True,
    )
    return success_response(result, message="Order plan generated")


@ai_bp.post("/error-assistant")
@jwt_required()
def error_assistant():
    """Search the error catalog and return causes and fixes for a fault description.

    Request body (JSON):
        query (str, required): Free-text fault description, e.g.
            "Maschine 3 zeigt Fehler E42 und macht Geraeusche."
        limit (int, optional): Maximum number of catalog matches to return
            (1–20, default 5).

    Response ``data`` keys:
        query        — the original query string
        matches      — scored catalog entries (entry, score, reason)
        causes       — deduplicated list of possible-cause strings
        fixes        — deduplicated list of solution strings
        diagnostics  — search metadata and ai_enhanced flag
    """
    user = current_user()
    if not has_dashboard_permission(user, "errors", "view"):
        return error_response("Keine Berechtigung fuer den Fehlerkatalog", 403)

    data = request.get_json(silent=True) or {}
    result, error, status_code = run_error_assistant(data, user)
    if error:
        return service_error_response(error, status_code)
    record_event(
        "ai.error_assistant",
        "ai",
        entity_type="error_assistant",
        user=user,
        department=user.department,
        source="ai",
        metadata={
            "match_count": len(result.get("matches") or []) if isinstance(result, dict) else 0,
            "ai_enhanced": bool(
                (result.get("diagnostics") or {}).get("ai_enhanced")
                if isinstance(result, dict)
                else False
            ),
        },
        commit=True,
    )
    return success_response(result, message="Error assistant result")


@ai_bp.post("/feedback")
@jwt_required()
def feedback():
    """Store user feedback for an AI response."""
    data = request.get_json(silent=True) or {}
    user = current_user()
    feedback_entry, error, status = record_ai_feedback(data, user)
    if error:
        return service_error_response(error, status)
    record_event(
        "ai.feedback",
        "ai",
        entity_type="ai_feedback",
        user=user,
        department=user.department,
        source="ai",
        metadata={"rating": feedback_entry.rating},
    )
    db.session.commit()
    return success_response(
        feedback_entry.to_dict(),
        201,
        "Feedback saved",
    )
