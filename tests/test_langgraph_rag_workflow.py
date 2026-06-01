"""Tests for the LangGraph RAG orchestration layer."""

from types import SimpleNamespace

from app.services.query_classifier_service import (
    QUERY_TYPE_HYBRID,
    QueryClassificationResult,
)
from app.services.rag_service import answer_with_rag, build_rag_context


class RecordingProvider:
    """AI provider test double that records answer-generation inputs."""

    name = "recording"

    def __init__(self):
        """Initialize an empty call log."""
        self.calls = []

    def answer_question(self, question, context, workflow="chat", extra_rules=None):
        """Return a deterministic answer and record the prompt inputs."""
        self.calls.append(
            {
                "question": question,
                "context": context,
                "workflow": workflow,
                "extra_rules": extra_rules,
            },
        )
        return "Provider answer with source context."


def test_build_rag_context_uses_langgraph_node_contract(monkeypatch):
    """Verify context assembly preserves the existing RAG payload shape."""
    _patch_workflow_boundaries(monkeypatch)

    payload = build_rag_context(
        "Welche Stoerungen sind dringend?",
        SimpleNamespace(id=1, role="master_admin"),
        requested_scopes={"errors"},
    )

    assert payload["context"] == "Structured context\n\nKnowledge context"
    assert payload["rag"]["pipeline"] == [
        "question",
        "intent_classification",
        "structured_data_retrieval",
        "vector_retrieval",
        "context_assembly",
        "answer_generation",
        "validation",
        "trace_logging",
    ]
    assert payload["rag"]["query_classification"]["query_type"] == QUERY_TYPE_HYBRID
    assert payload["rag"]["source_count"] == 2
    assert payload["rag"]["knowledge_source_count"] == 1
    assert payload["rag"]["langgraph"]["fallback_active"] is True
    assert payload["rag"]["langgraph"]["completed_nodes"] == [
        "question",
        "intent_classification",
        "structured_data_retrieval",
        "vector_retrieval",
        "context_assembly",
        "trace_logging",
    ]


def test_answer_with_rag_runs_full_fallback_workflow(monkeypatch):
    """Verify the full workflow generates, validates, and traces an answer."""
    _patch_workflow_boundaries(monkeypatch)
    provider = RecordingProvider()

    result = answer_with_rag(
        "Welche Stoerungen sind dringend?",
        SimpleNamespace(id=1, role="master_admin"),
        requested_scopes={"errors"},
        provider=provider,
    )

    assert "Provider answer" in result["answer"]
    assert result["provider"] == "recording"
    assert result["sources"][0]["type"] == "error"
    assert result["rag"]["langgraph"]["completed_nodes"] == result["rag"]["pipeline"]
    assert result["rag"]["langgraph"]["fallback_active"] is True
    assert result["confidence"]["score"] >= 0
    assert provider.calls == [
        {
            "question": "Welche Stoerungen sind dringend?",
            "context": "Structured context\n\nKnowledge context",
            "workflow": "chat",
            "extra_rules": (
                "Use maintenance evidence. Trenne dokumentierte Ursache, "
                "Pruefung und empfohlene Massnahme klar."
            ),
        },
    ]


def test_answer_with_rag_uses_compiled_langgraph_when_available(monkeypatch):
    """Verify an available compiled graph is used before the fallback runner."""
    _patch_workflow_boundaries(monkeypatch)
    calls = []

    class FakeCompiledGraph:
        """Minimal compiled graph test double."""

        def invoke(self, state):
            """Run the fallback sequence while recording graph usage."""
            calls.append(state["message"])
            state["workflow_engine"] = "langgraph"
            return workflow_module._run_fallback_workflow(state)

    from app.services import langgraph_rag_workflow as workflow_module

    monkeypatch.setattr(workflow_module, "_compiled_langgraph", lambda: FakeCompiledGraph())
    monkeypatch.setattr(workflow_module, "_workflow_engine_name", lambda: "langgraph")

    result = answer_with_rag(
        "Welche Stoerungen sind dringend?",
        SimpleNamespace(id=1, role="master_admin"),
        provider=RecordingProvider(),
    )

    assert calls == ["Welche Stoerungen sind dringend?"]
    assert result["rag"]["langgraph"]["engine"] == "langgraph"
    assert result["rag"]["langgraph"]["fallback_active"] is False


def _patch_workflow_boundaries(monkeypatch):
    """Patch expensive workflow boundaries with deterministic test doubles."""
    from app.services import langgraph_rag_workflow as workflow_module

    monkeypatch.setattr(workflow_module, "_compiled_langgraph", lambda: None)
    monkeypatch.setattr(workflow_module, "_workflow_engine_name", lambda: "fallback")
    monkeypatch.setattr(workflow_module, "is_rag_enabled", lambda: True)
    monkeypatch.setattr(
        workflow_module,
        "classify_ai_query",
        lambda message: QueryClassificationResult(
            query_type=QUERY_TYPE_HYBRID,
            extracted_keywords=["stoerungen"],
            suggested_sources=["errors", "knowledge"],
        ),
    )
    monkeypatch.setattr(workflow_module, "retrieve_context", _fake_retrieve_context)


def _fake_retrieve_context(
    message,
    user,
    requested_scopes=None,
    conversation_context=None,
    query_classification=None,
):
    """Return a deterministic retrieval payload for workflow tests."""
    assert message == "Welche Stoerungen sind dringend?"
    assert query_classification.query_type == QUERY_TYPE_HYBRID
    return {
        "context": "Structured context\n\nKnowledge context",
        "sources": [
            {
                "type": "error",
                "id": 7,
                "title": "Kritische Stoerung",
                "score": 88,
            },
            {
                "type": "knowledge",
                "id": 4,
                "title": "Stoerungsanleitung",
                "score": 91,
                "quality_status": "admin_approved",
            },
        ],
        "data": {"errors": [{"id": 7}], "knowledge": [{"id": 4}]},
        "requested_scopes": requested_scopes or {"errors", "knowledge"},
        "allowed_scopes": {"errors", "knowledge"},
        "query_understanding": {
            "query_type": "error_analysis",
            "retrieval_strategy": {"prompt_rules": ["Use maintenance evidence."]},
        },
        "safety": {"safety_relevant": False},
        "conflicts": {"has_conflicts": False},
        "context_builder": {"sections": ["structured", "knowledge"]},
        "knowledge_links": {"links": []},
        "timeline_context": {},
        "retrieval_duration_ms": 12,
        "retrieval_debug": {"keyword_fallback_used": False},
    }
