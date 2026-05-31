"""Local text knowledge base for AI retrieval."""
# ruff: noqa: F401, F821

import json
import logging
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import (
    AssistantTrainingEntry,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeChunk,
    KnowledgeDocument,
    Machine,
    MachineManual,
    MaintenancePlan,
    ShiftHandover,
    Task,
)
from app.services.chunking_service import (
    ChunkingConfig,
)
from app.services.chunking_service import (
    chunk_text as build_text_chunks,
)
from app.services.document_service import (
    document_path,
    extract_manual_text,
    html_to_text,
)
from app.services.knowledge_quality_service import (
    automatic_quality_status_from_chunk_report,
    default_quality_status_for_source,
    mark_quality_outdated_if_reviewed,
    retrieval_quality_gate_for_document,
)
from app.services.knowledge_source_quality_service import (
    aggregate_chunk_quality_reports,
    chunk_quality_report_for_document,
    filter_quality_chunks,
    latest_chunk_quality_summary,
    remember_chunk_quality_report,
    reset_chunk_quality_reports,
)
from app.services.retrieval_scoring_service import HybridRetrievalScorer
from app.services.source_visibility_policy import (
    can_user_read_source_document,
    source_role_visibility_label,
)
from app.services.technical_entity_service import (
    entities_to_json,
    entity_token_text,
    extract_technical_entities,
    load_technical_entity_catalog,
)
from app.services.text_normalization_service import tokenize_text
from app.services.vector_sync_status_service import (
    record_vector_sync_failure,
    record_vector_sync_success,
    vector_store_drift_status,
)

logger = logging.getLogger(__name__)

ALLOWED_KNOWLEDGE_EXTENSIONS = {".pdf", ".txt", ".html", ".htm"}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_RETRIEVAL_CHUNKS = 4
STRUCTURED_SOURCE_TYPES = (
    "error_entry",
    "task",
    "machine",
    "inventory_material",
    "maintenance_plan",
    "machine_manual",
    "shift_handover",
    "manual_training",
    "faq",
)


def rebuild_chunks(document, text):
    """Replace all chunks for a knowledge document."""
    KnowledgeChunk.query.filter(KnowledgeChunk.document_id == document.id).delete()
    chunks, quality_report = filter_quality_chunks(build_text_chunks(text))
    remember_chunk_quality_report(document.id, quality_report)
    document.quality_status = automatic_quality_status_from_chunk_report(
        document,
        quality_report,
    )
    provider = None
    embeddings = []
    if chunks:
        try:
            provider, embeddings = _chunk_embeddings(
                [_chunk_payload_text(chunk_payload) for chunk_payload in chunks]
            )
        except Exception as exc:
            _mark_embedding_failure(document, exc)
            return
    chunk_objects = []
    entity_catalog = load_technical_entity_catalog()
    source_metadata = document_entity_metadata(document)
    for index, chunk_payload in enumerate(chunks):
        chunk = _chunk_payload_text(chunk_payload)
        chunk_metadata = _chunk_payload_metadata(chunk_payload, index)
        chunk_metadata.setdefault("chunking_mode", _configured_chunking_mode())
        if provider is not None:
            chunk_metadata["embedding_model"] = _embedding_model_label(provider)
        entities = extract_technical_entities(
            chunk,
            metadata={**source_metadata, **chunk_metadata},
            catalog=entity_catalog,
        )
        chunk_object = KnowledgeChunk(
            document_id=document.id,
            chunk_index=index,
            text=chunk,
            token_text=" ".join(
                sorted(
                    tokens(
                        f"{chunk} {entity_token_text(entities)} "
                        f"{chunk_metadata.get('section_title', '')}",
                    )
                ),
            ),
            entities_json=_entities_to_json_with_chunk_metadata(
                entities,
                chunk_metadata,
            ),
            embedding=embeddings[index] if index < len(embeddings) else None,
            created_at=utc_now(),
        )
        db.session.add(chunk_object)
        chunk_objects.append(chunk_object)
    db.session.flush()
    document.chunk_count = len(chunks)
    sync_vector_store_document(document, chunk_objects)


def _chunk_embeddings(texts):
    """Return the configured embedding provider and one embedding per chunk text."""
    from app.services.embedding_service import get_embedding_provider

    provider = get_embedding_provider()
    embeddings = provider.embed_texts(texts)
    if len(embeddings) != len(texts):
        raise RuntimeError("Embedding provider returned an unexpected vector count")
    return provider, embeddings


def _mark_embedding_failure(document, error):
    """Mark a knowledge document as failed when embeddings cannot be created."""
    document.status = "error"
    document.error_message = "Embedding provider failed during chunk indexing"
    document.chunk_count = 0
    logger.exception(
        "knowledge_embedding_failed document_id=%s error=%s",
        getattr(document, "id", None),
        error,
    )
    record_vector_sync_failure(document.id, _configured_vector_store_name(), error)
    db.session.flush()


def _configured_chunking_mode():
    """Return the configured chunking mode for chunk metadata."""
    return str(current_app.config.get("RAG_CHUNKING_MODE", "hybrid_semantic"))


def _configured_vector_store_name():
    """Return the configured vector store name for diagnostics."""
    return str(current_app.config.get("RAG_VECTOR_STORE", "pgvector")).lower()


def _embedding_model_label(provider):
    """Return a compact embedding model/provider label for chunk metadata."""
    model = getattr(provider, "model", "")
    if model:
        return str(model)[:180]
    return str(getattr(provider, "name", "unknown"))[:180]


def sync_vector_store_document(document, chunks):
    """Persist indexed chunks in the configured external vector store when enabled."""
    try:
        from app.services.vector_store_service import (
            VectorRecord,
            get_vector_store,
        )
    except ImportError as exc:
        record_vector_sync_failure(document.id, "unavailable", exc)
        logger.warning("vector_store_import_failed document_id=%s error=%s", document.id, exc)
        return

    store = get_vector_store()
    if getattr(store, "name", "") == "pgvector":
        if all(getattr(chunk, "embedding", None) is not None for chunk in chunks):
            record_vector_sync_success(document.id, store.name, len(chunks))
        else:
            record_vector_sync_failure(
                document.id,
                store.name,
                RuntimeError("One or more knowledge chunks are missing embeddings"),
            )
        return
    if getattr(store, "name", "") != "chroma":
        configured_store = str(current_app.config.get("RAG_VECTOR_STORE", "local")).lower()
        if configured_store == "chroma":
            record_vector_sync_failure(
                document.id,
                "chroma",
                RuntimeError("Configured Chroma vector store fell back to local search"),
            )
        return
    try:
        store.delete_document(document.id)
        store.add_documents(
            [
                VectorRecord(
                    text=chunk.text,
                    record_id=f"knowledge:{document.id}:{chunk.chunk_index}",
                    metadata=chunk_vector_metadata(document, chunk),
                )
                for chunk in chunks
            ]
        )
        record_vector_sync_success(document.id, store.name, len(chunks))
    except Exception as exc:
        record_vector_sync_failure(document.id, getattr(store, "name", ""), exc)
        logger.warning("vector_store_sync_failed document_id=%s error=%s", document.id, exc)


def chunk_vector_metadata(document, chunk):
    """Return metadata stored with an external vector record."""
    quality_gate = retrieval_quality_gate_for_document(document)
    entities = chunk.entities()
    source_created_at = structured_source_created_at(document)
    metadata = {
        "type": "knowledge",
        "id": document.id,
        "chunk_id": chunk.id,
        "chunk_index": chunk.chunk_index,
        "title": document.title,
        "module": "knowledge",
        "source_type": document.source_type,
        "source_id": document.source_id,
        "document_type": document.source_type,
        "department": document.department,
        "machine_id": structured_source_machine_id(document),
        "role_visibility": source_role_visibility_label(document),
        "created_at": source_created_at or document.created_at.isoformat(),
        "url": source_url(document),
        "updated_at": document.updated_at.isoformat() if document.updated_at else "",
        "quality_status": quality_gate.status,
        "quality_gate": quality_gate.reason,
        "quality_score_multiplier": quality_gate.score_multiplier,
        "technical_entities": entities,
        "technical_entities_json": entities_to_json(entities),
    }
    metadata.update(_public_source_entity_metadata(document_entity_metadata(document)))
    metadata.update(stored_chunk_metadata(chunk))
    return metadata


def chunk_text(text, max_chars=1400, overlap=160):
    """Split text into stable overlapping chunks."""
    config = ChunkingConfig(max_chars=max_chars, overlap=overlap)
    return [chunk["text"] for chunk in build_text_chunks(text, config=config)]


def tokens(value):
    """Return normalized searchable tokens."""
    return set(tokenize_text(value))


def reindex_all_knowledge():
    """Register and reindex all supported RAG knowledge documents."""
    reset_chunk_quality_reports()
    ensure_generated_documents_registered()
    ensure_structured_sources_registered()
    documents = KnowledgeDocument.query.order_by(KnowledgeDocument.id.asc()).all()
    for document in documents:
        index_knowledge_document(document)
    db.session.commit()
    chunk_quality = aggregate_chunk_quality_reports(
        chunk_quality_report_for_document(document.id) for document in documents
    )
    return {
        "documents": len(documents),
        "indexed": sum(1 for document in documents if document.status == "indexed"),
        "chunks": sum(document.chunk_count for document in documents),
        "sources": source_type_counts(documents),
        "chunk_quality": chunk_quality,
    }


def reindex_stale_knowledge():
    """Reindex only stale and pending knowledge documents."""
    reset_chunk_quality_reports()
    ensure_generated_documents_registered()
    ensure_structured_sources_registered()
    documents = (
        KnowledgeDocument.query.filter(KnowledgeDocument.status.in_(("pending", "stale")))
        .order_by(KnowledgeDocument.id.asc())
        .all()
    )
    for document in documents:
        index_knowledge_document(document)
    db.session.commit()
    chunk_quality = aggregate_chunk_quality_reports(
        chunk_quality_report_for_document(document.id) for document in documents
    )
    return {
        "documents": len(documents),
        "indexed": sum(1 for document in documents if document.status == "indexed"),
        "chunks": sum(document.chunk_count for document in documents),
        "sources": source_type_counts(documents),
        "chunk_quality": chunk_quality,
    }


def reindex_knowledge_document(document):
    """Reindex one knowledge document and commit the result."""
    index_knowledge_document(document)
    db.session.commit()
    result = document.to_dict()
    result["chunk_quality"] = chunk_quality_report_for_document(document.id).to_dict()
    return result


__all__ = [
    "rebuild_chunks",
    "sync_vector_store_document",
    "chunk_vector_metadata",
    "chunk_text",
    "tokens",
    "reindex_all_knowledge",
    "reindex_stale_knowledge",
    "reindex_knowledge_document",
]
