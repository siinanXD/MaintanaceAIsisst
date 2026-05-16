"""RAG orchestration for AI-native maintenance assistant workflows."""

from app.services.ai_service import get_ai_provider
from app.services.retrieval_service import is_rag_enabled, retrieve_context

RAG_PIPELINE_STEPS = [
    "capture_data",
    "chunk_text",
    "create_embeddings",
    "store_vectors",
    "retrieve_chunks",
    "build_context",
    "generate_answer_with_sources",
]


def build_rag_context(message, user, requested_scopes=None):
    """Return retrieved context, sources, and RAG diagnostics for a question."""
    retrieval = retrieve_context(message, user, requested_scopes)
    retrieval["rag"] = {
        "enabled": is_rag_enabled(),
        "pipeline": list(RAG_PIPELINE_STEPS),
        "source_count": len(retrieval.get("sources") or []),
        "knowledge_source_count": _knowledge_source_count(retrieval.get("sources") or []),
    }
    return retrieval


def answer_with_rag(message, user, requested_scopes=None, provider=None):
    """Generate an answer with retrieved context and source metadata."""
    retrieval = build_rag_context(message, user, requested_scopes)
    ai_provider = provider or get_ai_provider()
    answer = ai_provider.answer_question(message, retrieval["context"])
    return {
        "answer": answer,
        "sources": retrieval["sources"],
        "data": retrieval["data"],
        "rag": retrieval["rag"],
        "provider": getattr(ai_provider, "name", "unknown"),
    }


def _knowledge_source_count(sources):
    """Return how many retrieved sources came from RAG knowledge chunks."""
    return sum(1 for source in sources if source.get("type") == "knowledge")
