"""Vector-store synchronization and drift diagnostics for knowledge retrieval."""

from __future__ import annotations

from sqlalchemy import func

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import KnowledgeChunk, KnowledgeDocument

MAX_SYNC_FAILURES = 20
MAX_STATUS_REFERENCES = 25
PENDING_REINDEX_STATUSES = {"pending", "stale"}

_vector_sync_state = {
    "last_successful_sync": None,
    "last_failed_sync": None,
    "failures": [],
}


def record_vector_sync_success(document_id, store_name, chunk_count):
    """Record a successful external vector-store synchronization event."""
    _vector_sync_state["last_successful_sync"] = {
        "document_id": _optional_int(document_id),
        "store": str(store_name or ""),
        "chunk_count": _safe_int(chunk_count),
        "synced_at": utc_now().isoformat(),
    }


def record_vector_sync_failure(document_id, store_name, error):
    """Record a prompt-safe external vector-store synchronization failure."""
    event = {
        "document_id": _optional_int(document_id),
        "store": str(store_name or ""),
        "error_type": error.__class__.__name__,
        "error": _bounded_string(error, 220),
        "failed_at": utc_now().isoformat(),
    }
    _vector_sync_state["last_failed_sync"] = event
    _vector_sync_state["failures"] = ([event] + list(_vector_sync_state.get("failures") or []))[
        :MAX_SYNC_FAILURES
    ]


def vector_sync_observability_snapshot():
    """Return the current in-process vector synchronization event snapshot."""
    return {
        "last_successful_sync": _vector_sync_state.get("last_successful_sync"),
        "last_failed_sync": _vector_sync_state.get("last_failed_sync"),
        "failures": list(_vector_sync_state.get("failures") or []),
    }


def clear_vector_sync_observability():
    """Clear in-process vector synchronization events for deterministic tests."""
    _vector_sync_state["last_successful_sync"] = None
    _vector_sync_state["last_failed_sync"] = None
    _vector_sync_state["failures"] = []


def vector_store_drift_status(documents=None):
    """Return prompt-safe vector-store drift and synchronization diagnostics."""
    document_list = list(documents) if documents is not None else _load_documents()
    chunk_counts = _chunk_counts_by_document()
    store = _current_vector_store()
    store_name = getattr(store, "name", "unavailable")
    configured_store = _configured_vector_store()
    store_error = getattr(store, "_status_error", "")
    external_sync_required = store_name == "chroma"
    fallback_active = configured_store == "chroma" and store_name != "chroma"

    indexed_documents = [document for document in document_list if document.status == "indexed"]
    stale_documents = [document for document in document_list if document.status == "stale"]
    status_pending_documents = [
        document for document in document_list if document.status in PENDING_REINDEX_STATUSES
    ]
    latest_indexed_at = _latest_indexed_at(indexed_documents)
    expected_vector_count = sum(chunk_counts.get(document.id, 0) for document in indexed_documents)
    declared_chunk_count = sum(
        max(_safe_int(document.chunk_count), 0) for document in indexed_documents
    )
    actual_vector_count = _collection_vector_count(store)

    missing_chunks = _missing_chunks(indexed_documents, chunk_counts)
    chunk_mismatches = _chunk_mismatches(indexed_documents, chunk_counts)
    vector_mismatches = _vector_mismatches(store, indexed_documents, chunk_counts)
    pending_reindex_documents = _pending_reindex_references(
        document_list=document_list,
        chunk_counts=chunk_counts,
        status_pending_documents=status_pending_documents,
        missing_chunks=missing_chunks,
        chunk_mismatches=chunk_mismatches,
        vector_mismatches=vector_mismatches,
    )
    collection_mismatch = (
        actual_vector_count is not None and actual_vector_count != expected_vector_count
    )
    sync_snapshot = vector_sync_observability_snapshot()
    reindex_reasons = _reindex_reasons(
        stale_documents=stale_documents,
        pending_reindex_documents=status_pending_documents,
        missing_chunks=missing_chunks,
        chunk_mismatches=chunk_mismatches,
        vector_mismatches=vector_mismatches,
        collection_mismatch=collection_mismatch,
        sync_failures=sync_snapshot["failures"],
        store_error=store_error,
        fallback_active=fallback_active,
    )

    return {
        "store": store_name,
        "configured_store": configured_store,
        "fallback_active": fallback_active,
        "external_sync_required": external_sync_required,
        "expected_vector_count": expected_vector_count,
        "declared_chunk_count": declared_chunk_count,
        "actual_vector_count": actual_vector_count,
        "chunk_vector_count_mismatch": bool(
            collection_mismatch or vector_mismatches or chunk_mismatches
        ),
        "chunk_mismatch_count": len(chunk_mismatches),
        "missing_chunk_count": len(missing_chunks),
        "stale_document_count": len(stale_documents),
        "pending_reindex_count": len(pending_reindex_documents),
        "vector_sync_failure_count": len(sync_snapshot["failures"]),
        "last_successful_sync": sync_snapshot["last_successful_sync"],
        "last_failed_sync": sync_snapshot["last_failed_sync"],
        "latest_indexed_at": latest_indexed_at,
        "stale_documents": _document_references(stale_documents, chunk_counts),
        "pending_reindex_documents": pending_reindex_documents[:MAX_STATUS_REFERENCES],
        "missing_chunks": missing_chunks[:MAX_STATUS_REFERENCES],
        "chunk_mismatches": chunk_mismatches[:MAX_STATUS_REFERENCES],
        "vector_mismatches": vector_mismatches[:MAX_STATUS_REFERENCES],
        "sync_failures": sync_snapshot["failures"][:MAX_STATUS_REFERENCES],
        "store_error": store_error,
        "reindex_recommended": bool(reindex_reasons),
        "reindex_reasons": reindex_reasons,
        "privacy": {
            "stores_document_text": False,
            "exposes_document_text": False,
            "exposes_titles": False,
            "source": "knowledge_document_metadata_and_chunk_counts",
        },
    }


def _load_documents():
    """Return all knowledge documents ordered for deterministic diagnostics."""
    return KnowledgeDocument.query.order_by(KnowledgeDocument.id.asc()).all()


def _chunk_counts_by_document():
    """Return persisted chunk counts keyed by knowledge document id."""
    rows = (
        db.session.query(KnowledgeChunk.document_id, func.count(KnowledgeChunk.id))
        .group_by(KnowledgeChunk.document_id)
        .all()
    )
    return {document_id: int(count) for document_id, count in rows}


def _current_vector_store():
    """Return the configured vector store or a lightweight error sentinel."""
    try:
        from app.services.vector_store_service import get_vector_store

        return get_vector_store()
    except Exception as exc:  # pragma: no cover - defensive status path
        return _UnavailableVectorStore(exc)


def _configured_vector_store():
    """Return the configured vector-store name without forcing a backend to load."""
    try:
        from flask import current_app, has_app_context

        if has_app_context():
            return current_app.config.get("RAG_VECTOR_STORE", "local")
    except RuntimeError:
        return "local"
    return "local"


def _collection_vector_count(store):
    """Return the backend vector count when the store can report it."""
    if not hasattr(store, "collection_vector_count"):
        return None
    try:
        return store.collection_vector_count()
    except Exception as exc:  # pragma: no cover - defensive status path
        store._status_error = _bounded_string(exc, 220)
        return None


def _document_vector_count(store, document_id):
    """Return one document's backend vector count when the store can report it."""
    if not hasattr(store, "document_vector_count"):
        return None
    try:
        return store.document_vector_count(document_id)
    except Exception as exc:  # pragma: no cover - defensive status path
        store._status_error = _bounded_string(exc, 220)
        return None


def _missing_chunks(indexed_documents, chunk_counts):
    """Return indexed documents that have no persisted chunks."""
    missing = []
    for document in indexed_documents:
        db_chunk_count = chunk_counts.get(document.id, 0)
        declared_count = _safe_int(document.chunk_count)
        if declared_count > 0 and db_chunk_count == 0:
            missing.append(_document_reference(document, chunk_counts))
    return missing


def _chunk_mismatches(indexed_documents, chunk_counts):
    """Return indexed documents whose declared and persisted chunk counts differ."""
    mismatches = []
    for document in indexed_documents:
        db_chunk_count = chunk_counts.get(document.id, 0)
        declared_count = max(_safe_int(document.chunk_count), 0)
        if declared_count != db_chunk_count:
            mismatches.append(_document_reference(document, chunk_counts))
    return mismatches


def _vector_mismatches(store, indexed_documents, chunk_counts):
    """Return documents whose persisted chunks and backend vectors differ."""
    mismatches = []
    for document in indexed_documents:
        vector_count = _document_vector_count(store, document.id)
        if vector_count is None:
            continue
        db_chunk_count = chunk_counts.get(document.id, 0)
        if int(vector_count) != db_chunk_count:
            payload = _document_reference(document, chunk_counts)
            payload["vector_count"] = int(vector_count)
            mismatches.append(payload)
    return mismatches


def _pending_reindex_references(
    *,
    document_list,
    chunk_counts,
    status_pending_documents,
    missing_chunks,
    chunk_mismatches,
    vector_mismatches,
):
    """Return unique documents that need reindexing because of status or drift."""
    pending_ids = {document.id for document in status_pending_documents}
    pending_ids.update(item["id"] for item in missing_chunks)
    pending_ids.update(item["id"] for item in chunk_mismatches)
    pending_ids.update(item["id"] for item in vector_mismatches)
    return [
        _document_reference(document, chunk_counts)
        for document in document_list
        if document.id in pending_ids
    ]


def _document_references(documents, chunk_counts):
    """Return bounded prompt-safe document references for status payloads."""
    return [
        _document_reference(document, chunk_counts)
        for document in list(documents)[:MAX_STATUS_REFERENCES]
    ]


def _document_reference(document, chunk_counts):
    """Return a prompt-safe knowledge document reference without title or content."""
    return {
        "id": document.id,
        "source_type": document.source_type,
        "source_id": document.source_id,
        "status": document.status,
        "quality_status": document.quality_status,
        "department": document.department,
        "declared_chunk_count": max(_safe_int(document.chunk_count), 0),
        "db_chunk_count": chunk_counts.get(document.id, 0),
        "updated_at": document.updated_at.isoformat() if document.updated_at else None,
    }


def _latest_indexed_at(indexed_documents):
    """Return the newest indexed document timestamp as an ISO string."""
    timestamps = [document.updated_at for document in indexed_documents if document.updated_at]
    if not timestamps:
        return None
    return max(timestamps).isoformat()


def _reindex_reasons(
    *,
    stale_documents,
    pending_reindex_documents,
    missing_chunks,
    chunk_mismatches,
    vector_mismatches,
    collection_mismatch,
    sync_failures,
    store_error,
    fallback_active,
):
    """Return normalized reasons why reindexing or sync repair is recommended."""
    reasons = []
    if stale_documents:
        reasons.append("stale_documents")
    if pending_reindex_documents:
        reasons.append("pending_documents")
    if missing_chunks:
        reasons.append("missing_chunks")
    if chunk_mismatches:
        reasons.append("chunk_count_mismatch")
    if vector_mismatches or collection_mismatch:
        reasons.append("vector_count_mismatch")
    if sync_failures:
        reasons.append("vector_sync_failures")
    if store_error:
        reasons.append("vector_store_unavailable")
    if fallback_active:
        reasons.append("vector_store_fallback")
    return reasons


def _safe_int(value):
    """Return an integer value, falling back to zero for invalid input."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int(value):
    """Return an optional integer for ids used in status payloads."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _bounded_string(value, max_length):
    """Return a stripped string bounded for status payloads."""
    return str(value or "").strip()[:max_length]


class _UnavailableVectorStore:
    """Minimal vector-store sentinel used when backend loading fails."""

    name = "unavailable"

    def __init__(self, error):
        """Initialize the sentinel with a prompt-safe error description."""
        self._status_error = _bounded_string(error, 220)

    def collection_vector_count(self):
        """Return no collection count for unavailable backends."""
        return None

    def document_vector_count(self, document_id):
        """Return no document count for unavailable backends."""
        return None
