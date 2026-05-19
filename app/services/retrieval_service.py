"""Retrieval orchestration for structured data and RAG knowledge chunks."""

from time import perf_counter

from flask import current_app, has_app_context

from app.services.ai_retrieval import retrieve_ai_context
from app.services.ai_safety_service import assess_ai_safety
from app.services.context_builder_service import build_dynamic_context
from app.services.incident_timeline_service import timeline_context_for_query
from app.services.knowledge_linking_service import linked_knowledge_for_sources
from app.services.query_understanding_service import classify_query
from app.services.retrieval_explainability_service import explainability_from_metadata
from app.services.source_conflict_service import detect_source_conflicts
from app.services.vector_store_service import get_vector_store


def retrieve_context(message, user, requested_scopes=None, conversation_context=None):
    """Return permission-aware structured and vector retrieval context."""
    started_at = perf_counter()
    retrieval_message = _retrieval_message(message, conversation_context)
    understanding = classify_query(retrieval_message, requested_scopes=requested_scopes)
    effective_scopes = _effective_scopes(requested_scopes, understanding)
    strategy = understanding.retrieval_strategy
    structured = retrieve_ai_context(retrieval_message, user, effective_scopes)
    structured_context = structured.get("context", "")
    structured_sources = structured.get("sources") or []
    data = dict(structured.get("data") or {})

    if not is_rag_enabled():
        sources = _deduplicate_sources(structured_sources)
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
        return _retrieval_payload(
            context=dynamic_context["context"],
            sources=sources,
            data=data,
            structured=structured,
            understanding=understanding,
            safety=safety,
            conflicts=conflicts,
            context_builder=dynamic_context,
            retrieval_duration_ms=_duration_ms(started_at),
            knowledge_links={"links": []},
            timeline_context={"context": "", "sources": [], "summary": {}},
        )

    vector_results = retrieve_vector_chunks(
        retrieval_message,
        user,
        limit=strategy.get("top_k"),
        filters=_strategy_filters(strategy),
    )
    vector_context = _vector_context(vector_results) if vector_results else ""
    vector_sources = [_source_from_result(result) for result in vector_results]
    sources = _deduplicate_sources(structured_sources + vector_sources)
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
    return _retrieval_payload(
        context=dynamic_context["context"],
        sources=sources,
        data=data,
        structured=structured,
        understanding=understanding,
        safety=safety,
        conflicts=conflicts,
        context_builder=dynamic_context,
        retrieval_duration_ms=_duration_ms(started_at),
        knowledge_links=knowledge_links,
        timeline_context=timeline_context,
    )


def retrieve_vector_chunks(message, user, limit=None, filters=None):
    """Return vector-store knowledge chunks visible to the user."""
    if not is_rag_enabled():
        return []
    return get_vector_store().similarity_search(
        query_text=message,
        user=user,
        limit=limit,
        filters=filters,
    )


def knowledge_context_for_chat(message, user, limit=None, conversation_context=None):
    """Return RAG knowledge context and public sources for chat workflows."""
    retrieval_message = _retrieval_message(message, conversation_context)
    understanding = classify_query(retrieval_message)
    strategy_limit = limit or understanding.retrieval_strategy.get("top_k")
    vector_results = retrieve_vector_chunks(retrieval_message, user, limit=strategy_limit)
    if not vector_results:
        return _prompt_context("", conversation_context), []
    return _prompt_context(_vector_context(vector_results), conversation_context), [
        _source_from_result(result) for result in vector_results
    ]


def is_rag_enabled():
    """Return whether RAG retrieval is enabled for the current app."""
    if not has_app_context():
        return True
    value = current_app.config.get("RAG_ENABLED", True)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _vector_context(results):
    """Build compact source context from vector-search results."""
    blocks = []
    for result in results:
        metadata = result.metadata
        title = metadata.get("title") or "Wissensquelle"
        source_id = metadata.get("id") or metadata.get("source_id") or ""
        document_type = metadata.get("document_type") or metadata.get("source_type") or ""
        machine_context = _machine_context_line(metadata)
        block_lines = [
            f"Quelle: Wissen #{source_id} - {title}",
            f"Dokumenttyp: {document_type}",
        ]
        if machine_context:
            block_lines.append(machine_context)
        block_lines.append(result.text)
        blocks.append(
            "\n".join(block_lines)
        )
    return "\n\n".join(blocks)


def _source_from_result(result):
    """Return a public source payload for one vector-search result."""
    metadata = result.metadata
    score_signals = metadata.get("score_signals") or {}
    explainability = explainability_from_metadata(metadata, result.score)
    source = {
        "type": metadata.get("type", "knowledge"),
        "id": metadata.get("id"),
        "chunk_id": metadata.get("chunk_id"),
        "title": metadata.get("title", "Wissensquelle"),
        "module": metadata.get("module", "knowledge"),
        "url": metadata.get("url", "/admin/ai"),
        "reason": f"{int(result.score)} RAG-Trefferpunkte",
        "score": int(result.score),
        "quality_status": explainability.get("quality_status")
        or metadata.get("quality_status")
        or score_signals.get("quality_status"),
        "machine_match": explainability.get("machine_match", 0),
        "machine_match_reasons": explainability.get("machine_match_reasons", []),
        "explainability": explainability,
    }
    if _score_debug_enabled() and metadata.get("score_debug"):
        source["score_debug"] = metadata["score_debug"]
    return source


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
    reasons = signals.get("machine_match_reasons") or []
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
