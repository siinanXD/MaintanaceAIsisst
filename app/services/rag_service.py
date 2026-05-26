"""RAG orchestration for AI-native maintenance assistant workflows."""

from app.services.ai_confidence_service import attach_confidence_to_result
from app.services.ai_safety_service import (
    apply_post_generation_safety_to_result,
    enforce_post_generation_safety,
)
from app.services.ai_service import get_ai_provider
from app.services.query_classifier_service import classify_ai_query
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
    query_classification = classify_ai_query(message)
    retrieval = retrieve_context(
        message,
        user,
        requested_scopes,
        conversation_context=conversation_context,
        query_classification=query_classification,
    )
    retrieval["rag"] = {
        "enabled": is_rag_enabled(),
        "pipeline": list(RAG_PIPELINE_STEPS),
        "source_count": len(retrieval.get("sources") or []),
        "knowledge_source_count": _knowledge_source_count(retrieval.get("sources") or []),
        "explainability": retrieval_explainability_summary(retrieval.get("sources") or []),
        "query_understanding": retrieval.get("query_understanding") or {},
        "query_classification": query_classification.to_dict(),
        "safety": retrieval.get("safety") or {},
        "conflicts": retrieval.get("conflicts") or {},
        "context_builder": retrieval.get("context_builder") or {},
        "knowledge_links": retrieval.get("knowledge_links") or {},
        "incident_timeline": retrieval.get("timeline_context") or {},
        "retrieval_duration_ms": retrieval.get("retrieval_duration_ms", 0),
        "retrieval_debug": retrieval.get("retrieval_debug") or {},
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
    answer = ai_provider.answer_question(
        message,
        retrieval["context"],
        extra_rules=_prompt_rules_for_retrieval(retrieval),
    )
    result = attach_confidence_to_result(
        message,
        {
            "answer": answer,
            "sources": retrieval["sources"],
            "data": retrieval["data"],
            "rag": retrieval["rag"],
            "provider": getattr(ai_provider, "name", "unknown"),
        },
    )
    post_safety = enforce_post_generation_safety(
        result.get("answer"),
        retrieval["rag"].get("safety"),
    )
    return apply_post_generation_safety_to_result(result, post_safety)


def _knowledge_source_count(sources):
    """Return how many retrieved sources came from RAG knowledge chunks."""
    return sum(1 for source in sources if source.get("type") == "knowledge")


def _prompt_rules_for_retrieval(retrieval):
    """Return query-type-specific prompt rules from retrieval strategy metadata."""
    understanding = retrieval.get("query_understanding") or {}
    strategy = understanding.get("retrieval_strategy") or {}
    rules = [str(rule).strip() for rule in strategy.get("prompt_rules") or [] if rule]
    query_type = str(understanding.get("query_type") or "")
    if query_type == "error_analysis":
        rules.append("Trenne dokumentierte Ursache, Pruefung und empfohlene Massnahme klar.")
    elif query_type == "safety_question":
        rules.append("Bei Sicherheitsfragen nur quellenbasierte, vorsichtige Hinweise geben.")
    elif query_type == "document_question":
        rules.append("Nenne Dokument, Abschnitt oder Chunk, wenn diese Hinweise im Kontext stehen.")
    return " ".join(dict.fromkeys(rules))
