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


def list_knowledge_documents(args):
    """Return filtered knowledge documents for admin views."""
    query = KnowledgeDocument.query
    q = str(args.get("q") or "").strip()
    status = str(args.get("status") or "").strip()
    quality_status = str(args.get("quality_status") or "").strip()
    source_type = str(args.get("source_type") or "").strip()
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (KnowledgeDocument.title.ilike(pattern))
            | (KnowledgeDocument.original_filename.ilike(pattern))
            | (KnowledgeDocument.department.ilike(pattern))
        )
    if status:
        query = query.filter(KnowledgeDocument.status == status)
    if quality_status:
        query = query.filter(KnowledgeDocument.quality_status == quality_status)
    if source_type:
        query = query.filter(KnowledgeDocument.source_type == source_type)
    return query.order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())


def knowledge_index_status():
    """Return admin-facing RAG index status and searchable source diagnostics."""
    from app.services.knowledge_lifecycle_service import knowledge_lifecycle_overview

    documents = KnowledgeDocument.query.order_by(KnowledgeDocument.id.asc()).all()
    status_counts = {}
    source_counts = {}
    searchable_by_source = {}
    chunks_by_source = {}
    for document in documents:
        source_type = document.source_type
        status_counts[document.status] = status_counts.get(document.status, 0) + 1
        source_counts[source_type] = source_counts.get(source_type, 0) + 1
        chunks_by_source[source_type] = chunks_by_source.get(source_type, 0) + (
            document.chunk_count or 0
        )
        if document.status == "indexed" and document.chunk_count > 0:
            searchable_by_source[source_type] = searchable_by_source.get(source_type, 0) + 1

    indexed = status_counts.get("indexed", 0)
    errors = status_counts.get("error", 0)
    total_chunks = sum(document.chunk_count or 0 for document in documents)
    lifecycle = knowledge_lifecycle_overview(documents)
    vector_status = vector_store_drift_status(documents)
    readiness_score, readiness_reasons = _rag_readiness(
        documents=documents,
        indexed=indexed,
        errors=errors,
        total_chunks=total_chunks,
        vector_status=vector_status,
    )
    return {
        "documents": len(documents),
        "indexed": indexed,
        "stale": status_counts.get("stale", 0),
        "pending": status_counts.get("pending", 0),
        "searchable_documents": sum(searchable_by_source.values()),
        "chunks": total_chunks,
        "status_counts": status_counts,
        "source_counts": source_counts,
        "searchable_by_source": searchable_by_source,
        "chunks_by_source": chunks_by_source,
        "source_types": _knowledge_source_type_diagnostics(
            source_counts,
            searchable_by_source,
            chunks_by_source,
        ),
        "readiness_score": readiness_score,
        "readiness_reasons": readiness_reasons,
        "problem_documents": _problem_knowledge_documents(documents),
        "lifecycle": lifecycle,
        "aging": lifecycle.get("aging", {}),
        "vector_store": vector_status,
        "chunk_quality": latest_chunk_quality_summary(),
        "diagnostics": {
            "rag_enabled": bool(current_app.config.get("RAG_ENABLED", True)),
            "vector_store": current_app.config.get("RAG_VECTOR_STORE", "local"),
            "embedding_provider": current_app.config.get("EMBEDDING_PROVIDER", "openai"),
            "chunk_size": current_app.config.get("RAG_CHUNK_SIZE", 1400),
            "chunk_overlap": current_app.config.get("RAG_CHUNK_OVERLAP", 160),
            "top_k": current_app.config.get("RAG_TOP_K", 4),
            "scan_limit": current_app.config.get("RAG_SCAN_LIMIT", 300),
            "has_errors": errors > 0,
            "ready": bool(indexed and total_chunks and current_app.config.get("RAG_ENABLED", True)),
        },
    }


def _rag_readiness(documents, indexed, errors, total_chunks, vector_status=None):
    """Return a RAG readiness score and admin-facing reasons."""
    vector_status = vector_status or {}
    if not current_app.config.get("RAG_ENABLED", True):
        return 0, ["RAG ist deaktiviert."]
    if not documents:
        return 0, ["Keine Wissensdokumente indexiert."]

    stale = sum(1 for document in documents if document.status == "stale")
    pending = sum(1 for document in documents if document.status == "pending")
    no_text = sum(1 for document in documents if document.status == "no_text")
    score = 100
    reasons = []
    if not indexed or not total_chunks:
        score = min(score, 30)
        reasons.append("Keine durchsuchbaren RAG-Chunks vorhanden.")
    if errors:
        score -= min(40, round((errors / len(documents)) * 100))
        reasons.append(f"{errors} Wissensdokumente haben Indexfehler.")
    if stale:
        score -= min(25, round((stale / len(documents)) * 60))
        reasons.append(f"{stale} Wissensdokumente sind veraltet.")
    if pending:
        score -= min(20, round((pending / len(documents)) * 50))
        reasons.append(f"{pending} Wissensdokumente warten auf Indexierung.")
    if no_text:
        score -= min(15, round((no_text / len(documents)) * 40))
        reasons.append(f"{no_text} Wissensdokumente enthalten keinen lesbaren Text.")
    if vector_status.get("fallback_active"):
        score = min(score, 20)
        reasons.append("Konfigurierter Vector Store ist im Fallback-Modus aktiv.")
    if vector_status.get("atlas_reindex_required"):
        score = min(score, 25)
        reasons.append("Atlas erfordert eine vollstaendige Reindexierung oder Resync.")
    if vector_status.get("chunk_vector_count_mismatch"):
        score = min(score, 35)
        reasons.append("Vector-Store-Drift zwischen SQL-Chunks und externen Vektoren erkannt.")
    if not reasons:
        reasons.append("RAG-Index ist bereit.")
    return max(0, min(100, score)), reasons


def _problem_knowledge_documents(documents, limit=10):
    """Return recent knowledge documents that need admin attention."""
    problem_statuses = {"error", "stale", "pending", "no_text"}
    problem_documents = [document for document in documents if document.status in problem_statuses]
    problem_documents.sort(key=lambda document: document.updated_at, reverse=True)
    return [
        {
            "id": document.id,
            "title": document.title,
            "source_type": document.source_type,
            "status": document.status,
            "error_message": document.error_message,
            "updated_at": document.updated_at.isoformat(),
        }
        for document in problem_documents[:limit]
    ]


def source_type_counts(documents):
    """Return document counts grouped by knowledge source type."""
    counts = {}
    for document in documents:
        counts[document.source_type] = counts.get(document.source_type, 0) + 1
    return counts


def _knowledge_source_type_diagnostics(source_counts, searchable_by_source, chunks_by_source):
    """Return normalized per-source diagnostics for the admin RAG status view."""
    source_types = sorted(set(source_counts) | set(searchable_by_source) | set(chunks_by_source))
    return [
        {
            "source_type": source_type,
            "documents": source_counts.get(source_type, 0),
            "searchable_documents": searchable_by_source.get(source_type, 0),
            "chunks": chunks_by_source.get(source_type, 0),
            "searchable": searchable_by_source.get(source_type, 0) > 0,
        }
        for source_type in source_types
    ]


__all__ = [
    "list_knowledge_documents",
    "knowledge_index_status",
    "_rag_readiness",
    "_problem_knowledge_documents",
    "source_type_counts",
    "_knowledge_source_type_diagnostics",
]
