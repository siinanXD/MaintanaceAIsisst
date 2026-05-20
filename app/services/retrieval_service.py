"""Retrieval orchestration for structured data and RAG knowledge chunks."""

import re
from time import perf_counter

from flask import current_app, has_app_context

from app.services.ai_retrieval import retrieve_ai_context
from app.services.ai_safety_service import assess_ai_safety
from app.services.context_builder_service import build_dynamic_context
from app.services.incident_timeline_service import timeline_context_for_query
from app.services.knowledge_linking_service import linked_knowledge_for_sources
from app.services.query_understanding_service import classify_query
from app.services.query_classifier_service import QUERY_TYPE_GENERAL, QUERY_TYPE_LIVE_SQL
from app.services.retrieval_candidate_service import (
    public_sources_from_candidates,
    rank_candidates,
    vector_result_candidate,
)
from app.services.retrieval_debug_service import empty_retrieval_debug, merge_retrieval_debug
from app.services.source_conflict_service import detect_source_conflicts
from app.services.sql_keyword_retrieval_service import retrieve_sql_keyword_fallback
from app.services.vector_store_service import get_vector_store

SQL_KEYWORD_FALLBACK_THRESHOLD = 2
EXACT_SQL_LOOKUP_PATTERN = re.compile(
    r"\b(?:task|aufgabe)\s*#?\s*\d+\b|\b[A-Z]{1,6}[-_ ]?\d{2,6}\b",
    re.IGNORECASE,
)


def retrieve_context(
    message,
    user,
    requested_scopes=None,
    conversation_context=None,
    query_classification=None,
):
    """Return permission-aware structured and vector retrieval context."""
    started_at = perf_counter()
    retrieval_message = _retrieval_message(message, conversation_context)
    understanding = classify_query(retrieval_message, requested_scopes=requested_scopes)
    effective_scopes = _effective_scopes(requested_scopes, understanding)
    strategy = understanding.retrieval_strategy
    structured = retrieve_ai_context(retrieval_message, user, effective_scopes)
    structured_context = structured.get("context", "")
    structured_candidates = structured.get("candidates") or []
    data = dict(structured.get("data") or {})
    filters = _strategy_filters(strategy)
    retrieval_debug = merge_retrieval_debug(
        structured.get("debug") or {},
        rag_enabled=is_rag_enabled(),
        filters=filters or {},
        top_k=strategy.get("top_k"),
        query_classification_type=_classification_type(query_classification),
        query_classification_sources=_classification_sources(query_classification),
    )

    if not is_rag_enabled():
        sources = _deduplicate_sources(
            public_sources_from_candidates(rank_candidates(structured_candidates))
        )
        fallback = _sql_keyword_fallback(
            retrieval_message,
            user,
            sources,
            structured_candidates,
            [],
            query_classification,
        )
        if fallback["candidates"]:
            structured_candidates = [*structured_candidates, *fallback["candidates"]]
            sources = _deduplicate_sources(
                public_sources_from_candidates(rank_candidates(structured_candidates))
            )
            structured_context = _join_context(
                structured_context,
                _candidate_context(fallback["candidates"]),
            )
            _merge_data(data, fallback["data"])
            retrieval_debug = merge_retrieval_debug(retrieval_debug, fallback["debug"])
        conflicts = detect_source_conflicts(sources, data)
        safety = assess_ai_safety(retrieval_message, understanding, sources)
        dynamic_context = build_dynamic_context(
            retrieval_message,
            {
                "structured_context": structured_context,
                "vector_context": "",
                "sources": sources,
                "knowledge_sources": [],
                "knowledge_links": {"links": []},
            },
            understanding,
            safety_assessment=safety,
            conflicts=conflicts,
            conversation_context=conversation_context,
        )
        duration_ms = _duration_ms(started_at)
        return _retrieval_payload(
            context=dynamic_context["context"],
            sources=sources,
            data=data,
            structured=structured,
            understanding=understanding,
            safety=safety,
            conflicts=conflicts,
            context_builder=dynamic_context,
            retrieval_duration_ms=duration_ms,
            knowledge_links={"links": []},
            timeline_context={"context": "", "sources": [], "summary": {}},
            retrieval_debug=merge_retrieval_debug(
                retrieval_debug,
                rag_enabled=False,
                final_visible_sources=len(sources),
                source_types=_source_type_counts(sources),
                duration_ms=duration_ms,
            ),
            query_classification=_classification_payload(query_classification),
        )

    vector_results, vector_debug = _retrieve_vector_chunks_with_debug(
        retrieval_message,
        user,
        limit=strategy.get("top_k"),
        filters=filters,
    )
    vector_candidates = rank_candidates(
        [
            vector_result_candidate(
                result,
                include_score_debug=_score_debug_enabled(),
            )
            for result in vector_results
        ]
    )
    vector_context = _vector_context(vector_candidates) if vector_candidates else ""
    vector_sources = public_sources_from_candidates(
        vector_candidates,
        include_score_debug=_score_debug_enabled(),
    )
    ranked_sources = public_sources_from_candidates(
        rank_candidates([*structured_candidates, *vector_candidates]),
        include_score_debug=_score_debug_enabled(),
    )
    sources = _deduplicate_sources(ranked_sources)
    data["knowledge"] = vector_sources
    knowledge_links = linked_knowledge_for_sources(vector_sources, user=user)
    data["knowledge_links"] = knowledge_links.get("links", [])
    timeline_context = timeline_context_for_query(
        retrieval_message,
        user,
        query_understanding=understanding,
    )
    if timeline_context.get("sources"):
        sources = _deduplicate_sources(sources + timeline_context["sources"])
        data["incident_timeline"] = timeline_context.get("summary", {})

    fallback = _sql_keyword_fallback(
        retrieval_message,
        user,
        sources,
        structured_candidates,
        vector_candidates,
        query_classification,
    )
    if fallback["candidates"]:
        structured_candidates = [*structured_candidates, *fallback["candidates"]]
        ranked_sources = public_sources_from_candidates(
            rank_candidates([*structured_candidates, *vector_candidates]),
            include_score_debug=_score_debug_enabled(),
        )
        sources = _deduplicate_sources(ranked_sources)
        if timeline_context.get("sources"):
            sources = _deduplicate_sources(sources + timeline_context["sources"])
        structured_context = _join_context(
            structured_context,
            _candidate_context(fallback["candidates"]),
        )
        _merge_data(data, fallback["data"])
        retrieval_debug = merge_retrieval_debug(retrieval_debug, fallback["debug"])

    conflicts = detect_source_conflicts(sources, data)
    safety = assess_ai_safety(retrieval_message, understanding, sources)
    dynamic_context = build_dynamic_context(
        retrieval_message,
        {
            "structured_context": structured_context,
            "vector_context": vector_context,
            "sources": sources,
            "knowledge_sources": vector_sources,
            "knowledge_links": knowledge_links,
        },
        understanding,
        safety_assessment=safety,
        conflicts=conflicts,
        conversation_context=conversation_context,
        timeline_context=timeline_context,
    )
    duration_ms = _duration_ms(started_at)
    return _retrieval_payload(
        context=dynamic_context["context"],
        sources=sources,
        data=data,
        structured=structured,
        understanding=understanding,
        safety=safety,
        conflicts=conflicts,
        context_builder=dynamic_context,
        retrieval_duration_ms=duration_ms,
        knowledge_links=knowledge_links,
        timeline_context=timeline_context,
        retrieval_debug=merge_retrieval_debug(
            retrieval_debug,
            vector_debug,
            rag_enabled=True,
            final_visible_sources=len(sources),
            source_types=_source_type_counts(sources),
            duration_ms=duration_ms,
        ),
        query_classification=_classification_payload(query_classification),
    )


def retrieve_vector_chunks(message, user, limit=None, filters=None):
    """Return vector-store knowledge chunks visible to the user."""
    results, _debug = _retrieve_vector_chunks_with_debug(message, user, limit, filters)
    return results


def _retrieve_vector_chunks_with_debug(message, user, limit=None, filters=None):
    """Return vector chunks and prompt-safe retrieval debug counters."""
    if not is_rag_enabled():
        return [], empty_retrieval_debug(rag_enabled=False, filters=filters or {})
    store = get_vector_store()
    results = store.similarity_search(
        query_text=message,
        user=user,
        limit=limit,
        filters=filters,
    )
    debug = store.last_debug() if hasattr(store, "last_debug") else {}
    return results, debug


def _sql_keyword_fallback(
    message,
    user,
    sources,
    structured_candidates,
    vector_candidates,
    query_classification,
):
    """Return SQL keyword fallback data when visible sources are below threshold."""
    if not _should_run_sql_keyword_fallback(message, sources, query_classification):
        return {"candidates": [], "data": {}, "debug": {}}
    fallback = retrieve_sql_keyword_fallback(
        message,
        user,
        existing_sources=sources,
        limit=max(SQL_KEYWORD_FALLBACK_THRESHOLD - len(sources or []), 1),
    )
    existing_keys = {
        (candidate.source_type, candidate.source_id)
        for candidate in [*(structured_candidates or []), *(vector_candidates or [])]
    }
    candidates = [
        candidate
        for candidate in fallback.get("candidates") or []
        if (candidate.source_type, candidate.source_id) not in existing_keys
    ]
    return {
        "candidates": candidates,
        "data": fallback.get("data") or {},
        "debug": fallback.get("debug") or {},
    }


def _should_run_sql_keyword_fallback(message, sources, query_classification=None):
    """Return whether SQL fallback should supplement current retrieval sources."""
    classification_type = _classification_type(query_classification)
    if classification_type == QUERY_TYPE_GENERAL and not _classification_entities(
        query_classification
    ):
        return False
    if classification_type == QUERY_TYPE_LIVE_SQL and _classification_entities(
        query_classification
    ):
        return True
    if len(sources or []) < SQL_KEYWORD_FALLBACK_THRESHOLD:
        return True
    return bool(EXACT_SQL_LOOKUP_PATTERN.search(str(message or "")))


def knowledge_context_for_chat(message, user, limit=None, conversation_context=None):
    """Return RAG knowledge context and public sources for chat workflows."""
    retrieval_message = _retrieval_message(message, conversation_context)
    understanding = classify_query(retrieval_message)
    strategy_limit = limit or understanding.retrieval_strategy.get("top_k")
    vector_results = retrieve_vector_chunks(retrieval_message, user, limit=strategy_limit)
    vector_candidates = rank_candidates(
        [
            vector_result_candidate(
                result,
                include_score_debug=_score_debug_enabled(),
            )
            for result in vector_results
        ],
        strategy_limit,
    )
    if not vector_candidates:
        return _prompt_context("", conversation_context), []
    return _prompt_context(_vector_context(vector_candidates), conversation_context), (
        public_sources_from_candidates(
            vector_candidates,
            include_score_debug=_score_debug_enabled(),
        )
    )


def is_rag_enabled():
    """Return whether RAG retrieval is enabled for the current app."""
    if not has_app_context():
        return True
    value = current_app.config.get("RAG_ENABLED", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _vector_context(candidates):
    """Build compact source context from ranked knowledge candidates."""
    blocks = []
    for candidate in candidates:
        metadata = candidate.metadata
        title = candidate.title or "Wissensquelle"
        source_id = candidate.source_id or metadata.get("source_record_id") or ""
        document_type = (
            metadata.get("document_type")
            or metadata.get("knowledge_source_type")
            or candidate.source_type
        )
        machine_context = _machine_context_line(metadata)
        block_lines = [
            f"Quelle: Wissen #{source_id} - {title}",
            f"Dokumenttyp: {document_type}",
            f"Chunk-ID: {metadata.get('chunk_id') or ''}",
            f"Retrieval Score: {round(float(candidate.normalized_score or 0), 2)}",
        ]
        if metadata.get("section_title"):
            block_lines.append(f"Abschnitt: {metadata['section_title']}")
        if machine_context:
            block_lines.append(machine_context)
        block_lines.append(candidate.content)
        blocks.append(
            "\n".join(block_lines)
        )
    return "\n\n".join(blocks)


def _retrieval_payload(
    context,
    sources,
    data,
    structured,
    understanding,
    safety,
    conflicts,
    context_builder,
    retrieval_duration_ms,
    knowledge_links,
    timeline_context,
    retrieval_debug,
    query_classification=None,
):
    """Return the normalized retrieval payload used by RAG and chat."""
    return {
        "context": context,
        "sources": sources,
        "data": data,
        "allowed_scopes": structured.get("allowed_scopes", []),
        "requested_scopes": structured.get("requested_scopes", []),
        "query_understanding": understanding.to_dict(),
        "safety": safety.to_dict(),
        "conflicts": conflicts,
        "context_builder": {
            "sections": context_builder.get("sections", []),
            "stats": context_builder.get("stats", {}),
            "explainability": context_builder.get("explainability", {}),
        },
        "retrieval_duration_ms": retrieval_duration_ms,
        "knowledge_links": knowledge_links,
        "timeline_context": {
            "summary": timeline_context.get("summary", {}),
            "source_count": len(timeline_context.get("sources") or []),
        },
        "retrieval_debug": retrieval_debug,
        "query_classification": query_classification or {},
    }


def _deduplicate_sources(sources):
    """Return sources without duplicate type/id/chunk combinations."""
    seen = set()
    unique_sources = []
    for source in sources:
        key = (source.get("type"), source.get("id"), source.get("chunk_id"))
        if key in seen:
            continue
        seen.add(key)
        unique_sources.append(source)
    return unique_sources


def _source_type_counts(sources):
    """Return prompt-safe counts grouped by public source type."""
    counts = {}
    for source in sources or []:
        source_type = str(source.get("type") or "unknown")
        counts[source_type] = counts.get(source_type, 0) + 1
    return counts


def _candidate_context(candidates):
    """Return context blocks for fallback candidates."""
    return "\n\n".join(candidate.context_block() for candidate in candidates or [])


def _join_context(*parts):
    """Join non-empty retrieval context parts."""
    return "\n\n".join(part for part in parts if part)


def _merge_data(target, additions):
    """Merge fallback data payloads into retrieval data without replacing keys."""
    if not additions:
        return target
    fallback_data = target.setdefault("sql_keyword_fallback", {})
    for key, items in additions.items():
        fallback_data.setdefault(key, []).extend(items or [])
    return target


def _classification_payload(query_classification):
    """Return a JSON-safe query classification payload."""
    if query_classification is None:
        return {}
    if hasattr(query_classification, "to_dict"):
        return query_classification.to_dict()
    if isinstance(query_classification, dict):
        return dict(query_classification)
    return {}


def _classification_type(query_classification):
    """Return the high-level query classification type."""
    payload = _classification_payload(query_classification)
    return str(payload.get("query_type") or "")


def _classification_sources(query_classification):
    """Return suggested source names from a query classification."""
    payload = _classification_payload(query_classification)
    sources = payload.get("suggested_sources") or []
    return [str(source) for source in sources if source]


def _classification_entities(query_classification):
    """Return entity hints from a query classification."""
    payload = _classification_payload(query_classification)
    entities = payload.get("possible_entities") or {}
    return entities if isinstance(entities, dict) else {}


def _score_debug_enabled():
    """Return whether retrieval score debug fields should be exposed."""
    if not has_app_context():
        return False
    return bool(current_app.config.get("RAG_SCORE_DEBUG", False))


def _effective_scopes(requested_scopes, understanding):
    """Return requested scopes enriched by query understanding."""
    scopes = list(requested_scopes or [])
    for scope in understanding.recommended_scopes:
        if scope not in scopes:
            scopes.append(scope)
    return set(scopes)


def _strategy_filters(strategy):
    """Return optional vector-store filters for a routing strategy."""
    source_types = list(strategy.get("source_types") or [])
    if len(source_types) == 1:
        return {"source_type": source_types[0]}
    return None


def _duration_ms(started_at):
    """Return elapsed milliseconds from a perf_counter start value."""
    return int(round((perf_counter() - started_at) * 1000))


def _retrieval_message(message, conversation_context):
    """Return a query string enriched by short-term conversation context."""
    if conversation_context is None:
        return message
    return conversation_context.retrieval_query(message)


def _prompt_context(context, conversation_context):
    """Return retrieval context with optional conversation memory prepended."""
    if conversation_context is None:
        return context
    return conversation_context.prompt_context(context)


def _machine_context_line(metadata):
    """Return an optional context line explaining machine-aware retrieval signals."""
    signals = metadata.get("score_signals") or {}
    reasons = metadata.get("machine_match_reasons") or signals.get(
        "machine_match_reasons",
    ) or []
    if not reasons:
        return ""
    labels = {
        "same_machine": "gleiche Maschine",
        "same_machine_series": "gleiche Maschinenserie",
        "same_area": "gleicher Bereich",
        "same_manufacturer": "gleicher Hersteller",
        "same_error_code": "gleicher Fehlercode",
        "similar_error_code": "aehnlicher Fehlercode",
    }
    reason_text = ", ".join(labels.get(reason, reason) for reason in reasons)
    return f"Maschinenkontext: {reason_text}"
