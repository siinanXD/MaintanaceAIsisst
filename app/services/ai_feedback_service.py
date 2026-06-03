"""Services for collecting AI answer feedback."""

import json

from app.extensions import db
from app.models import AIAuditEvent, AIFeedback, ChatMessage
from app.services.langfuse_eval_score_service import submit_user_feedback_score

ALLOWED_FEEDBACK_RATINGS = {"helpful", "not_helpful", "partially_helpful"}
MAX_FEEDBACK_SOURCES = 12


def record_ai_feedback(data, user):
    """Validate and stage user feedback for one AI answer."""
    data = data or {}
    rating = str(data.get("rating") or "").strip()
    if rating not in ALLOWED_FEEDBACK_RATINGS:
        return None, {"error": _rating_error()}, 400

    chat_message, error, status = _chat_message_for_feedback(data, user)
    if error:
        return None, error, status

    try:
        sources = normalize_feedback_sources(data.get("sources", []))
        audit_event_id = _audit_event_id_for_feedback(data, user, chat_message)
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    prompt = str(data.get("prompt") or "").strip()
    response = str(data.get("response") or "").strip()
    response_type = str(data.get("response_type") or "").strip()
    if chat_message:
        prompt = prompt or chat_message.message
        response = response or chat_message.response
        response_type = response_type or chat_message.response_type

    if not prompt or not response:
        return None, {"error": "prompt and response are required"}, 400

    feedback_entry = AIFeedback(
        user_id=user.id,
        chat_message_id=chat_message.id if chat_message else None,
        audit_event_id=audit_event_id,
        prompt=prompt[:4000],
        response=response[:8000],
        response_type=response_type[:80],
        rating=rating,
        comment=str(data.get("comment") or "").strip()[:1000],
        sources_json=json.dumps(sources, ensure_ascii=True),
        source_count=len(sources),
        review_status="open",
    )
    db.session.add(feedback_entry)
    db.session.flush()
    submit_user_feedback_score(chat_message, feedback_entry)
    return feedback_entry, None, 201


def normalize_feedback_sources(sources):
    """Return sanitized source metadata for feedback storage."""
    if sources in (None, ""):
        return []
    if not isinstance(sources, list):
        raise ValueError("sources must be a list")

    return [_normalize_feedback_source(source) for source in sources[:MAX_FEEDBACK_SOURCES]]


def _normalize_feedback_source(source):
    """Return one sanitized source dictionary."""
    if not isinstance(source, dict):
        raise ValueError("sources must contain objects")
    return {
        "type": _source_string(source.get("type"), "knowledge", 80),
        "id": _optional_int(source.get("id"), "sources[].id"),
        "chunk_id": _optional_int(source.get("chunk_id"), "sources[].chunk_id"),
        "title": _source_string(source.get("title"), "Wissensquelle", 220),
        "module": _source_string(source.get("module"), "", 80),
        "url": _source_string(source.get("url"), "", 500),
        "reason": _source_string(source.get("reason"), "", 500),
        "score": _optional_float(source.get("score"), "sources[].score"),
    }


def _chat_message_for_feedback(data, user):
    """Return a user's chat message referenced by feedback payload."""
    chat_message_id = data.get("chat_message_id")
    if chat_message_id in (None, ""):
        return None, None, None
    try:
        parsed_id = int(chat_message_id)
    except (TypeError, ValueError):
        return None, {"error": "chat_message_id must be an integer"}, 400

    chat_message = db.session.get(ChatMessage, parsed_id)
    if not chat_message or chat_message.user_id != user.id:
        return None, {"error": "chat message not found"}, 404
    return chat_message, None, None


def _audit_event_id_for_feedback(data, user, chat_message):
    """Return a validated audit event id for feedback linkage."""
    if chat_message and chat_message.audit_event_id:
        return chat_message.audit_event_id

    audit_event_id = data.get("audit_event_id")
    if audit_event_id in (None, ""):
        return None
    try:
        parsed_id = int(audit_event_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("audit_event_id must be an integer") from exc

    event = db.session.get(AIAuditEvent, parsed_id)
    if not event or event.user_id not in (None, user.id):
        raise ValueError("audit_event_id does not reference a visible AI event")
    return parsed_id


def _optional_int(value, field_name):
    """Return an optional integer source field."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _optional_float(value, field_name):
    """Return an optional floating-point source score."""
    if value in (None, ""):
        return None
    try:
        return round(float(value), 4)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a number") from exc


def _source_string(value, default, max_length):
    """Return a bounded source metadata string."""
    cleaned = str(value or default or "").strip()
    return cleaned[:max_length]


def _rating_error():
    """Return the public validation message for unsupported ratings."""
    return "rating must be helpful, not_helpful or partially_helpful"
