"""Automatic document processing for the local knowledge base."""

import logging
import re

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import GeneratedDocument, KnowledgeChunk, KnowledgeDocument, MachineManual
from app.services.knowledge_quality_service import default_quality_status_for_source

logger = logging.getLogger(__name__)

DOCUMENT_SOURCE_TYPES = {"generated_document", "machine_manual"}
ERROR_CODE_PATTERN = re.compile(
    r"\b(?:[A-Z]{1,8}[-_])?[A-Z]{1,4}[-_]?\d{2,5}(?:[-_][A-Z0-9]{1,8})?\b",
    re.IGNORECASE,
)


def process_generated_document_for_knowledge(document, user=None):
    """Process a generated maintenance document into searchable knowledge chunks."""
    return process_document_for_knowledge(document, "generated_document", user=user)


def process_machine_manual_for_knowledge(manual, user=None):
    """Process an uploaded machine manual into searchable knowledge chunks."""
    return process_document_for_knowledge(manual, "machine_manual", user=user)


def process_document_for_knowledge(source, source_type, user=None):
    """Register, summarize, detect metadata, and index one document source."""
    if source is None:
        return None, {"error": "document is required"}, 400
    if source_type not in DOCUMENT_SOURCE_TYPES:
        return None, {"error": "document source type is not supported"}, 400
    if not getattr(source, "id", None):
        return None, {"error": "document id is required"}, 400

    try:
        knowledge_document = _ensure_knowledge_document(source, source_type, user)
        content_text = _extract_document_content_text(source, source_type)
        text = _extract_searchable_text(knowledge_document)
        metadata = detect_document_metadata(
            text,
            source,
            source_type,
            content_text=content_text,
        )
        _store_summary_when_missing(source, source_type, content_text)
        indexed_document = (
            _index_knowledge_document(knowledge_document)
            if content_text.strip()
            else _mark_knowledge_document_no_text(knowledge_document)
        )
        db.session.commit()
    except (OSError, ValueError) as exc:
        db.session.rollback()
        logger.warning(
            "document_knowledge_processing_failed source_type=%s source_id=%s error=%s",
            source_type,
            getattr(source, "id", None),
            exc,
        )
        return None, {"error": str(exc)}, 400

    return _processing_payload(source, source_type, indexed_document, metadata), None, 200


def detect_document_metadata(text, source, source_type, content_text=None):
    """Return machine, department, error-code, and document-type metadata."""
    normalized_text = str(text or "")
    normalized_content = (
        str(content_text or "") if content_text is not None else normalized_text
    )
    return {
        "source_type": source_type,
        "source_id": getattr(source, "id", None),
        "document_type": _document_type(source, source_type),
        "machine": _source_machine(source, normalized_text),
        "department": _source_department(source),
        "error_codes": _error_codes("\n".join((normalized_text, normalized_content))),
        "has_text": bool(normalized_content.strip()),
        "text_length": len(normalized_content.strip()),
    }


def _ensure_knowledge_document(source, source_type, user=None):
    """Return an existing or newly registered knowledge document for a source."""
    knowledge_document = KnowledgeDocument.query.filter_by(
        source_type=source_type,
        source_id=source.id,
    ).first()
    if not knowledge_document:
        knowledge_document = KnowledgeDocument(
            source_type=source_type,
            source_id=source.id,
            title=_source_title(source, source_type),
            original_filename=_source_original_filename(source, source_type),
            relative_path=_source_relative_path(source, source_type),
            content_type=_source_content_type(source, source_type),
            file_size=_source_file_size(source),
            department=_source_department(source)[:120],
            status="pending",
            quality_status=default_quality_status_for_source(source_type),
            is_public=True,
            created_by=_source_created_by(source, user),
            created_at=getattr(source, "created_at", None) or utc_now(),
        )
        db.session.add(knowledge_document)

    _sync_knowledge_document_metadata(knowledge_document, source, source_type, user)
    db.session.flush()
    return knowledge_document


def _sync_knowledge_document_metadata(knowledge_document, source, source_type, user=None):
    """Synchronize stable source metadata onto the knowledge document row."""
    knowledge_document.title = _source_title(source, source_type)
    knowledge_document.original_filename = _source_original_filename(source, source_type)
    knowledge_document.relative_path = _source_relative_path(source, source_type)
    knowledge_document.content_type = _source_content_type(source, source_type)
    knowledge_document.file_size = _source_file_size(source)
    knowledge_document.department = _source_department(source)[:120]
    knowledge_document.created_by = knowledge_document.created_by or _source_created_by(
        source,
        user,
    )
    knowledge_document.updated_at = utc_now()


def _extract_searchable_text(knowledge_document):
    """Extract searchable source text through the existing knowledge pipeline."""
    from app.services.knowledge_service import extract_knowledge_text

    return extract_knowledge_text(knowledge_document)


def _extract_document_content_text(source, source_type):
    """Return only the actual uploaded or generated document text content."""
    if source_type == "machine_manual":
        version = source.current_version
        return version.extracted_text if version else ""

    from app.services.document_service import document_path, html_to_text

    path = document_path(source)
    if not path.exists():
        return str(getattr(source, "summary", "") or "")
    return html_to_text(path.read_text(encoding="utf-8", errors="ignore"))


def _index_knowledge_document(knowledge_document):
    """Rebuild local chunks and optional vector-store records for one source."""
    from app.services.knowledge_service import index_knowledge_document

    return index_knowledge_document(knowledge_document)


def _mark_knowledge_document_no_text(knowledge_document):
    """Clear chunks and mark a document without extractable content as no-text."""
    KnowledgeChunk.query.filter(
        KnowledgeChunk.document_id == knowledge_document.id,
    ).delete()
    knowledge_document.status = "no_text"
    knowledge_document.chunk_count = 0
    knowledge_document.error_message = "Keine Textschicht gefunden."
    knowledge_document.updated_at = utc_now()
    _clear_vector_records(knowledge_document)
    return knowledge_document


def _clear_vector_records(knowledge_document):
    """Remove external vector records for a no-text knowledge document when enabled."""
    try:
        from app.services.knowledge_service import sync_vector_store_document

        sync_vector_store_document(knowledge_document, [])
    except ImportError as exc:
        logger.warning(
            "vector_store_cleanup_import_failed document_id=%s error=%s",
            knowledge_document.id,
            exc,
        )


def _store_summary_when_missing(source, source_type, text):
    """Persist a short summary on document models when no summary exists yet."""
    if not hasattr(source, "summary") or str(source.summary or "").strip():
        return

    from app.services.document_service import summarize_text

    summary, status = summarize_text(
        text,
        {
            "source_type": source_type,
            "source_id": source.id,
            "title": _source_title(source, source_type),
        },
    )
    source.summary = str(summary or "")[:4000]
    source.summary_status = status


def _processing_payload(source, source_type, knowledge_document, metadata):
    """Return a compact processing result for tests and internal callers."""
    return {
        "source_type": source_type,
        "source_id": source.id,
        "knowledge_document_id": knowledge_document.id,
        "status": knowledge_document.status,
        "chunk_count": knowledge_document.chunk_count,
        "summary": getattr(source, "summary", ""),
        "summary_status": getattr(source, "summary_status", ""),
        "metadata": metadata,
        "knowledge_document": knowledge_document.to_dict(),
    }


def _source_title(source, source_type):
    """Return the stable knowledge title for a document source."""
    if source_type == "generated_document":
        return str(source.title or f"Wartungsbericht {source.id}")[:220]
    return str(source.title or source.original_filename or f"Handbuch {source.id}")[:220]


def _source_original_filename(source, source_type):
    """Return the original filename stored on the knowledge document."""
    if source_type == "generated_document":
        return _generated_document_filename(source)
    return str(source.original_filename or "")[:255]


def _generated_document_filename(document):
    """Return the filename for a generated document source."""
    if document.current_version and document.current_version.original_filename:
        return document.current_version.original_filename[:255]
    return str(document.relative_path or "").rsplit("/", 1)[-1][:255]


def _source_relative_path(source, source_type):
    """Return a source path or API URL for the knowledge document."""
    if source_type == "generated_document":
        return str(source.relative_path or "")
    return f"/api/v1/documents/manuals/{source.id}/download"


def _source_content_type(source, source_type):
    """Return the best-known content type for a document source."""
    if source_type == "generated_document":
        if source.current_version and source.current_version.content_type:
            return source.current_version.content_type[:120]
        return "text/html"
    return str(source.content_type or "application/octet-stream")[:120]


def _source_file_size(source):
    """Return the persisted file size for a document source."""
    if getattr(source, "file_size", None):
        return int(source.file_size)
    version = getattr(source, "current_version", None)
    return int(getattr(version, "file_size", 0) or 0)


def _source_department(source):
    """Return the department associated with a document source."""
    return str(getattr(source, "department", "") or "").strip()


def _source_created_by(source, user=None):
    """Return the user id responsible for a knowledge document source."""
    return getattr(source, "created_by", None) or getattr(user, "id", None)


def _document_type(source, source_type):
    """Return the normalized document type metadata value."""
    if source_type == "generated_document":
        return str(getattr(source, "document_type", "") or "generated_document")
    return "machine_manual"


def _source_machine(source, text):
    """Return the machine name from source metadata or extracted text."""
    machine_value = getattr(source, "machine", "")
    if isinstance(source, MachineManual) and source.machine:
        return source.machine.name
    if isinstance(source, GeneratedDocument) and machine_value:
        return str(machine_value).strip()
    return _line_value(text, ("maschine", "anlage"))


def _line_value(text, labels):
    """Return the first value after one of the provided labels in source text."""
    for line in str(text or "").splitlines():
        if ":" not in line:
            continue
        label, value = line.split(":", 1)
        if label.strip().lower() in labels:
            return value.strip()[:160]
    return ""


def _error_codes(text):
    """Return unique error codes detected in extracted document text."""
    matches = {
        match.group(0).upper().replace("_", "-")
        for match in ERROR_CODE_PATTERN.finditer(str(text or ""))
    }
    return sorted(matches)[:20]
