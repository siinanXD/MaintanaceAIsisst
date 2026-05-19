"""Read-only admin retrieval debug view models."""

from __future__ import annotations

from datetime import timedelta

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AIFeedback, ChatMessage

DEFAULT_DEBUG_DAYS = 30
DEFAULT_DEBUG_LIMIT = 30
MAX_DEBUG_LIMIT = 100
ANSWER_PREVIEW_CHARS = 420


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
            "shows_full_answer": False,
            "question_max_chars": 220,
            "answer_preview_max_chars": ANSWER_PREVIEW_CHARS,
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
    structured_sources = _structured_sources(sources)
    rag_chunks = _rag_chunks(sources)
    context_builder = explainability.get("context_builder") or {}
    safety = explainability.get("safety") or {}
    post_generation_safety = explainability.get("post_generation_safety") or {}
    confidence = {
        "score": chat.confidence_score,
        "level": chat.confidence_level,
    }
    retrieval_duration_ms = explainability.get(
        "retrieval_duration_ms",
        diagnostics.get("retrieval_duration_ms", 0),
    )
    scores = _scores(sources, explainability)
    flow_context = {
        "chat": chat,
        "diagnostics": diagnostics,
        "explainability": explainability,
        "query_understanding": query_understanding,
        "sources": sources,
        "structured_sources": structured_sources,
        "rag_chunks": rag_chunks,
        "scores": scores,
        "context_builder": context_builder,
        "safety": safety,
        "post_generation_safety": post_generation_safety,
        "confidence": confidence,
        "retrieval_duration_ms": retrieval_duration_ms,
    }
    return {
        "chat_message_id": chat.id,
        "audit_event_id": chat.audit_event_id,
        "user_id": chat.user_id,
        "user_question": _bounded(chat.message, 220),
        "answer_preview": _bounded(chat.response, ANSWER_PREVIEW_CHARS),
        "query_type": query_understanding.get("query_type") or "unknown",
        "query_understanding": query_understanding,
        "used_sources": sources,
        "structured_sources": structured_sources,
        "rag_chunks": rag_chunks,
        "scores": scores,
        "reranking": _reranking_summary(sources),
        "context_builder": context_builder,
        "explainability": {
            "source_count": explainability.get("source_count", 0),
            "explained_source_count": explainability.get("explained_source_count", 0),
            "averages": explainability.get("averages", {}),
            "quality_status_counts": explainability.get("quality_status_counts", {}),
        },
        "confidence": confidence,
        "conflicts": explainability.get("conflicts") or {},
        "safety": safety,
        "post_generation_safety": post_generation_safety,
        "safety_checks": _safety_checks(safety, post_generation_safety),
        "machine_references": _machine_references(explainability, diagnostics),
        "source_answer_links": _source_answer_links(sources),
        "flow_steps": _flow_steps(flow_context),
        "feedback": feedback,
        "retrieval_duration_ms": retrieval_duration_ms,
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


def _structured_sources(sources):
    """Return prompt-safe structured source references."""
    return [
        _flow_source(source, index)
        for index, source in enumerate(sources or [], start=1)
        if not _is_rag_chunk(source)
    ][:8]


def _rag_chunks(sources):
    """Return prompt-safe RAG chunk references."""
    return [
        _flow_source(source, index)
        for index, source in enumerate(sources or [], start=1)
        if _is_rag_chunk(source)
    ][:8]


def _flow_source(source, rank):
    """Return one source reference for the admin flow visualization."""
    explainability = source.get("explainability") or {}
    return {
        "rank": rank,
        "type": source.get("type") or "knowledge",
        "id": source.get("id"),
        "chunk_id": source.get("chunk_id"),
        "section_title": source.get("section_title") or source.get("source_section") or "",
        "chunk_order": source.get("chunk_order"),
        "score": source.get("score"),
        "final_score": explainability.get("final_score"),
        "quality_status": explainability.get("quality_status") or source.get("quality_status"),
        "machine_match": explainability.get("machine_match"),
        "machine_match_reasons": explainability.get("machine_match_reasons") or [],
        "source_label": _source_label(source),
    }


def _source_label(source):
    """Return a source label without exposing source body text."""
    source_type = str(source.get("type") or "knowledge")
    source_id = source.get("id")
    chunk_id = source.get("chunk_id")
    section = source.get("section_title") or source.get("source_section")
    label = source_type
    if source_id is not None:
        label = f"{label} #{source_id}"
    if chunk_id is not None:
        label = f"{label} / Chunk #{chunk_id}"
    if section:
        label = f"{label} - {str(section)[:80]}"
    return label


def _is_rag_chunk(source):
    """Return whether a source represents a RAG knowledge chunk."""
    if not isinstance(source, dict):
        return False
    return source.get("type") == "knowledge" or source.get("chunk_id") is not None


def _reranking_summary(sources):
    """Return prompt-safe re-ranking diagnostics for retrieved sources."""
    ranked_sources = [
        _flow_source(source, index)
        for index, source in enumerate(sources or [], start=1)
    ][:8]
    reranked_count = sum(
        1
        for source in ranked_sources
        if source.get("final_score") is not None
        and source.get("score") is not None
        and source.get("final_score") != source.get("score")
    )
    score_values = [
        _optional_float(source.get("final_score"))
        if source.get("final_score") is not None
        else _optional_float(source.get("score"))
        for source in ranked_sources
    ]
    top_score = max(
        [score for score in score_values if score is not None],
        default=None,
    )
    return {
        "candidate_count": len(sources or []),
        "shown_count": len(ranked_sources),
        "reranked_count": reranked_count,
        "top_score": top_score,
        "ranked_sources": ranked_sources,
    }


def _safety_checks(safety, post_generation_safety):
    """Return pre- and post-generation safety check summaries."""
    pre_safety = safety if isinstance(safety, dict) else {}
    post_safety = post_generation_safety if isinstance(post_generation_safety, dict) else {}
    return [
        {
            "phase": "pre_generation",
            "label": "Pre-Generation Safety",
            "safety_relevant": bool(pre_safety.get("safety_relevant")),
            "risk_level": pre_safety.get("risk_level") or "",
            "categories": pre_safety.get("categories") or [],
            "warning_count": len(pre_safety.get("warnings") or []),
        },
        {
            "phase": "post_generation",
            "label": "Post-Generation Safety",
            "safety_relevant": bool(post_safety.get("safety_relevant")),
            "risk_level": post_safety.get("risk_level") or "",
            "action": post_safety.get("action") or "",
            "modified": bool(post_safety.get("modified")),
            "warning_count": len(post_safety.get("warnings") or []),
        },
    ]


def _source_answer_links(sources):
    """Return source-to-answer linkage hints without answer or chunk body text."""
    links = []
    for index, source in enumerate(sources or [], start=1):
        flow_source = _flow_source(source, index)
        reasons = []
        if flow_source.get("final_score") is not None or flow_source.get("score") is not None:
            reasons.append("score_signal")
        if flow_source.get("quality_status"):
            reasons.append("quality_gate")
        if flow_source.get("machine_match_reasons"):
            reasons.append("machine_context")
        if flow_source.get("section_title"):
            reasons.append("section_context")
        links.append(
            {
                "source": flow_source,
                "relation": "used_as_answer_context",
                "reasons": reasons or ["retrieved_context"],
            }
        )
    return links[:8]


def _flow_steps(context):
    """Return ordered AI retrieval flow steps for admin visualization."""
    query = context["query_understanding"]
    sources = context["sources"]
    structured_sources = context["structured_sources"]
    rag_chunks = context["rag_chunks"]
    context_builder = context["context_builder"]
    safety = context["safety"]
    post_generation_safety = context["post_generation_safety"]
    confidence = context["confidence"]
    return [
        _flow_step(
            "question",
            "Userfrage",
            "ok",
            "Eingang wurde auf einen Retrieval-Query-Typ klassifiziert.",
            {
                "query_type": query.get("query_type") or "unknown",
                "query_confidence": query.get("confidence"),
            },
        ),
        _flow_step(
            "structured_retrieval",
            "Strukturierte Quellen",
            "ok" if structured_sources else "empty",
            f"{len(structured_sources)} strukturierte Quellen im Vergleichspfad.",
            {"source_count": len(structured_sources)},
        ),
        _flow_step(
            "rag_chunks",
            "RAG-Chunks",
            "ok" if rag_chunks else "empty",
            f"{len(rag_chunks)} Knowledge-Chunks im Retrieval-Kontext.",
            {"chunk_count": len(rag_chunks)},
        ),
        _flow_step(
            "reranking",
            "Scoring und Re-Ranking",
            "ok" if sources else "empty",
            "Kandidaten wurden anhand der gespeicherten Score-Signale sortiert.",
            _reranking_summary(sources),
        ),
        _flow_step(
            "context_builder",
            "Context Building",
            _context_builder_status(context_builder),
            _context_builder_summary(context_builder),
            context_builder.get("stats") if isinstance(context_builder, dict) else {},
        ),
        _flow_step(
            "safety",
            "Safety Checks",
            _safety_status(safety, post_generation_safety),
            _safety_summary(safety, post_generation_safety),
            {"checks": _safety_checks(safety, post_generation_safety)},
        ),
        _flow_step(
            "generation",
            "Finale Antwort",
            "ok" if context["chat"].response else "empty",
            "Antwortvorschau ist gekürzt und stammt aus der gespeicherten Chat-Historie.",
            {
                "answer_preview_chars": min(
                    len(context["chat"].response or ""),
                    ANSWER_PREVIEW_CHARS,
                ),
            },
        ),
        _flow_step(
            "confidence",
            "Confidence",
            _confidence_status(confidence),
            _confidence_summary(confidence),
            confidence,
        ),
    ]


def _flow_step(key, label, status, summary, metrics=None):
    """Return one visual flow step."""
    return {
        "key": key,
        "label": label,
        "status": status,
        "summary": summary,
        "metrics": metrics or {},
    }


def _context_builder_status(context_builder):
    """Return a flow status for context-builder diagnostics."""
    if not isinstance(context_builder, dict) or not context_builder:
        return "empty"
    stats = context_builder.get("stats") or {}
    if stats.get("removed_source_count") or stats.get("truncated_source_count"):
        return "warning"
    return "ok"


def _context_builder_summary(context_builder):
    """Return a compact context-builder summary."""
    if not isinstance(context_builder, dict) or not context_builder:
        return "Kein separater Context-Builder-Datensatz gespeichert."
    stats = context_builder.get("stats") or {}
    section_count = stats.get("section_count", 0)
    used_chars = stats.get("used_chars", 0)
    max_chars = stats.get("max_chars", 0)
    return f"{section_count} Sections, {used_chars}/{max_chars} Zeichen Kontextbudget."


def _safety_status(safety, post_generation_safety):
    """Return a flow status for safety diagnostics."""
    if _safety_relevant(safety) or _safety_relevant(post_generation_safety):
        return "warning"
    return "ok"


def _safety_summary(safety, post_generation_safety):
    """Return a compact safety summary."""
    checks = _safety_checks(safety, post_generation_safety)
    relevant = [check for check in checks if check.get("safety_relevant")]
    if not relevant:
        return "Keine sicherheitsrelevanten Signale in den gespeicherten Checks."
    labels = [check["label"] for check in relevant]
    return "Sicherheitsrelevant: " + ", ".join(labels)


def _safety_relevant(value):
    """Return whether a safety payload is marked relevant."""
    return isinstance(value, dict) and bool(value.get("safety_relevant"))


def _confidence_status(confidence):
    """Return a flow status for confidence."""
    score = _optional_float((confidence or {}).get("score"))
    level = str((confidence or {}).get("level") or "")
    if level == "low" or (score is not None and score < 45):
        return "warning"
    if score is None:
        return "empty"
    return "ok"


def _confidence_summary(confidence):
    """Return a compact confidence summary."""
    score = (confidence or {}).get("score")
    level = (confidence or {}).get("level")
    if score is None and not level:
        return "Keine Confidence-Metadaten gespeichert."
    return f"{score if score is not None else '-'} / {level or '-'}"


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


def _optional_float(value):
    """Return an optional floating-point value."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
