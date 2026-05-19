"""Tests for vector-store drift and synchronization observability."""

import pytest

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import KnowledgeChunk, KnowledgeDocument, Role
from app.services.knowledge_service import knowledge_index_status
from app.services.vector_sync_status_service import (
    clear_vector_sync_observability,
    record_vector_sync_failure,
)


@pytest.fixture(autouse=True)
def clear_vector_sync_state():
    """Keep in-process vector sync telemetry isolated per test."""
    clear_vector_sync_observability()
    yield
    clear_vector_sync_observability()


def test_vector_store_status_detects_stale_documents(app):
    """Verify stale documents are visible and trigger a reindex recommendation."""
    with app.app_context():
        _create_knowledge_document(
            title="VS900 stale source",
            status="stale",
            chunk_count=1,
            chunk_rows=0,
        )
        db.session.commit()

        vector_status = knowledge_index_status()["vector_store"]

    assert vector_status["stale_document_count"] == 1
    assert vector_status["pending_reindex_count"] == 1
    assert vector_status["reindex_recommended"] is True
    assert "stale_documents" in vector_status["reindex_reasons"]
    assert vector_status["stale_documents"][0]["source_type"] == "upload"
    assert "title" not in vector_status["stale_documents"][0]


def test_vector_store_status_detects_declared_chunk_mismatch(app):
    """Verify declared chunk counts and persisted chunks are compared."""
    with app.app_context():
        document = _create_knowledge_document(
            title="VS901 chunk mismatch",
            status="indexed",
            chunk_count=2,
            chunk_rows=1,
        )
        db.session.commit()

        vector_status = knowledge_index_status()["vector_store"]

    mismatch = vector_status["chunk_mismatches"][0]
    assert vector_status["chunk_mismatch_count"] == 1
    assert vector_status["chunk_vector_count_mismatch"] is True
    assert vector_status["reindex_recommended"] is True
    assert "chunk_count_mismatch" in vector_status["reindex_reasons"]
    assert mismatch["id"] == document.id
    assert mismatch["declared_chunk_count"] == 2
    assert mismatch["db_chunk_count"] == 1


def test_vector_store_status_detects_missing_chunks(app):
    """Verify indexed documents without persisted chunks are reported."""
    with app.app_context():
        document = _create_knowledge_document(
            title="VS902 missing chunks",
            status="indexed",
            chunk_count=1,
            chunk_rows=0,
        )
        db.session.commit()

        vector_status = knowledge_index_status()["vector_store"]

    missing = vector_status["missing_chunks"][0]
    assert vector_status["missing_chunk_count"] == 1
    assert vector_status["reindex_recommended"] is True
    assert "missing_chunks" in vector_status["reindex_reasons"]
    assert missing["id"] == document.id
    assert missing["declared_chunk_count"] == 1
    assert missing["db_chunk_count"] == 0


def test_vector_store_status_exposes_sync_failures_without_content(app):
    """Verify external sync failures are visible without document text or titles."""
    with app.app_context():
        record_vector_sync_failure(
            document_id=321,
            store_name="chroma",
            error=RuntimeError("sync failed for backend"),
        )

        vector_status = knowledge_index_status()["vector_store"]

    failure = vector_status["sync_failures"][0]
    assert vector_status["vector_sync_failure_count"] == 1
    assert vector_status["last_failed_sync"]["document_id"] == 321
    assert vector_status["reindex_recommended"] is True
    assert "vector_sync_failures" in vector_status["reindex_reasons"]
    assert failure["store"] == "chroma"
    assert "document_text" not in failure
    assert "title" not in failure


def test_vector_store_status_works_when_rag_is_disabled(app):
    """Verify RAG-disabled status still reports structured index diagnostics."""
    app.config["RAG_ENABLED"] = False
    with app.app_context():
        _create_knowledge_document(
            title="VS903 rag disabled",
            status="indexed",
            chunk_count=1,
            chunk_rows=1,
        )
        db.session.commit()

        status = knowledge_index_status()

    assert status["diagnostics"]["rag_enabled"] is False
    assert status["vector_store"]["store"] == "local_knowledge"
    assert status["vector_store"]["expected_vector_count"] == 1
    assert status["vector_store"]["reindex_recommended"] is False


def test_admin_knowledge_status_includes_vector_observability(
    client,
    make_user,
    auth_headers,
):
    """Verify the admin status endpoint exposes vector drift metadata."""
    admin = make_user(
        username="vector_status_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with client.application.app_context():
        _create_knowledge_document(
            title="VS904 admin status",
            status="indexed",
            chunk_count=1,
            chunk_rows=1,
        )
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    vector_status = payload["vector_store"]
    assert response.status_code == 200
    assert vector_status["store"] == "local_knowledge"
    assert vector_status["expected_vector_count"] == 1
    assert vector_status["missing_chunk_count"] == 0
    assert vector_status["privacy"]["exposes_document_text"] is False


def _create_knowledge_document(
    *,
    title,
    status,
    chunk_count,
    chunk_rows,
    source_type="upload",
):
    """Create one knowledge document with a controlled chunk-count shape."""
    now = utc_now()
    document = KnowledgeDocument(
        source_type=source_type,
        title=title,
        original_filename=f"{title}.txt",
        relative_path=f"knowledge/{title}.txt",
        content_type="text/plain",
        department="Produktion",
        status=status,
        quality_status="admin_approved",
        is_public=True,
        chunk_count=chunk_count,
        created_at=now,
        updated_at=now,
    )
    db.session.add(document)
    db.session.flush()
    for index in range(chunk_rows):
        db.session.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                text=f"{title} chunk {index}",
                token_text=f"{title.lower()} chunk {index}",
                created_at=now,
            )
        )
    return document
