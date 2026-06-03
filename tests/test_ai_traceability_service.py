"""Tests for AI answer traceability storage."""

from app.extensions import db
from app.models import AIAnswerTrace, AIAuditEvent, ChatMessage, Role
from app.services.ai_traceability_service import create_answer_trace


def test_create_answer_trace_stores_safe_chunk_metadata(app, make_user, monkeypatch):
    """Verify answer traces store scores and chunk refs without raw chunk text."""
    linked_traces = []
    monkeypatch.setattr(
        "app.services.ai_traceability_service.link_langfuse_answer_trace",
        lambda diagnostics, chat_message, trace: linked_traces.append(
            (diagnostics, chat_message.id, trace.answer_id),
        )
        or True,
    )
    monkeypatch.setattr(
        "app.services.ai_traceability_service.submit_automatic_eval_scores",
        lambda diagnostics, result: 0,
    )
    user = make_user(username="trace_chunk_admin", role=Role.MASTER_ADMIN)
    with app.app_context():
        audit_event = AIAuditEvent(
            user_id=user["id"],
            workflow="assistant",
            status="openai_used",
            provider="openai",
            model="gpt-5-mini",
            model_tier="balanced",
            input_tokens=120,
            output_tokens=40,
            cached_tokens=20,
            total_tokens=160,
            estimated_cost_usd=0.0123,
            source_count=1,
            confidence_score=82,
            confidence_level="high",
        )
        db.session.add(audit_event)
        db.session.flush()
        chat_message = ChatMessage(
            user_id=user["id"],
            message="Wie pruefe ich F-77?",
            response="Antwort",
            response_type="assistant",
            diagnostics_json="{}",
            source_count=1,
            confidence_score=82,
            confidence_level="high",
            audit_event_id=audit_event.id,
        )
        db.session.add(chat_message)
        db.session.commit()

        result = {
            "type": "assistant",
            "answer": "Antwort",
            "diagnostics": {
                "workflow": "chat",
                "provider": "openai",
                "model": "gpt-5-mini",
                "model_tier": "balanced",
                "input_tokens": 120,
                "output_tokens": 40,
                "cached_tokens": 20,
                "total_tokens": 160,
                "estimated_cost_usd": 0.0123,
                "confidence_score": 82,
                "confidence_level": "high",
                "langfuse_trace_id": "1234567890abcdef1234567890abcdef",
                "langfuse_observation_id": "fedcba0987654321",
            },
            "confidence": {"score": 82, "level": "high"},
            "sources": [
                {
                    "type": "knowledge",
                    "source_type": "manual_training",
                    "source_kind": "rag",
                    "id": 99,
                    "source_id": 15,
                    "document_id": 15,
                    "chunk_id": 99,
                    "chunk_index": 3,
                    "title": "F-77 Pruefung",
                    "score": 91.2,
                    "normalized_score": 0.83,
                    "explainability": {"semantic_similarity": 0.82},
                    "text": "Nicht speichern",
                    "content": "Nicht speichern",
                    "relative_path": "private/path.txt",
                },
            ],
        }

        trace = create_answer_trace(chat_message, result)

        saved = db.session.get(AIAnswerTrace, trace.id)
        serialized_sources = saved.sources()
        serialized_chunks = saved.chunks()
        assert result["answer_id"].startswith("ans_")
        assert saved.answer_id == result["answer_id"]
        assert saved.chat_message_id == chat_message.id
        assert saved.audit_event_id == audit_event.id
        assert saved.model == "gpt-5-mini"
        assert saved.total_tokens == 160
        assert saved.estimated_cost_usd == 0.0123
        assert saved.confidence_score == 82
        assert saved.source_count == 1
        assert saved.chunk_count == 1
        assert serialized_sources[0]["similarity_score"] == 0.83
        assert serialized_sources[0]["explainability"]["semantic_similarity"] == 0.82
        assert serialized_chunks[0]["chunk_id"] == 99
        assert serialized_chunks[0]["document_id"] == 15
        assert "text" not in serialized_sources[0]
        assert "content" not in serialized_sources[0]
        assert "relative_path" not in serialized_sources[0]
        assert linked_traces == [
            (
                result["diagnostics"],
                chat_message.id,
                result["answer_id"],
            ),
        ]
