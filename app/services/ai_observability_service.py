"""Admin-facing AI monitoring and observability read models."""

from __future__ import annotations

from collections import Counter
from datetime import timedelta
from math import ceil

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AIAuditEvent, AIFeedback, ChatMessage, KnowledgeDocument
from app.services.ai_prompting import text_system_prompt
from app.services.retrieval_telemetry_service import retrieval_quality_analytics

DEFAULT_OBSERVABILITY_DAYS = 30
DEFAULT_OBSERVABILITY_LIMIT = 10
MAX_OBSERVABILITY_LIMIT = 50
LOW_SIMILARITY_THRESHOLD = 0.35
LOW_SCORE_THRESHOLD = 35.0
NEGATIVE_RATINGS = {"not_helpful"}


def ai_observability_dashboard(args=None):
    """Return an admin-facing AI monitoring dashboard from existing telemetry."""
    args = args or {}
    days = _bounded_int(args.get("days"), DEFAULT_OBSERVABILITY_DAYS, 1, 365)
    limit = _bounded_int(args.get("limit"), DEFAULT_OBSERVABILITY_LIMIT, 1, MAX_OBSERVABILITY_LIMIT)
    chat_message_id = _optional_int(args.get("chat_message_id"))
    since = utc_now() - timedelta(days=days)
    events = _audit_events_since(since)
    chats = _chat_messages_since(since)
    feedback_entries = _feedback_since(since)
    telemetry = retrieval_quality_analytics(days=days, limit=limit)
    return {
        "window_days": days,
        "metrics": _metrics(events, chats, feedback_entries, telemetry),
        "retrieval_monitoring": _retrieval_monitoring(events, feedback_entries, limit),
        "ai_logs": _ai_logs(chats, limit),
        "quality_metrics": _quality_metrics(events, telemetry),
        "debug_tools": _debug_tools(chats, chat_message_id),
        "privacy": {
            "source": "chat_history_audit_metadata_retrieval_telemetry",
            "raw_questions_visible_to_admins": True,
            "raw_answers_bounded": True,
            "raw_chunk_text_visible": False,
        },
    }


def _audit_events_since(since):
    """Return audit events in the observability window."""
    return (
        AIAuditEvent.query.filter(AIAuditEvent.created_at >= since)
        .order_by(AIAuditEvent.created_at.desc(), AIAuditEvent.id.desc())
        .all()
    )


def _chat_messages_since(since):
    """Return chat messages in the observability window."""
    return (
        ChatMessage.query.filter(ChatMessage.created_at >= since)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .all()
    )


def _feedback_since(since):
    """Return feedback entries in the observability window."""
    return (
        AIFeedback.query.filter(AIFeedback.created_at >= since)
        .order_by(AIFeedback.created_at.desc(), AIFeedback.id.desc())
        .all()
    )


def _metrics(events, chats, feedback_entries, telemetry):
    """Return top-level AI operations metrics."""
    event_count = len(events)
    response_times = [event.latency_ms for event in events if event.latency_ms]
    retrieval_times = [_retrieval_duration_ms(event) for event in events]
    retrieval_times = [value for value in retrieval_times if value is not None]
    empty_retrieval_count = sum(1 for chat in chats if _is_empty_retrieval(chat))
    hallucination_warning_count = sum(1 for chat in chats if _has_hallucination_warning(chat))
    error_count = sum(1 for event in events if _is_error_event(event))
    source_distribution = _source_distribution(events)
    return {
        "event_count": event_count,
        "chat_count": len(chats),
        "average_response_ms": _average(response_times),
        "p95_response_ms": _percentile(response_times, 0.95),
        "average_retrieval_ms": _average(retrieval_times),
        "p95_retrieval_ms": _percentile(retrieval_times, 0.95),
        "total_tokens": sum(event.total_tokens or 0 for event in events),
        "input_tokens": sum(event.input_tokens or 0 for event in events),
        "output_tokens": sum(event.output_tokens or 0 for event in events),
        "error_count": error_count,
        "error_rate": _rate(error_count, event_count),
        "empty_retrieval_count": empty_retrieval_count,
        "empty_retrieval_rate": _rate(empty_retrieval_count, len(chats)),
        "hallucination_warning_count": hallucination_warning_count,
        "fallback_rate": _rate(sum(1 for event in events if event.fallback_used), event_count),
        "negative_feedback_count": sum(
            1 for feedback in feedback_entries if feedback.rating in NEGATIVE_RATINGS
        ),
        "top_questions": _top_questions(chats),
        "source_distribution": source_distribution,
        "source_distribution_rows": _counter_rows(source_distribution),
        "telemetry_status": (telemetry.get("retrieval_slo") or {}).get("status", "ok"),
    }


def _retrieval_monitoring(events, feedback_entries, limit):
    """Return retrieval hit, score, chunk, and document usage details."""
    source_rows = _source_rows(events)
    chunk_counter = Counter()
    document_counter = Counter()
    for row in source_rows:
        if row.get("chunk_id") is not None:
            chunk_counter[(row["source_id"], row["chunk_id"], row["source_type"])] += 1
        if row.get("source_id") is not None:
            document_counter[(row["source_type"], row["source_id"])] += 1
    negative_feedback_ids = {
        feedback.audit_event_id
        for feedback in feedback_entries
        if feedback.rating in NEGATIVE_RATINGS
    }
    return {
        "top_hits": _top_hit_rows(source_rows, limit),
        "poor_hits": _poor_hit_rows(source_rows, negative_feedback_ids, limit),
        "score_summary": _score_summary(source_rows),
        "chunk_usage": _chunk_usage_rows(chunk_counter, limit),
        "frequently_used_documents": _document_usage_rows(document_counter, limit),
    }


def _ai_logs(chats, limit):
    """Return bounded AI request logs for admin diagnosis."""
    return [_ai_log_row(chat) for chat in chats[:limit]]


def _ai_log_row(chat):
    """Return one bounded AI log row."""
    diagnostics = chat.diagnostics()
    event = chat.audit_event
    explainability = (
        event.retrieval_explainability()
        if event
        else (diagnostics.get("retrieval_explainability") or {})
    )
    sources = explainability.get("sources") if isinstance(explainability, dict) else []
    quality_warnings = diagnostics.get("quality_warnings") or []
    return {
        "chat_message_id": chat.id,
        "audit_event_id": chat.audit_event_id,
        "created_at": chat.created_at.isoformat(),
        "user_question": _bounded(chat.message, 300),
        "answer_preview": _bounded(chat.response, 420),
        "response_type": chat.response_type,
        "answer_quality": _answer_quality(chat, quality_warnings),
        "confidence": {
            "score": chat.confidence_score,
            "level": chat.confidence_level,
        },
        "source_count": chat.source_count,
        "sources": [_source_reference(source) for source in (sources or [])[:8]],
        "error": event.error_category if event else "",
        "status": event.status if event else diagnostics.get("status", ""),
        "response_duration_ms": event.latency_ms if event else 0,
        "retrieval_duration_ms": _retrieval_duration_ms(event) if event else 0,
        "quality_warnings": quality_warnings,
    }


def _quality_metrics(events, telemetry):
    """Return retrieval quality metrics aligned with golden evaluation when available."""
    total_events = len(events)
    hit_count = sum(1 for event in events if int(event.source_count or 0) > 0)
    similarity_values = _similarity_values(events)
    evaluation = telemetry.get("retrieval_evaluation_history") or {}
    latest_eval = evaluation.get("latest") or {}
    return {
        "recall_at_k": latest_eval.get("recall_at_k"),
        "mrr": latest_eval.get("mrr"),
        "ndcg_at_k": latest_eval.get("ndcg_at_k"),
        "retrieval_hit_rate": _rate(hit_count, total_events),
        "empty_retrieval_rate": _rate(total_events - hit_count, total_events),
        "average_similarity_score": _average(similarity_values),
        "low_similarity_count": sum(
            1 for value in similarity_values if value <= LOW_SIMILARITY_THRESHOLD
        ),
        "evaluated_query_count": latest_eval.get("query_count", 0),
    }


def _debug_tools(chats, chat_message_id):
    """Return selected request details for step-by-step debugging."""
    selected = _selected_chat(chats, chat_message_id)
    if not selected:
        return {
            "selected_chat_message_id": None,
            "request_analysis": None,
            "prompt_blueprint": None,
            "available_requests": [],
        }
    return {
        "selected_chat_message_id": selected.id,
        "request_analysis": _request_analysis(selected),
        "prompt_blueprint": _prompt_blueprint(selected),
        "available_requests": [
            {
                "chat_message_id": chat.id,
                "created_at": chat.created_at.isoformat(),
                "question": _bounded(chat.message, 160),
                "confidence_level": chat.confidence_level,
                "source_count": chat.source_count,
            }
            for chat in chats[:20]
        ],
    }


def _selected_chat(chats, chat_message_id):
    """Return the requested chat or the newest available chat."""
    if not chats:
        return None
    if chat_message_id is None:
        return chats[0]
    for chat in chats:
        if chat.id == chat_message_id:
            return chat
    return chats[0]


def _request_analysis(chat):
    """Return one request analysis with retrieval, confidence, and safety signals."""
    diagnostics = chat.diagnostics()
    event = chat.audit_event
    explainability = (
        event.retrieval_explainability()
        if event
        else (diagnostics.get("retrieval_explainability") or {})
    )
    context_builder = (
        explainability.get("context_builder") if isinstance(explainability, dict) else {}
    )
    query_understanding = (
        (explainability.get("query_understanding") if isinstance(explainability, dict) else {})
        or diagnostics.get("query_understanding")
        or {}
    )
    sources = explainability.get("sources") if isinstance(explainability, dict) else []
    return {
        "question": _bounded(chat.message, 500),
        "answer_preview": _bounded(chat.response, 700),
        "query_understanding": query_understanding,
        "retrieval": {
            "source_count": chat.source_count,
            "retrieval_duration_ms": _retrieval_duration_ms(event) if event else 0,
            "sources": [_source_reference(source) for source in (sources or [])[:10]],
            "score_summary": _score_summary(_source_rows([event]) if event else []),
        },
        "context_builder": {
            "stats": (context_builder or {}).get("stats", {}),
            "sections": _context_sections(context_builder),
            "explainability": (context_builder or {}).get("explainability", {}),
        },
        "confidence": {
            "score": chat.confidence_score,
            "level": chat.confidence_level,
        },
        "quality_warnings": diagnostics.get("quality_warnings") or [],
        "safety": (explainability or {}).get("safety", {}),
        "post_generation_safety": (explainability or {}).get("post_generation_safety", {}),
    }


def _prompt_blueprint(chat):
    """Return a bounded prompt blueprint without raw chunk text."""
    diagnostics = chat.diagnostics()
    event = chat.audit_event
    explainability = (
        event.retrieval_explainability()
        if event
        else (diagnostics.get("retrieval_explainability") or {})
    )
    context_builder = (
        explainability.get("context_builder") if isinstance(explainability, dict) else {}
    )
    sources = explainability.get("sources") if isinstance(explainability, dict) else []
    return {
        "system_prompt": text_system_prompt(),
        "user_question": _bounded(chat.message, 1000),
        "context_visibility": "source references and context-builder sections only",
        "context_sections": _context_sections(context_builder),
        "source_references": [_source_reference(source) for source in (sources or [])[:10]],
        "prompt_preview": (
            "Kontext: "
            + _bounded(_context_preview(context_builder, sources), 1200)
            + "\n\nFrage: "
            + _bounded(chat.message, 500)
        ),
    }


def _context_sections(context_builder):
    """Return context-builder sections without full context text."""
    if not isinstance(context_builder, dict):
        return []
    sections = context_builder.get("sections") or []
    return [
        {
            "label": _bounded(section.get("label") or section.get("type"), 120),
            "source_count": section.get("source_count"),
            "used_chars": section.get("used_chars"),
            "truncated": bool(section.get("truncated")),
        }
        for section in sections[:12]
        if isinstance(section, dict)
    ]


def _context_preview(context_builder, sources):
    """Return a compact context preview based on section and source metadata."""
    sections = _context_sections(context_builder)
    section_labels = [section["label"] for section in sections if section.get("label")]
    source_labels = [_source_label(source) for source in (sources or [])[:8]]
    parts = []
    if section_labels:
        parts.append("Sections: " + ", ".join(section_labels))
    if source_labels:
        parts.append("Sources: " + ", ".join(source_labels))
    return " | ".join(parts) if parts else "Keine gespeicherten Kontext-Metadaten."


def _top_questions(chats):
    """Return frequent bounded questions grouped by normalized text."""
    grouped = {}
    for chat in chats:
        key = _normalized_question(chat.message)
        item = grouped.setdefault(
            key,
            {
                "question": _bounded(chat.message, 220),
                "count": 0,
                "latest_at": chat.created_at,
                "confidence_total": 0,
                "confidence_count": 0,
            },
        )
        item["count"] += 1
        if chat.created_at > item["latest_at"]:
            item["latest_at"] = chat.created_at
            item["question"] = _bounded(chat.message, 220)
        if chat.confidence_score is not None:
            item["confidence_total"] += chat.confidence_score
            item["confidence_count"] += 1
    rows = []
    for item in grouped.values():
        rows.append(
            {
                "question": item["question"],
                "count": item["count"],
                "latest_at": item["latest_at"].isoformat(),
                "average_confidence": _average_from_total(
                    item["confidence_total"],
                    item["confidence_count"],
                ),
            }
        )
    return sorted(rows, key=lambda row: (row["count"], row["latest_at"]), reverse=True)[:10]


def _source_rows(events):
    """Return flattened source rows from audit events."""
    rows = []
    for event in events:
        if not event:
            continue
        explainability = event.retrieval_explainability()
        sources = explainability.get("sources") if isinstance(explainability, dict) else []
        for rank, source in enumerate(sources or [], start=1):
            score = _source_score(source)
            similarity = _source_similarity(source)
            rows.append(
                {
                    "audit_event_id": event.id,
                    "workflow": event.workflow,
                    "rank": rank,
                    "source_type": source.get("type") or "knowledge",
                    "source_id": _optional_int(source.get("id")),
                    "chunk_id": _optional_int(source.get("chunk_id")),
                    "section_title": _bounded(
                        source.get("section_title") or source.get("source_section"),
                        160,
                    ),
                    "score": score,
                    "similarity": similarity,
                    "quality_status": _source_quality(source),
                    "created_at": event.created_at.isoformat(),
                }
            )
    return rows


def _source_distribution(events):
    """Return source usage counts by source type."""
    counter = Counter()
    for event in events:
        for row in _source_rows([event]):
            counter[row["source_type"]] += 1
    return dict(counter)


def _top_hit_rows(source_rows, limit):
    """Return top retrieval hits by rank and score."""
    rows = sorted(
        source_rows,
        key=lambda row: (
            0 if row["rank"] == 1 else -row["rank"],
            row["score"] if row["score"] is not None else -1,
            row["similarity"] if row["similarity"] is not None else -1,
        ),
        reverse=True,
    )
    return [_source_hit_payload(row) for row in rows[:limit]]


def _poor_hit_rows(source_rows, negative_feedback_ids, limit):
    """Return low-quality retrieval hits for monitoring."""
    poor_rows = [
        row
        for row in source_rows
        if row["audit_event_id"] in negative_feedback_ids
        or (row["score"] is not None and row["score"] <= LOW_SCORE_THRESHOLD)
        or (row["similarity"] is not None and row["similarity"] <= LOW_SIMILARITY_THRESHOLD)
    ]
    poor_rows.sort(
        key=lambda row: (
            row["audit_event_id"] in negative_feedback_ids,
            -(row["score"] if row["score"] is not None else 1000),
            -(row["similarity"] if row["similarity"] is not None else 1),
        ),
        reverse=True,
    )
    return [_source_hit_payload(row) for row in poor_rows[:limit]]


def _source_hit_payload(row):
    """Return one retrieval-hit payload."""
    payload = dict(row)
    payload["label"] = _source_row_label(row)
    return payload


def _score_summary(source_rows):
    """Return aggregate retrieval score metrics."""
    scores = [row["score"] for row in source_rows if row.get("score") is not None]
    similarities = [row["similarity"] for row in source_rows if row.get("similarity") is not None]
    return {
        "source_count": len(source_rows),
        "average_score": _average(scores),
        "average_similarity": _average(similarities),
        "low_score_count": sum(1 for score in scores if score <= LOW_SCORE_THRESHOLD),
        "low_similarity_count": sum(
            1 for similarity in similarities if similarity <= LOW_SIMILARITY_THRESHOLD
        ),
    }


def _chunk_usage_rows(counter, limit):
    """Return frequently used chunk references."""
    rows = []
    for (source_id, chunk_id, source_type), count in counter.most_common(limit):
        rows.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "chunk_id": chunk_id,
                "uses": count,
                "label": _knowledge_title(source_id) if source_type == "knowledge" else "",
            }
        )
    return rows


def _document_usage_rows(counter, limit):
    """Return frequently used document or structured source references."""
    rows = []
    for (source_type, source_id), count in counter.most_common(limit):
        rows.append(
            {
                "source_type": source_type,
                "source_id": source_id,
                "uses": count,
                "label": _knowledge_title(source_id) if source_type == "knowledge" else "",
            }
        )
    return rows


def _source_reference(source):
    """Return one source reference without chunk body text."""
    return {
        "type": source.get("type") or "knowledge",
        "id": _optional_int(source.get("id")),
        "chunk_id": _optional_int(source.get("chunk_id")),
        "section_title": _bounded(
            source.get("section_title") or source.get("source_section"),
            160,
        ),
        "score": _source_score(source),
        "similarity": _source_similarity(source),
        "quality_status": _source_quality(source),
        "label": _source_label(source),
    }


def _source_label(source):
    """Return a readable source reference label."""
    source_type = str(source.get("type") or "knowledge")
    source_id = _optional_int(source.get("id"))
    chunk_id = _optional_int(source.get("chunk_id"))
    section = _bounded(source.get("section_title") or source.get("source_section"), 80)
    label = source_type
    if source_type == "knowledge" and source_id:
        title = _knowledge_title(source_id)
        if title:
            label = title
    elif source_id is not None:
        label = f"{source_type} #{source_id}"
    if chunk_id is not None:
        label = f"{label} / Chunk #{chunk_id}"
    if section:
        label = f"{label} - {section}"
    return label


def _source_row_label(row):
    """Return a source label from a flattened source row."""
    source = {
        "type": row.get("source_type"),
        "id": row.get("source_id"),
        "chunk_id": row.get("chunk_id"),
        "section_title": row.get("section_title"),
    }
    return _source_label(source)


def _source_score(source):
    """Return the best score available for a source."""
    explainability = source.get("explainability") if isinstance(source, dict) else {}
    if isinstance(explainability, dict) and explainability.get("final_score") is not None:
        return _optional_float(explainability.get("final_score"))
    return _optional_float(source.get("score") if isinstance(source, dict) else None)


def _source_similarity(source):
    """Return semantic similarity for one source when available."""
    explainability = source.get("explainability") if isinstance(source, dict) else {}
    if not isinstance(explainability, dict):
        return None
    return _optional_float(explainability.get("semantic_similarity"))


def _source_quality(source):
    """Return source quality status."""
    explainability = source.get("explainability") if isinstance(source, dict) else {}
    if isinstance(explainability, dict) and explainability.get("quality_status"):
        return str(explainability.get("quality_status"))
    return str(source.get("quality_status") or "") if isinstance(source, dict) else ""


def _retrieval_duration_ms(event):
    """Return retrieval duration from stored explainability."""
    if not event:
        return None
    explainability = event.retrieval_explainability()
    if not isinstance(explainability, dict):
        return None
    return _optional_int(explainability.get("retrieval_duration_ms"))


def _similarity_values(events):
    """Return all semantic similarity samples from audit events."""
    values = []
    for row in _source_rows(events):
        if row.get("similarity") is not None:
            values.append(row["similarity"])
    return values


def _is_empty_retrieval(chat):
    """Return whether a chat was answered without retrieved sources."""
    diagnostics = chat.diagnostics()
    return bool(diagnostics.get("empty_retrieval")) or int(chat.source_count or 0) == 0


def _has_hallucination_warning(chat):
    """Return whether a chat has a hallucination-risk warning."""
    diagnostics = chat.diagnostics()
    if diagnostics.get("hallucination_warning"):
        return True
    warnings = diagnostics.get("quality_warnings") or []
    return any(
        isinstance(warning, dict) and warning.get("type") == "hallucination_risk"
        for warning in warnings
    )


def _answer_quality(chat, warnings):
    """Return a simple quality label for one answer."""
    if _has_hallucination_warning(chat):
        return "risk"
    if chat.confidence_level == "low" or warnings:
        return "warning"
    if chat.confidence_level == "high" and int(chat.source_count or 0) > 0:
        return "good"
    return "ok"


def _is_error_event(event):
    """Return whether an audit event counts as an AI error."""
    return bool(event.error_category) or "error" in str(event.status or "").lower()


def _counter_rows(counter):
    """Return sorted counter rows."""
    return [{"key": key, "count": count} for key, count in Counter(counter).most_common()]


def _normalized_question(message):
    """Return a stable grouping key for common question analysis."""
    return " ".join(str(message or "").lower().split())[:300]


def _knowledge_title(document_id):
    """Return a knowledge document title for a source id if it still exists."""
    if document_id is None:
        return ""
    try:
        document = db.session.get(KnowledgeDocument, int(document_id))
    except (TypeError, ValueError):
        return ""
    return _bounded(getattr(document, "title", ""), 180) if document else ""


def _average(values):
    """Return a rounded arithmetic mean."""
    numeric_values = [float(value) for value in values if value is not None]
    if not numeric_values:
        return 0
    return round(sum(numeric_values) / len(numeric_values), 4)


def _average_from_total(total, count):
    """Return a rounded average from a total and count."""
    return round(total / count, 2) if count else None


def _percentile(values, percentile):
    """Return a nearest-rank percentile."""
    numeric_values = sorted(float(value) for value in values if value is not None)
    if not numeric_values:
        return 0
    index = max(0, min(len(numeric_values) - 1, ceil(len(numeric_values) * percentile) - 1))
    return int(round(numeric_values[index]))


def _rate(numerator, denominator):
    """Return a rounded ratio."""
    return round(numerator / denominator, 4) if denominator else 0


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value):
    """Return an optional float value."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_int(value, default, minimum, maximum):
    """Return a bounded integer value."""
    try:
        parsed = int(value if value not in (None, "") else default)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _bounded(value, max_chars):
    """Return normalized text bounded to max chars."""
    text = " ".join(str(value or "").strip().split())
    return text[:max_chars]
