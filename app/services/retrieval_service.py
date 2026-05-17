"""Retrieval orchestration for structured data and RAG knowledge chunks."""

from flask import current_app, has_app_context

from app.services.ai_retrieval import retrieve_ai_context
from app.services.retrieval_explainability_service import explainability_from_metadata
from app.services.vector_store_service import get_vector_store


def retrieve_context(message, user, requested_scopes=None, conversation_context=None):
    """Return permission-aware structured and vector retrieval context."""
    retrieval_message = _retrieval_message(message, conversation_context)
    structured = retrieve_ai_context(retrieval_message, user, requested_scopes)
    if not is_rag_enabled():
        structured["context"] = _prompt_context(structured.get("context", ""), conversation_context)
        return structured

    vector_results = retrieve_vector_chunks(retrieval_message, user)
    if not vector_results:
        structured["context"] = _prompt_context(structured.get("context", ""), conversation_context)
        return structured

    vector_context = _vector_context(vector_results)
    structured_context = structured.get("context", "")
    context = f"{structured_context}\n\n{vector_context}" if structured_context else vector_context
    vector_sources = [_source_from_result(result) for result in vector_results]
    sources = _deduplicate_sources((structured.get("sources") or []) + vector_sources)
    data = dict(structured.get("data") or {})
    data["knowledge"] = vector_sources
    return {
        "context": _prompt_context(context, conversation_context),
        "sources": sources,
        "data": data,
        "allowed_scopes": structured.get("allowed_scopes", []),
        "requested_scopes": structured.get("requested_scopes", []),
    }


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
    vector_results = retrieve_vector_chunks(retrieval_message, user, limit=limit)
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
