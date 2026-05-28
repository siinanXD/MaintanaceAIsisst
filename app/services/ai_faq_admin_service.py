"""Admin services for AI FAQ entries, response snippets and suggestions."""

from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AIFAQEntry, AIFeedback, AIResponseSnippet, ChatMessage, KnowledgeGap
from app.services.knowledge_gap_service import normalize_question

FAQ_STATUSES = {"draft", "approved", "archived"}
FAQ_SOURCES = {"manual", "suggested", "gap", "chat"}


def list_faq_entries(args):
    """Return filtered FAQ entries for the admin UI."""
    query = AIFAQEntry.query
    status = str(args.get("status") or "").strip()
    q = str(args.get("q") or "").strip()
    if status:
        query = query.filter(AIFAQEntry.status == status)
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (AIFAQEntry.question.ilike(pattern))
            | (AIFAQEntry.answer.ilike(pattern))
            | (AIFAQEntry.keywords.ilike(pattern))
            | (AIFAQEntry.machine.ilike(pattern))
        )
    return query.order_by(AIFAQEntry.updated_at.desc(), AIFAQEntry.id.desc())


def create_faq_entry(data, user):
    """Create a draft or approved FAQ entry."""
    try:
        payload = normalize_faq_payload(data, partial=False)
    except ValueError as exc:
        return None, {"message": str(exc)}, 400
    entry = AIFAQEntry(
        question=payload["question"],
        answer=payload["answer"],
        category=payload["category"],
        keywords=payload["keywords"],
        machine=payload["machine"],
        department=payload["department"],
        status=payload["status"],
        source=payload["source"],
        source_ref_id=payload["source_ref_id"],
        created_by=getattr(user, "id", None),
        approved_by=getattr(user, "id", None) if payload["status"] == "approved" else None,
        approved_at=utc_now() if payload["status"] == "approved" else None,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(entry)
    db.session.flush()
    if entry.status == "approved":
        mark_faq_entry_knowledge_stale(entry)
    db.session.commit()
    return entry.to_dict(), None, 201


def update_faq_entry(entry, data):
    """Update an existing FAQ entry and mark its knowledge document stale."""
    try:
        payload = normalize_faq_payload(data, partial=True)
    except ValueError as exc:
        return None, {"message": str(exc)}, 400
    for field, value in payload.items():
        setattr(entry, field, value)
    entry.updated_at = utc_now()
    if entry.status == "approved":
        mark_faq_entry_knowledge_stale(entry)
    db.session.commit()
    return entry.to_dict(), None, 200


def approve_faq_entry(entry, user):
    """Approve an FAQ entry and make it available for RAG indexing."""
    entry.status = "approved"
    entry.approved_by = getattr(user, "id", None)
    entry.approved_at = utc_now()
    entry.updated_at = utc_now()
    mark_faq_entry_knowledge_stale(entry)
    db.session.commit()
    return entry.to_dict(), None, 200


def list_response_snippets(args):
    """Return filtered reusable response snippets."""
    query = AIResponseSnippet.query
    category = str(args.get("category") or "").strip()
    if category:
        query = query.filter(AIResponseSnippet.category == category)
    return query.order_by(AIResponseSnippet.category.asc(), AIResponseSnippet.key.asc())


def create_response_snippet(data, user):
    """Create a reusable response snippet."""
    try:
        payload = normalize_response_snippet_payload(data)
    except ValueError as exc:
        return None, {"message": str(exc)}, 400
    snippet = AIResponseSnippet(
        key=payload["key"],
        title=payload["title"],
        body=payload["body"],
        category=payload["category"],
        is_active=payload["is_active"],
        created_by=getattr(user, "id", None),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(snippet)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"message": "Snippet-Key ist bereits vorhanden"}, 409
    return snippet.to_dict(), None, 201


def faq_suggestions(args):
    """Return frequent questions, low-quality answers and knowledge-gap suggestions."""
    days = _bounded_int(args.get("days"), 30, 1, 90)
    limit = _bounded_int(args.get("limit"), 10, 1, 50)
    since = datetime.now(UTC) - timedelta(days=days)
    chats = ChatMessage.query.filter(ChatMessage.created_at >= since).all()
    feedback = AIFeedback.query.filter(AIFeedback.created_at >= since).all()
    gaps = (
        KnowledgeGap.query.filter(KnowledgeGap.last_seen_at >= since)
        .order_by(KnowledgeGap.occurrence_count.desc(), KnowledgeGap.last_seen_at.desc())
        .limit(limit)
        .all()
    )
    return {
        "window_days": days,
        "frequent_questions": _frequent_questions(chats, limit),
        "frequent_answers": _frequent_answers(chats, limit),
        "questions_without_sources": _questions_without_sources(chats, limit),
        "negative_feedback": _negative_feedback(feedback, limit),
        "knowledge_gaps": [gap.to_dict() for gap in gaps],
    }


def mark_faq_entry_knowledge_stale(entry):
    """Create or mark the FAQ knowledge document as stale after a change."""
    from app.services.knowledge_registry_service import mark_faq_entry_knowledge_stale

    mark_faq_entry_knowledge_stale(entry)


def normalize_faq_payload(data, partial=False):
    """Validate and normalize FAQ entry input."""
    payload = data if isinstance(data, dict) else {}
    result = {}
    for field, max_length in (
        ("question", 4000),
        ("answer", 8000),
        ("category", 80),
        ("keywords", 1000),
        ("machine", 160),
        ("department", 120),
        ("source", 40),
    ):
        if field in payload or not partial:
            value = str(payload.get(field) or "").strip()[:max_length]
            if field in {"question", "answer"} and not value:
                raise ValueError(f"{field} is required")
            result[field] = value
    result.setdefault("category", "wartung")
    result.setdefault("source", "manual")
    status = str(payload.get("status") or ("draft" if not partial else "")).strip().lower()
    if status:
        if status not in FAQ_STATUSES:
            raise ValueError("status must be draft, approved or archived")
        result["status"] = status
    source = result.get("source")
    if source and source not in FAQ_SOURCES:
        raise ValueError("source must be manual, suggested, gap or chat")
    if "source_ref_id" in payload or not partial:
        result["source_ref_id"] = _optional_int(payload.get("source_ref_id"))
    return result


def normalize_response_snippet_payload(data):
    """Validate and normalize response snippet input."""
    payload = data if isinstance(data, dict) else {}
    key = str(payload.get("key") or "").strip().lower()[:80]
    title = str(payload.get("title") or "").strip()[:160]
    body = str(payload.get("body") or "").strip()[:8000]
    if not key:
        raise ValueError("key is required")
    if not title:
        raise ValueError("title is required")
    if not body:
        raise ValueError("body is required")
    return {
        "key": key,
        "title": title,
        "body": body,
        "category": str(payload.get("category") or "fallback").strip()[:80],
        "is_active": bool(payload.get("is_active", True)),
    }


def _frequent_questions(chats, limit):
    """Return frequent normalized questions from chat history."""
    grouped = {}
    for chat in chats:
        key = normalize_question(chat.message)
        if not key:
            continue
        item = grouped.setdefault(
            key,
            {"question": chat.message[:500], "count": 0, "latest_at": chat.created_at},
        )
        item["count"] += 1
        if chat.created_at > item["latest_at"]:
            item["latest_at"] = chat.created_at
            item["question"] = chat.message[:500]
    rows = [
        {
            "question": item["question"],
            "count": item["count"],
            "latest_at": item["latest_at"].isoformat(),
        }
        for item in grouped.values()
    ]
    return sorted(rows, key=lambda item: (item["count"], item["latest_at"]), reverse=True)[:limit]


def _frequent_answers(chats, limit):
    """Return frequent bounded answers from chat history."""
    counter = Counter(_bounded(chat.response, 500) for chat in chats if chat.response)
    return [{"answer": answer, "count": count} for answer, count in counter.most_common(limit)]


def _questions_without_sources(chats, limit):
    """Return recent questions with no attached sources."""
    rows = [
        {
            "chat_message_id": chat.id,
            "question": _bounded(chat.message, 500),
            "response_type": chat.response_type,
            "created_at": chat.created_at.isoformat(),
        }
        for chat in chats
        if int(chat.source_count or 0) == 0
    ]
    return sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit]


def _negative_feedback(feedback_entries, limit):
    """Return negative feedback rows without exposing more than stored feedback text."""
    rows = [
        {
            "feedback_id": item.id,
            "chat_message_id": item.chat_message_id,
            "audit_event_id": item.audit_event_id,
            "rating": item.rating,
            "prompt": _bounded(item.prompt, 500),
            "comment": _bounded(item.comment, 500),
            "created_at": item.created_at.isoformat(),
        }
        for item in feedback_entries
        if item.rating in {"not_helpful", "partially_helpful"}
    ]
    return sorted(rows, key=lambda item: item["created_at"], reverse=True)[:limit]


def _bounded(value, max_length):
    """Return text bounded to a maximum length."""
    return str(value or "").strip()[:max_length]


def _bounded_int(value, default, minimum, maximum):
    """Return a bounded integer."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _optional_int(value):
    """Return an optional integer from user input."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("source_ref_id must be an integer") from exc
