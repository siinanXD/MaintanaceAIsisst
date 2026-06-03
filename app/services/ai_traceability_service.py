"""Answer traceability storage and read models."""

from __future__ import annotations

import json
import logging
from uuid import uuid4

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import AIAnswerTrace, Role
from app.services.langfuse_eval_score_service import submit_automatic_eval_scores
from app.services.langfuse_service import link_langfuse_answer_trace

logger = logging.getLogger(__name__)

SOURCE_TRACE_FIELDS = {
    "type",
    "source_type",
    "source_kind",
    "source_id",
    "source_record_id",
    "id",
    "title",
    "module",
    "url",
    "machine",
    "machine_id",
    "error_code",
    "document_id",
    "chunk_id",
    "chunk_index",
    "quality_status",
    "role_visibility",
    "employee_access_level",
    "score",
    "relevance",
    "normalized_score",
    "created_at",
}
FORBIDDEN_TRACE_KEYS = {
    "answer",
    "content",
    "description",
    "details",
    "internal_note",
    "internal_notes",
    "message",
    "notes",
    "private_notes",
    "prompt",
    "raw",
    "relative_path",
    "response",
    "solution",
    "summary",
    "text",
}


def create_answer_trace(chat_message, result):
    """Persist one answer trace and attach its ids to the mutable result payload."""
    if chat_message is None or not isinstance(result, dict):
        return None
    diagnostics = result.get("diagnostics") or {}
    confidence = result.get("confidence") or diagnostics.get("confidence") or {}
    sources = _safe_sources(result.get("sources") or [])
    chunks = _safe_chunks(sources)
    trace = AIAnswerTrace(
        answer_id=_new_answer_id(),
        user_id=chat_message.user_id,
        chat_message_id=chat_message.id,
        audit_event_id=chat_message.audit_event_id,
        workflow=str(diagnostics.get("workflow") or result.get("type") or "assistant")[:80],
        provider=str(diagnostics.get("provider") or result.get("provider") or "")[:80],
        model=str(diagnostics.get("model") or "")[:120],
        model_tier=str(diagnostics.get("model_tier") or "")[:40],
        input_tokens=_int_value(diagnostics.get("input_tokens")),
        output_tokens=_int_value(diagnostics.get("output_tokens")),
        cached_tokens=_int_value(diagnostics.get("cached_tokens")),
        total_tokens=_int_value(diagnostics.get("total_tokens")),
        estimated_cost_usd=_float_value(diagnostics.get("estimated_cost_usd")),
        confidence_score=_optional_int(
            diagnostics.get("confidence_score") or confidence.get("score"),
        ),
        confidence_level=str(
            diagnostics.get("confidence_level") or confidence.get("level") or "",
        )[:40],
        source_count=len(sources),
        chunk_count=len(chunks),
        sources_json=json.dumps(sources, ensure_ascii=True),
        chunks_json=json.dumps(chunks, ensure_ascii=True),
    )
    db.session.add(trace)
    try:
        db.session.flush()
        _attach_trace_ids(chat_message, result, trace)
        db.session.commit()
        link_langfuse_answer_trace(diagnostics, chat_message, trace)
        eval_result = dict(result)
        eval_result["question"] = chat_message.message
        submit_automatic_eval_scores(diagnostics, eval_result)
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception(
            "ai_answer_trace_save_failed chat_message_id=%s audit_event_id=%s",
            chat_message.id,
            chat_message.audit_event_id,
        )
        return None
    return trace


def answer_trace_for_user(answer_id, user):
    """Return one answer trace if the user is allowed to inspect evidence."""
    if not _can_view_trace(user):
        return None, {"message": "Forbidden"}, 403
    trace = AIAnswerTrace.query.filter_by(answer_id=str(answer_id or "").strip()).first()
    if trace is None:
        return None, {"message": "Answer trace not found"}, 404
    return trace.to_dict(), None, 200


def answer_trace_for_chat_message(chat_message_id, user):
    """Return one answer trace by chat message id for privileged users."""
    if not _can_view_trace(user):
        return None, {"message": "Forbidden"}, 403
    try:
        message_id = int(chat_message_id)
    except (TypeError, ValueError):
        return None, {"message": "chat_message_id must be an integer"}, 400
    trace = AIAnswerTrace.query.filter_by(chat_message_id=message_id).first()
    if trace is None:
        return None, {"message": "Answer trace not found"}, 404
    return trace.to_dict(), None, 200


def _safe_sources(sources):
    """Return prompt-safe source trace entries."""
    safe_sources = []
    for index, source in enumerate(sources):
        if not isinstance(source, dict):
            continue
        entry = {
            key: _safe_scalar(value)
            for key, value in source.items()
            if key in SOURCE_TRACE_FIELDS and key not in FORBIDDEN_TRACE_KEYS
        }
        entry["trace_index"] = index
        entry["similarity_score"] = _similarity_score(source)
        score_debug = (
            source.get("score_debug") if isinstance(source.get("score_debug"), dict) else {}
        )
        if score_debug:
            entry["score_components"] = _safe_score_components(score_debug.get("signals"))
        explainability = (
            source.get("explainability")
            if isinstance(source.get("explainability"), dict)
            else {}
        )
        if explainability:
            entry["explainability"] = _safe_score_components(explainability)
        safe_sources.append(_drop_empty_values(entry))
    return safe_sources


def _safe_chunks(sources):
    """Return chunk-level trace entries from safe source references."""
    chunks = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        chunk_id = source.get("chunk_id")
        if chunk_id in (None, "") and source.get("type") != "knowledge":
            continue
        chunks.append(
            _drop_empty_values(
                {
                    "source_trace_index": source.get("trace_index"),
                    "source_id": source.get("source_id") or source.get("id"),
                    "document_id": source.get("document_id") or source.get("source_record_id"),
                    "chunk_id": chunk_id or source.get("id"),
                    "chunk_index": source.get("chunk_index"),
                    "title": source.get("title"),
                    "source_type": source.get("source_type"),
                    "quality_status": source.get("quality_status"),
                    "similarity_score": source.get("similarity_score"),
                    "score": source.get("score"),
                    "relevance": source.get("relevance"),
                    "normalized_score": source.get("normalized_score"),
                },
            ),
        )
    return chunks


def _safe_score_components(values):
    """Return numeric score components only."""
    if not isinstance(values, dict):
        return {}
    return {
        key: _safe_scalar(value)
        for key, value in values.items()
        if key not in FORBIDDEN_TRACE_KEYS and isinstance(value, int | float | bool | str)
    }


def _similarity_score(source):
    """Return the best available similarity score from a source card."""
    candidates = [
        source.get("similarity"),
        source.get("semantic_similarity"),
        source.get("normalized_score"),
        source.get("relevance"),
        source.get("score"),
    ]
    explainability = (
        source.get("explainability")
        if isinstance(source.get("explainability"), dict)
        else {}
    )
    candidates.append(explainability.get("semantic_similarity"))
    for value in candidates:
        parsed = _optional_float(value)
        if parsed is not None:
            return parsed
    return None


def _can_view_trace(user):
    """Return whether a user may inspect answer trace evidence."""
    return bool(
        user
        and (
            getattr(user, "is_admin", False)
            or getattr(user, "role", None) in {Role.IT, Role.MASTER_ADMIN}
        )
    )


def _new_answer_id():
    """Return a public answer id for trace lookups."""
    return f"ans_{uuid4().hex}"


def _attach_trace_ids(chat_message, result, trace):
    """Attach trace ids to the response payload and stored chat diagnostics."""
    diagnostics = result.setdefault("diagnostics", {})
    result["answer_id"] = trace.answer_id
    result["answer_trace_id"] = trace.id
    diagnostics["answer_id"] = trace.answer_id
    diagnostics["answer_trace_id"] = trace.id
    stored_diagnostics = {}
    try:
        stored_diagnostics = json.loads(chat_message.diagnostics_json or "{}")
    except (TypeError, json.JSONDecodeError):
        stored_diagnostics = {}
    if not isinstance(stored_diagnostics, dict):
        stored_diagnostics = {}
    stored_diagnostics["answer_id"] = trace.answer_id
    stored_diagnostics["answer_trace_id"] = trace.id
    chat_message.diagnostics_json = json.dumps(stored_diagnostics, ensure_ascii=True)


def _safe_scalar(value):
    """Return a JSON-safe scalar or compact list/dict of scalars."""
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, int | float | bool) or value is None:
        return value
    if isinstance(value, list | tuple | set):
        return [_safe_scalar(item) for item in list(value)[:20]]
    if isinstance(value, dict):
        return {
            str(key)[:80]: _safe_scalar(item)
            for key, item in list(value.items())[:20]
            if str(key) not in FORBIDDEN_TRACE_KEYS
        }
    return str(value)[:200]


def _drop_empty_values(payload):
    """Return a dictionary without empty values."""
    return {
        key: value
        for key, value in payload.items()
        if value not in (None, "", [], {})
    }


def _int_value(value):
    """Return a safe integer value."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value):
    """Return a safe float value."""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _optional_float(value):
    """Return an optional rounded float value."""
    if value in (None, ""):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None
