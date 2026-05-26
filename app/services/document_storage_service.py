"""Document Storage Service helpers."""

# ruff: noqa: F401, F821

import logging
import re
from datetime import UTC, datetime
from html import escape
from html.parser import HTMLParser
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import (
    DocumentApprovalEvent,
    DocumentVersion,
    GeneratedDocument,
    Machine,
    MachineManual,
    MachineManualVersion,
    Role,
)
from app.services.ai_service import AIServiceError, get_ai_provider

ALLOWED_CHECK_EXTENSIONS = {".html", ".htm", ".txt"}
ALLOWED_MANUAL_EXTENSIONS = {".pdf", ".txt", ".html", ".htm"}
DOCUMENT_STATUSES = {"draft", "in_review", "approved", "rejected"}

REVIEW_REQUIRED_FIELDS = (
    "Maschine",
    "Ursache",
    "Durchgefuehrte Massnahme",
    "Ergebnis",
    "Notizen",
)

REPORT_FIELD_ALIASES = {
    "anlage": "Maschine",
    "maschine": "Maschine",
    "fehler": "Fehler",
    "fehlercode": "Fehlercode",
    "fehler-code": "Fehlercode",
    "task titel": "Task-Titel",
    "task-titel": "Task-Titel",
    "titel": "Task-Titel",
    "beschreibung": "Beschreibung",
    "ursache": "Ursache",
    "moegliche ursache": "Ursache",
    "mögliche ursache": "Ursache",
    "moegliche ursachen": "Ursache",
    "mögliche ursachen": "Ursache",
    "durchgefuehrte massnahme": "Durchgefuehrte Massnahme",
    "durchgeführte maßnahme": "Durchgefuehrte Massnahme",
    "massnahme": "Durchgefuehrte Massnahme",
    "maßnahme": "Durchgefuehrte Massnahme",
    "vorgeschlagene massnahme": "Durchgefuehrte Massnahme",
    "vorgeschlagene maßnahme": "Durchgefuehrte Massnahme",
    "loesung": "Durchgefuehrte Massnahme",
    "lösung": "Durchgefuehrte Massnahme",
    "ergebnis": "Ergebnis",
    "notizen": "Notizen",
    "hinweise": "Notizen",
}


logger = logging.getLogger(__name__)


def _resolve_machine_id(name):
    """Return Machine.id for an exact case-insensitive name match, or None."""
    if not name:
        return None
    machine = Machine.query.filter(Machine.name.ilike(name)).first()
    return machine.id if machine else None


def visible_documents_query(user):
    """Return a query for documents visible to the user."""
    query = GeneratedDocument.query
    if not user:
        return query.filter(False)
    if user.role != Role.MASTER_ADMIN and user.department:
        query = query.filter(GeneratedDocument.department == user.department.name)
    return query


def document_path(document):
    """Return the absolute safe path for a generated document."""
    return safe_storage_path(current_app.config["DOCUMENTS_FOLDER"], document.relative_path)


def manual_path(manual_or_version):
    """Return the absolute safe path for a stored machine manual file."""
    return safe_storage_path(current_app.config["MANUALS_FOLDER"], manual_or_version.relative_path)


def safe_storage_path(base_folder, relative_path):
    """Return a resolved path and reject traversal outside a configured folder."""
    base_path = Path(base_folder).resolve()
    full_path = (base_path / relative_path).resolve()
    if base_path not in full_path.parents and full_path != base_path:
        raise ValueError("Path escapes document storage")
    return full_path


def visible_manuals_query(user):
    """Return a query for machine manuals visible to the user."""
    query = MachineManual.query
    if not user:
        return query.filter(False)
    if user.role != Role.MASTER_ADMIN and user.department:
        query = query.filter(MachineManual.department == user.department.name)
    return query


def ensure_document_version(document):
    """Create a current document version for legacy documents if needed."""
    if document.current_version_id:
        return document.current_version
    path = document_path(document)
    version = DocumentVersion(
        document=document,
        version_number=1,
        relative_path=document.relative_path,
        original_filename=Path(document.relative_path).name,
        content_type="text/html",
        file_size=path.stat().st_size if path.exists() else 0,
        created_by=document.created_by,
        created_at=document.created_at,
    )
    db.session.add(version)
    db.session.flush()
    document.current_version_id = version.id
    db.session.commit()
    return version


def document_versions(document):
    """Return version records for a generated document, creating v1 if missing."""
    ensure_document_version(document)
    return (
        DocumentVersion.query.filter_by(document_id=document.id)
        .order_by(DocumentVersion.version_number.desc())
        .all()
    )


def render_document_pdf(document):
    """Render a generated HTML report as a simple server-side PDF byte stream."""
    path = document_path(document)
    if not path.exists():
        return None, {"error": "Document file not found"}, 404
    html_text = path.read_text(encoding="utf-8")
    title = document.title or f"Wartungsbericht {document.id}"
    pdf_bytes = plain_text_to_pdf(title, html_to_text(html_text))
    return pdf_bytes, None, 200


def upload_machine_manual(file_storage, user, machine_id=None, department=""):
    """Persist an uploaded machine manual and create its first version."""
    validation_error = validate_manual_upload(file_storage, machine_id)
    if validation_error:
        return None, validation_error, 400

    machine = db.session.get(Machine, int(machine_id)) if machine_id else None
    filename = secure_filename(Path(file_storage.filename).name)
    raw_content = file_storage.read()
    if not raw_content:
        return None, {"error": "file must not be empty"}, 400

    department_name = (department or "").strip()
    if not department_name and user.department:
        department_name = user.department.name
    if not department_name and machine:
        department_name = ""

    manual = MachineManual(
        machine=machine,
        department=department_name,
        title=Path(filename).stem or filename,
        original_filename=filename,
        relative_path="pending",
        content_type=file_storage.mimetype or "",
        file_size=len(raw_content),
        created_by=user.id,
    )
    db.session.add(manual)
    db.session.flush()

    relative_path = f"manual_{manual.id}/v1/{filename}"
    full_path = safe_storage_path(current_app.config["MANUALS_FOLDER"], relative_path)
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(raw_content)

    extracted_text, extraction_status = extract_manual_text(filename, raw_content)
    version = MachineManualVersion(
        manual=manual,
        version_number=1,
        relative_path=relative_path,
        original_filename=filename,
        content_type=file_storage.mimetype or "",
        file_size=len(raw_content),
        extracted_text=extracted_text,
        extraction_status=extraction_status,
        created_by=user.id,
    )
    manual.relative_path = relative_path
    db.session.add(version)
    db.session.flush()
    manual.current_version_id = version.id
    db.session.commit()
    _process_machine_manual_knowledge(manual, user)
    return manual.to_dict(), None, 201


def validate_manual_upload(file_storage, machine_id=None):
    """Return an error payload when a manual upload is invalid."""
    if not file_storage or not file_storage.filename:
        return {"error": "file is required"}
    extension = Path(file_storage.filename).suffix.lower()
    if extension not in ALLOWED_MANUAL_EXTENSIONS:
        return {"error": "file type not supported; use pdf, txt, html or htm"}
    if machine_id not in (None, ""):
        try:
            parsed_machine_id = int(machine_id)
        except (TypeError, ValueError):
            return {"error": "machine_id must be a valid machine id"}
        if not db.session.get(Machine, parsed_machine_id):
            return {"error": "machine_id does not reference an existing machine"}
    return None


def analyze_machine_manual(manual):
    """Analyze a machine manual using extracted text and local structured fallback."""
    version = manual.current_version
    if not version or not version.extracted_text.strip():
        manual.analysis_status = "no_text"
        manual.analysis = "Keine Textschicht gefunden. OCR ist nicht integriert."
        db.session.commit()
        return manual.to_dict(), None, 200
    analysis = local_manual_analysis(version.extracted_text, manual)
    manual.analysis = analysis
    manual.analysis_status = "local_answer"
    db.session.commit()
    _process_machine_manual_knowledge(manual)
    return manual.to_dict(), None, 200


def summarize_machine_manual(manual):
    """Create or update a stored machine manual summary."""
    version = manual.current_version
    if not version or not version.extracted_text.strip():
        manual.summary_status = "no_text"
        manual.summary = "Keine Textschicht gefunden. OCR ist nicht integriert."
        db.session.commit()
        return manual.to_dict(), None, 200
    summary, status = summarize_text(
        version.extracted_text,
        {"manual_id": manual.id, "title": manual.title},
    )
    manual.summary = summary
    manual.summary_status = status
    db.session.commit()
    _process_machine_manual_knowledge(manual)
    return manual.to_dict(), None, 200


def delete_machine_manual(manual):
    """Delete a manual record and its stored file if present."""
    _delete_machine_manual_knowledge(manual)
    try:
        path = manual_path(manual)
    except ValueError:
        path = None
    if path and path.exists():
        try:
            path.unlink()
        except OSError as exc:
            logger.warning("manual_file_delete_failed manual_id=%s error=%s", manual.id, exc)
    db.session.delete(manual)
    db.session.commit()


def _process_generated_document_knowledge(document, user=None):
    """Best-effort sync of a generated document into the knowledge index."""
    try:
        from app.services.document_knowledge_processing_service import (
            process_generated_document_for_knowledge,
        )

        _result, error, _status = process_generated_document_for_knowledge(document, user=user)
    except Exception:
        logger.exception(
            "generated_document_knowledge_processing_failed document_id=%s",
            getattr(document, "id", None),
        )
        return
    if error:
        logger.warning(
            "generated_document_knowledge_processing_error document_id=%s error=%s",
            getattr(document, "id", None),
            error,
        )


def _process_machine_manual_knowledge(manual, user=None):
    """Best-effort sync of a machine manual into the knowledge index."""
    try:
        from app.services.document_knowledge_processing_service import (
            process_machine_manual_for_knowledge,
        )

        _result, error, _status = process_machine_manual_for_knowledge(manual, user=user)
    except Exception:
        logger.exception(
            "machine_manual_knowledge_processing_failed manual_id=%s",
            getattr(manual, "id", None),
        )
        return
    if error:
        logger.warning(
            "machine_manual_knowledge_processing_error manual_id=%s error=%s",
            getattr(manual, "id", None),
            error,
        )


def _delete_machine_manual_knowledge(manual):
    """Best-effort deletion of knowledge chunks linked to a machine manual."""
    try:
        from app.services.knowledge_service import delete_source_knowledge_document

        delete_source_knowledge_document("machine_manual", manual.id)
    except Exception:
        logger.exception(
            "machine_manual_knowledge_delete_failed manual_id=%s",
            getattr(manual, "id", None),
        )


__all__ = [
    "_resolve_machine_id",
    "visible_documents_query",
    "document_path",
    "manual_path",
    "safe_storage_path",
    "visible_manuals_query",
    "ensure_document_version",
    "document_versions",
    "render_document_pdf",
    "upload_machine_manual",
    "validate_manual_upload",
    "analyze_machine_manual",
    "summarize_machine_manual",
    "delete_machine_manual",
    "_process_generated_document_knowledge",
    "_process_machine_manual_knowledge",
    "_delete_machine_manual_knowledge",
]
