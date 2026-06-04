"""Local text knowledge base for AI retrieval."""

from app.services.source_visibility_policy import can_user_read_source_document

MAX_RETRIEVAL_CHUNKS = 4


def search_knowledge_chunks(query_text, user, limit=MAX_RETRIEVAL_CHUNKS):
    """Return visible knowledge chunks through the shared retrieval pipeline."""
    from app.services.retrieval_service import retrieve_knowledge_candidates

    candidates = retrieve_knowledge_candidates(query_text, user, limit=limit)
    return [_candidate_payload(candidate) for candidate in candidates]


def _candidate_payload(candidate):
    """Return the legacy knowledge chunk payload for a retrieval candidate."""
    metadata = dict(candidate.metadata or {})
    payload = {
        "type": "knowledge",
        "id": candidate.source_id,
        "chunk_id": metadata.get("chunk_id"),
        "title": candidate.title,
        "module": candidate.module,
        "url": candidate.url,
        "reason": candidate.explanation,
        "score": int(round(max(float(candidate.raw_score or 0), 0))),
        "context": candidate.content,
    }
    payload.update({key: value for key, value in metadata.items() if value not in (None, "")})
    return payload


def can_user_read_knowledge_document(user, document):
    """Return whether a user may use a knowledge document as RAG context."""
    return can_user_read_source_document(user, document)


def source_url(document):
    """Return a frontend route hint for a knowledge document source."""
    if document.relative_path and document.relative_path.startswith("/"):
        return document.relative_path
    urls = {
        "upload": "/admin/ai",
        "generated_document": "/documents",
        "error_entry": "/errors",
        "task": "/tasks",
        "machine": "/machines",
        "inventory_material": "/inventory",
        "maintenance_plan": "/machines",
        "machine_manual": "/documents",
        "shift_handover": "/handover",
        "manual_training": "/admin/ai/rag-board",
        "faq": "/admin/ai/prompt-faq",
    }
    return urls.get(document.source_type, "/admin/ai")


def knowledge_sources_for_chat(query_text, user):
    """Return context text and public source records for chat retrieval."""
    from app.services.retrieval_service import knowledge_context_for_chat

    return knowledge_context_for_chat(query_text, user, limit=MAX_RETRIEVAL_CHUNKS)


__all__ = [
    "search_knowledge_chunks",
    "can_user_read_knowledge_document",
    "source_url",
    "knowledge_sources_for_chat",
]
