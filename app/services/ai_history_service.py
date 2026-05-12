"""Services for AI chat history and admin chat search."""

import json

from app.models import ChatMessage


def save_chat_exchange(user, message, result):
    """Persist one chat exchange with safe response metadata."""
    diagnostics = result.get("diagnostics") or {}
    chat = ChatMessage(
        user_id=user.id,
        message=str(message or "")[:8000],
        response=str(result.get("answer") or "")[:16000],
        response_type=str(result.get("type") or "assistant")[:80],
        diagnostics_json=json.dumps(diagnostics, ensure_ascii=True),
        source_count=len(result.get("sources") or []),
        audit_event_id=diagnostics.get("audit_event_id"),
    )
    return chat


def chat_history_query(user, filters=None, include_all=False):
    """Return a filtered chat history query for a user or all users."""
    filters = filters or {}
    query = ChatMessage.query
    if not include_all:
        query = query.filter(ChatMessage.user_id == user.id)

    user_id = filters.get("user_id")
    if include_all and user_id not in (None, ""):
        try:
            query = query.filter(ChatMessage.user_id == int(user_id))
        except (TypeError, ValueError) as exc:
            raise ValueError("user_id must be an integer") from exc

    q = str(filters.get("q") or "").strip()
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (ChatMessage.message.ilike(pattern)) | (ChatMessage.response.ilike(pattern))
        )

    return query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())


def paginated_chat_history(user, args, include_all=False):
    """Return paginated chat history entries and pagination metadata."""
    query = chat_history_query(user, args, include_all=include_all)
    limit, offset = parse_limit_offset(args)
    total = query.count()
    entries = query.offset(offset).limit(limit).all()
    return {
        "items": [entry.to_dict(include_user=include_all) for entry in entries],
        "pagination": {
            "limit": limit,
            "offset": offset,
            "total": total,
        },
    }


def parse_limit_offset(args, default_limit=30, max_limit=200):
    """Parse common limit and offset query parameters."""
    try:
        limit = min(max(1, int(args.get("limit", default_limit))), max_limit)
        offset = max(0, int(args.get("offset", 0)))
    except (TypeError, ValueError) as exc:
        raise ValueError("limit and offset must be integers") from exc
    return limit, offset
