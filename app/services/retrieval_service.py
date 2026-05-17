"""Retrieval orchestration for structured data and RAG knowledge chunks."""

from flask import current_app, has_app_context

from app.services.ai_retrieval import retrieve_ai_context
from app.services.vector_store_service import get_vector_store


def retrieve_context(message, user, requested_scopes=None):
    """Return permission-aware structured and vector retrieval context."""
    structured = retrieve_ai_context(message, user, requested_scopes)
    if not is_rag_enabled():
        return structured

    vector_results = retrieve_vector_chunks(message, user)
    if not vector_results:
        return structured

    vector_context = _vector_context(vector_results)
    structured_context = structured.get("context", "")
    context = f"{structured_context}\n\n{vector_context}" if structured_context else vector_context
    vector_sources = [_source_from_result(result) for result in vector_results]
    sources = _deduplicate_sources((structured.get("sources") or []) + vector_sources)
    data = dict(structured.get("data") or {})
    data["knowledge"] = vector_sources
    return {
        "context": context,
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


def knowledge_context_for_chat(message, user, limit=None):
    """Return RAG knowledge context and public sources for chat workflows."""
    vector_results = retrieve_vector_chunks(message, user, limit=limit)
    if not vector_results:
        return "", []
    return _vector_context(vector_results), [
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
        blocks.append(
            "\n".join(
                [
                    f"Quelle: Wissen #{source_id} - {title}",
                    f"Dokumenttyp: {document_type}",
                    result.text,
                ]
            )
        )
    return "\n\n".join(blocks)


def _source_from_result(result):
    """Return a public source payload for one vector-search result."""
    metadata = result.metadata
    return {
        "type": metadata.get("type", "knowledge"),
        "id": metadata.get("id"),
        "chunk_id": metadata.get("chunk_id"),
        "title": metadata.get("title", "Wissensquelle"),
        "module": metadata.get("module", "knowledge"),
        "url": metadata.get("url", "/admin/ai"),
        "reason": f"{int(result.score)} RAG-Trefferpunkte",
        "score": int(result.score),
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
