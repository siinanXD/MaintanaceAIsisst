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
from app.services.source_visibility_policy import can_user_read_source_document
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


def search_knowledge_chunks(query_text, user, limit=MAX_RETRIEVAL_CHUNKS):
    """Return ranked knowledge chunks visible to the given user."""
    query_tokens = tokens(query_text)
    if not query_tokens:
        return []
    scorer = HybridRetrievalScorer(query_text=query_text)

    chunks = (
        KnowledgeChunk.query.join(KnowledgeDocument)
        .filter(KnowledgeDocument.status == "indexed")
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeChunk.chunk_index.asc())
        .limit(300)
        .all()
    )
    ranked = []
    for chunk in chunks:
        document = chunk.document
        if not can_user_read_knowledge_document(user, document):
            continue
        overlap = query_tokens & tokens(chunk.token_text or chunk.text)
        if not overlap:
            continue
        score = scorer.score_text_result(
            text=chunk.text,
            document=document,
            chunk_id=chunk.id,
            token_text=chunk.token_text,
        )
        if not score.allowed or score.final_score <= 0:
            continue
        ranked.append((score.final_score, chunk))
    ranked.sort(key=lambda item: (item[0], item[1].document.updated_at), reverse=True)
    return [chunk_payload(chunk, score) for score, chunk in ranked[:limit]]


def can_user_read_knowledge_document(user, document):
    """Return whether a user may use a knowledge document as RAG context."""
    return can_user_read_source_document(user, document)


def chunk_payload(chunk, score):
    """Return an internal retrieval payload for one chunk."""
    document = chunk.document
    payload = {
        "type": "knowledge",
        "id": document.id,
        "chunk_id": chunk.id,
        "title": document.title,
        "module": "knowledge",
        "url": source_url(document),
        "reason": f"{int(score)} lokale Wissens-Trefferpunkte",
        "score": int(score),
        "context": chunk.text,
    }
    payload.update(stored_chunk_metadata(chunk))
    return payload


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
    "chunk_payload",
    "source_url",
    "knowledge_sources_for_chat",
]
