"""Tests for the modular RAG service layer."""

import math

import pytest

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import KnowledgeChunk, KnowledgeDocument, Role, User
from app.services.chunking_service import ChunkingConfig, chunk_text
from app.services.embedding_service import HashingEmbeddingProvider
from app.services.retrieval_service import knowledge_context_for_chat


def test_chunk_text_preserves_metadata_and_overlap():
    """Verify chunking returns metadata-ready overlapping chunks."""
    text = "Hydraulikfilter X900 taeglich pruefen. " * 25
    chunks = chunk_text(
        text,
        metadata={"machine_id": 7, "document_type": "manual"},
        config=ChunkingConfig(max_chars=240, overlap=40, max_chunks=10),
    )

    assert len(chunks) > 1
    assert chunks[0]["metadata"]["machine_id"] == 7
    assert chunks[0]["metadata"]["document_type"] == "manual"
    assert chunks[0]["metadata"]["chunk_index"] == 0
    assert "Hydraulikfilter" in chunks[1]["text"]


def test_chunk_text_rejects_invalid_overlap():
    """Verify invalid chunking settings fail explicitly."""
    with pytest.raises(ValueError, match="overlap"):
        chunk_text(
            "kurzer Text",
            config=ChunkingConfig(max_chars=240, overlap=240),
        )


def test_hashing_embedding_provider_is_stable_and_normalized():
    """Verify local embeddings are deterministic and normalized."""
    provider = HashingEmbeddingProvider(dimensions=64)

    first = provider.embed_text("Hydraulikfilter X900 pruefen")
    second = provider.embed_text("Hydraulikfilter X900 pruefen")

    assert first == second
    assert len(first) == 64
    assert math.isclose(sum(value * value for value in first), 1.0)


def test_rag_knowledge_context_respects_document_permissions(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify RAG knowledge retrieval is permission-aware."""
    user_data = make_user(
        username="rag_context_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked_data = make_user(
        username="rag_context_blocked",
        role=Role.PRODUKTION,
        department_name="Instandhaltung",
    )
    set_dashboard_permission(user_data["username"], "documents", can_view=True)
    set_dashboard_permission(blocked_data["username"], "documents", can_view=False)

    with app.app_context():
        user = db.session.get(User, user_data["id"])
        blocked = db.session.get(User, blocked_data["id"])
        document = KnowledgeDocument(
            source_type="upload",
            title="Hydraulikfilter X900",
            original_filename="manual.txt",
            relative_path="uploads/manual.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            is_public=True,
            chunk_count=1,
            created_by=user.id,
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        db.session.add(document)
        db.session.flush()
        db.session.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                text="Hydraulikfilter X900 muss taeglich geprueft werden.",
                token_text="hydraulikfilter x900 taeglich pruefen",
                created_at=utc_now(),
            )
        )
        db.session.commit()

        context, sources = knowledge_context_for_chat("Hydraulikfilter X900", user)
        blocked_context, blocked_sources = knowledge_context_for_chat(
            "Hydraulikfilter X900",
            blocked,
        )

    assert "Hydraulikfilter X900" in context
    assert sources[0]["type"] == "knowledge"
    assert blocked_context == ""
    assert blocked_sources == []
