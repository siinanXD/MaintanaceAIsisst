"""RAG orchestration for AI-native maintenance assistant workflows."""

from app.services.ai_confidence_service import attach_confidence_to_result
from app.services.ai_service import get_ai_provider
from app.services.retrieval_explainability_service import retrieval_explainability_summary
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


def build_rag_context(message, user, requested_scopes=None, conversation_context=None):
    """Return retrieved context, sources, and RAG diagnostics for a question."""
    retrieval = retrieve_context(
        message,
        user,
        requested_scopes,
        conversation_context=conversation_context,
    )
    retrieval["rag"] = {
        "enabled": is_rag_enabled(),
        "pipeline": list(RAG_PIPELINE_STEPS),
        "source_count": len(retrieval.get("sources") or []),
        "knowledge_source_count": _knowledge_source_count(retrieval.get("sources") or []),
        "explainability": retrieval_explainability_summary(retrieval.get("sources") or []),
        "query_understanding": retrieval.get("query_understanding") or {},
        "safety": retrieval.get("safety") or {},
        "conflicts": retrieval.get("conflicts") or {},
        "context_builder": retrieval.get("context_builder") or {},
        "knowledge_links": retrieval.get("knowledge_links") or {},
        "incident_timeline": retrieval.get("timeline_context") or {},
        "retrieval_duration_ms": retrieval.get("retrieval_duration_ms", 0),
    }
    if conversation_context is not None:
        retrieval["rag"]["conversation_context"] = conversation_context.diagnostics()
    return retrieval


def answer_with_rag(
    message,
    user,
    requested_scopes=None,
    provider=None,
    conversation_context=None,
):
    """Generate an answer with retrieved context and source metadata."""
    retrieval = build_rag_context(
        message,
        user,
        requested_scopes,
        conversation_context=conversation_context,
    )
    ai_provider = provider or get_ai_provider()
    answer = ai_provider.answer_question(message, retrieval["context"])
    return attach_confidence_to_result(
        message,
        {
            "answer": answer,
            "sources": retrieval["sources"],
            "data": retrieval["data"],
            "rag": retrieval["rag"],
            "provider": getattr(ai_provider, "name", "unknown"),
        },
    )


def _knowledge_source_count(sources):
    """Return how many retrieved sources came from RAG knowledge chunks."""
    return sum(1 for source in sources if source.get("type") == "knowledge")
