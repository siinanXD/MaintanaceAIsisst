"""Read-only admin retrieval debug view models."""

from __future__ import annotations

from datetime import timedelta

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AIFeedback, ChatMessage

DEFAULT_DEBUG_DAYS = 30
DEFAULT_DEBUG_LIMIT = 30
MAX_DEBUG_LIMIT = 100


def retrieval_debug_items(args=None):
    """Return prompt-safe retrieval debug records for administrators."""
    args = args or {}
    days = _bounded_int(args.get("days"), DEFAULT_DEBUG_DAYS, 1, 365)
    limit = _bounded_int(args.get("limit"), DEFAULT_DEBUG_LIMIT, 1, MAX_DEBUG_LIMIT)
    query_text = str(args.get("q") or "").strip()
    query_type = str(args.get("query_type") or "").strip()
    since = utc_now() - timedelta(days=days)

    query = ChatMessage.query.filter(ChatMessage.created_at >= since)
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(ChatMessage.message.ilike(pattern))
    chats = (
        query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(max(limit * 3, limit))
        .all()
    )
    items = []
    for chat in chats:
        item = _debug_item(chat)
        if query_type and item["query_type"] != query_type:
            continue
        items.append(item)
        if len(items) >= limit:
            break
    return {
        "items": items,
        "pagination": {"limit": limit, "offset": 0, "total": len(items)},
        "filters": {"days": days, "q": query_text, "query_type": query_type},
        "privacy": {
            "shows_raw_prompt": False,
            "shows_chunk_text": False,
            "question_max_chars": 220,
        },
    }


def _debug_item(chat):
    """Return one prompt-safe retrieval debug record."""
    diagnostics = chat.diagnostics()
    event = chat.audit_event
    explainability = event.retrieval_explainability() if event else (
        diagnostics.get("retrieval_explainability") or {}
    )
    query_understanding = explainability.get("query_understanding") or diagnostics.get(
        "query_understanding",
        {},
    )
    feedback = _feedback_for_chat(chat)
    sources = explainability.get("sources") or []
    return {
        "chat_message_id": chat.id,
        "audit_event_id": chat.audit_event_id,
        "user_id": chat.user_id,
        "user_question": _bounded(chat.message, 220),
        "query_type": query_understanding.get("query_type") or "unknown",
        "query_understanding": query_understanding,
        "used_sources": sources,
        "scores": _scores(sources, explainability),
        "explainability": {
            "source_count": explainability.get("source_count", 0),
            "explained_source_count": explainability.get("explained_source_count", 0),
            "averages": explainability.get("averages", {}),
            "quality_status_counts": explainability.get("quality_status_counts", {}),
        },
        "confidence": {
            "score": chat.confidence_score,
            "level": chat.confidence_level,
        },
        "conflicts": explainability.get("conflicts") or {},
        "safety": explainability.get("safety") or {},
        "machine_references": _machine_references(explainability, diagnostics),
        "feedback": feedback,
        "retrieval_duration_ms": explainability.get(
            "retrieval_duration_ms",
            diagnostics.get("retrieval_duration_ms", 0),
        ),
        "created_at": chat.created_at.isoformat(),
    }


def _feedback_for_chat(chat):
    """Return feedback metadata linked to a chat message."""
    filters = [AIFeedback.chat_message_id == chat.id]
    if chat.audit_event_id:
        filters.append(AIFeedback.audit_event_id == chat.audit_event_id)
    feedback_items = AIFeedback.query.filter(db.or_(*filters)).all()
    return {
        "count": len(feedback_items),
        "ratings": [item.rating for item in feedback_items],
        "review_statuses": [item.review_status for item in feedback_items],
    }


def _scores(sources, explainability):
    """Return source score diagnostics."""
    return {
        "source_scores": [
            {
                "type": source.get("type"),
                "id": source.get("id"),
                "chunk_id": source.get("chunk_id"),
                "score": source.get("score"),
                "final_score": (source.get("explainability") or {}).get("final_score"),
            }
            for source in sources[:8]
        ],
        "averages": explainability.get("averages", {}),
    }


def _machine_references(explainability, diagnostics):
    """Return machine-reference signals without source text."""
    sources = explainability.get("sources") or []
    references = []
    for source in sources:
        details = source.get("explainability") or {}
        reasons = details.get("machine_match_reasons") or []
        if reasons:
            references.append(
                {
                    "source_type": source.get("type"),
                    "source_id": source.get("id"),
                    "chunk_id": source.get("chunk_id"),
                    "reasons": reasons,
                    "machine_match": details.get("machine_match"),
                }
            )
    context = diagnostics.get("conversation_context") or {}
    for machine in context.get("machine_names") or []:
        references.append({"source_type": "session", "machine": machine})
    return references[:8]


def _bounded(value, max_chars):
    """Return compact bounded text."""
    text = " ".join(str(value or "").strip().split())
    return text[:max_chars]


def _bounded_int(value, default, minimum, maximum):
    """Return a bounded integer value."""
    try:
        parsed = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)
