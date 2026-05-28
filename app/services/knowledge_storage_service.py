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
    AIFAQEntry,
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


def knowledge_folder():
    """Return the configured knowledge storage folder."""
    folder = Path(current_app.config["KNOWLEDGE_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def knowledge_path(document):
    """Return a safe absolute path for a stored knowledge document."""
    base = knowledge_folder().resolve()
    path = (base / document.relative_path).resolve()
    if base != path and base not in path.parents:
        raise ValueError("Knowledge path escapes configured folder")
    return path


def validate_knowledge_upload(file_storage):
    """Return an error tuple when a knowledge upload is invalid."""
    if not file_storage or not file_storage.filename:
        return {"error": "file is required"}, 400
    filename = secure_filename(file_storage.filename)
    if not filename:
        return {"error": "filename is invalid"}, 400
    if Path(filename).suffix.lower() not in ALLOWED_KNOWLEDGE_EXTENSIONS:
        return {"error": "file type is not supported"}, 400
    return None, None


def upload_knowledge_document(file_storage, user, department=""):
    """Persist, extract and index an uploaded knowledge document."""
    error, status = validate_knowledge_upload(file_storage)
    if error:
        return None, error, status

    filename = secure_filename(file_storage.filename)
    raw_content = file_storage.read()
    if not raw_content:
        return None, {"error": "file must not be empty"}, 400
    if len(raw_content) > MAX_UPLOAD_BYTES:
        return None, {"error": "file is too large"}, 400

    relative_path = f"uploads/{uuid.uuid4().hex}_{filename}"
    target_path = knowledge_folder() / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(raw_content)

    document = KnowledgeDocument(
        source_type="upload",
        title=Path(filename).stem[:220] or filename[:220],
        original_filename=filename,
        relative_path=relative_path,
        content_type=file_storage.mimetype or "",
        file_size=len(raw_content),
        department=str(department or "").strip()[:120],
        status="pending",
        quality_status=default_quality_status_for_source("upload"),
        is_public=True,
        created_by=user.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(document)
    db.session.flush()
    index_knowledge_document(document, raw_content=raw_content, filename=filename)
    db.session.commit()
    return document.to_dict(), None, 201


def index_knowledge_document(document, raw_content=None, filename=None):
    """Extract text and rebuild chunks for one knowledge document."""
    try:
        text = extract_knowledge_text(document, raw_content=raw_content, filename=filename)
    except (OSError, ValueError) as exc:
        logger.warning("knowledge_extract_failed document_id=%s", document.id)
        document.status = "error"
        document.error_message = str(exc)[:1000]
        document.chunk_count = 0
        return document

    document.updated_at = utc_now()
    rebuild_chunks(document, text)
    if document.status == "error":
        return document
    document.status = "indexed" if document.chunk_count else "no_text"
    document.error_message = "" if document.chunk_count else "Keine Textschicht gefunden."
    return document


def extract_knowledge_text(document, raw_content=None, filename=None):
    """Extract searchable text from any registered knowledge document."""
    if raw_content is not None:
        text, _status = extract_manual_text(filename or document.original_filename, raw_content)
        return text

    if document.source_type == "generated_document":
        return generated_document_text(document.source_id)
    if document.source_type == "error_entry":
        return error_entry_text(document.source_id)
    if document.source_type == "task":
        return task_text(document.source_id)
    if document.source_type == "machine":
        return machine_text(document.source_id)
    if document.source_type == "inventory_material":
        return inventory_material_text(document.source_id)
    if document.source_type == "maintenance_plan":
        return maintenance_plan_text(document.source_id)
    if document.source_type == "machine_manual":
        return machine_manual_text(document.source_id)
    if document.source_type == "shift_handover":
        return shift_handover_text(document.source_id)
    if document.source_type == "manual_training":
        return manual_training_text(document.source_id)
    if document.source_type == "faq":
        return faq_entry_text(document.source_id)

    path = knowledge_path(document)
    if not path.exists():
        return ""
    text, _status = extract_manual_text(
        document.original_filename or path.name,
        path.read_bytes(),
    )
    return text


def generated_document_text(document_id):
    """Return searchable text for a generated maintenance document."""
    source = db.session.get(GeneratedDocument, document_id)
    if not source:
        return ""
    path = document_path(source)
    if not path.exists():
        return source.summary or ""
    file_text = html_to_text(path.read_text(encoding="utf-8", errors="ignore"))
    return "\n".join(
        part
        for part in (
            f"Titel: {source.title}",
            f"Dokumenttyp: {source.document_type}",
            f"Maschine: {source.machine}",
            f"Abteilung: {source.department}",
            f"Zusammenfassung: {source.summary}",
            file_text,
        )
        if part
    )


def error_entry_text(error_id):
    """Return searchable text for an error catalog entry."""
    entry = db.session.get(ErrorEntry, error_id)
    if not entry:
        return ""
    return "\n".join(
        part
        for part in (
            f"Fehlerkatalog #{entry.id}",
            f"Maschine: {entry.machine}",
            f"Fehlercode: {entry.error_code}",
            f"Titel: {entry.title}",
            f"Beschreibung: {entry.description}",
            f"Moegliche Ursachen: {entry.possible_causes}",
            f"Loesung: {entry.solution}",
            f"Abteilung: {entry.department.name if entry.department else ''}",
        )
        if part
    )


def task_text(task_id):
    """Return searchable text for a maintenance task."""
    task = db.session.get(Task, task_id)
    if not task:
        return ""
    return "\n".join(
        part
        for part in (
            f"Task #{task.id}",
            f"Titel: {task.title}",
            f"Beschreibung: {task.description}",
            f"Prioritaet: {task.priority.value}",
            f"Status: {task.status.value}",
            f"Faelligkeit: {task.due_date.isoformat()}",
            f"Abteilung: {task.department.name if task.department else ''}",
        )
        if part
    )


def maintenance_plan_text(plan_id):
    """Return searchable text for a recurring maintenance plan."""
    plan = db.session.get(MaintenancePlan, plan_id)
    if not plan:
        return ""
    return "\n".join(
        part
        for part in (
            f"Wartungsplan #{plan.id}",
            f"Titel: {plan.title}",
            f"Beschreibung: {plan.description}",
            f"Intervall Tage: {plan.interval_days}",
            f"Naechste Faelligkeit: {plan.next_due_date.isoformat()}",
            f"Prioritaet: {plan.priority.value}",
            f"Aktiv: {plan.is_active}",
            f"Maschine: {plan.machine.name if plan.machine else ''}",
            f"Abteilung: {plan.department.name if plan.department else ''}",
        )
        if part
    )


def machine_text(machine_id):
    """Return searchable text for a production machine."""
    machine = db.session.get(Machine, machine_id)
    if not machine:
        return ""
    material_lines = [
        f"- {material.name}: Bestand {material.quantity}, Hersteller {material.manufacturer}"
        for material in machine.materials
    ]
    return "\n".join(
        part
        for part in (
            f"Maschine #{machine.id}",
            f"Name: {machine.name}",
            f"Produziertes Teil: {machine.produced_item}",
            f"Personalbedarf: {machine.required_employees}",
            "Materialien:\n" + "\n".join(material_lines) if material_lines else "",
        )
        if part
    )


def inventory_material_text(material_id):
    """Return searchable text for an inventory material."""
    material = db.session.get(InventoryMaterial, material_id)
    if not material:
        return ""
    return "\n".join(
        part
        for part in (
            f"Material #{material.id}",
            f"Name: {material.name}",
            f"Bestand: {material.quantity}",
            f"Einzelkosten: {material.unit_cost}",
            f"Hersteller: {material.manufacturer}",
            f"Maschine: {material.machine.name if material.machine else ''}",
            f"Produziertes Teil: {material.machine.produced_item if material.machine else ''}",
        )
        if part
    )


def machine_manual_text(manual_id):
    """Return searchable text for an uploaded machine manual."""
    manual = db.session.get(MachineManual, manual_id)
    if not manual:
        return ""
    extracted_text = manual.current_version.extracted_text if manual.current_version else ""
    return "\n".join(
        part
        for part in (
            f"Maschinenhandbuch #{manual.id}",
            f"Titel: {manual.title}",
            f"Datei: {manual.original_filename}",
            f"Maschine: {manual.machine.name if manual.machine else ''}",
            f"Abteilung: {manual.department}",
            f"Analyse: {manual.analysis}",
            f"Zusammenfassung: {manual.summary}",
            extracted_text,
        )
        if part
    )


def shift_handover_text(handover_id):
    """Return searchable text for a shift handover entry."""
    handover = db.session.get(ShiftHandover, handover_id)
    if not handover:
        return ""
    return "\n".join(
        part
        for part in (
            f"Schichtuebergabe #{handover.id}",
            f"Datum: {handover.shift_date.isoformat()}",
            f"Schicht: {handover.shift_type}",
            f"Status: {handover.status}",
            f"Abteilung: {handover.department}",
            f"Inhalt: {handover.content}",
            f"Offene Tasks: {handover.open_tasks}",
            f"Maschinenhinweise: {handover.machine_notes}",
            f"Naechste Schritte: {handover.next_notes}",
        )
        if part
    )


def manual_training_text(entry_id):
    """Return searchable text for a manual assistant training entry."""
    entry = db.session.get(AssistantTrainingEntry, entry_id)
    if not entry or not entry.is_active:
        return ""
    return "\n".join(
        part
        for part in (
            f"Manuelles Assistant-Training #{entry.id}",
            f"Titel: {entry.title}",
            f"Kategorie: {entry.category}",
            f"Abteilung: {entry.department}",
            f"Prioritaet: {entry.priority}",
            f"Frage: {entry.question}",
            f"Antwort: {entry.answer}",
            f"Keywords: {entry.keywords}",
        )
        if part
    )


def faq_entry_text(entry_id):
    """Return searchable text for an approved AI FAQ entry."""
    entry = db.session.get(AIFAQEntry, entry_id)
    if not entry or entry.status != "approved":
        return ""
    return "\n".join(
        part
        for part in (
            f"FAQ #{entry.id}",
            f"Kategorie: {entry.category}",
            f"Abteilung: {entry.department}",
            f"Maschine: {entry.machine}",
            f"Frage: {entry.question}",
            f"Antwort: {entry.answer}",
            f"Keywords: {entry.keywords}",
        )
        if part
    )


def delete_knowledge_document(document):
    """Delete a knowledge document and its stored upload if applicable."""
    if document.source_type == "upload" and document.relative_path:
        try:
            path = knowledge_path(document)
            if path.exists():
                path.unlink()
        except (OSError, ValueError):
            logger.warning("knowledge_file_delete_failed document_id=%s", document.id)
    db.session.delete(document)
    db.session.commit()


__all__ = [
    "knowledge_folder",
    "knowledge_path",
    "validate_knowledge_upload",
    "upload_knowledge_document",
    "index_knowledge_document",
    "extract_knowledge_text",
    "generated_document_text",
    "error_entry_text",
    "task_text",
    "maintenance_plan_text",
    "machine_text",
    "inventory_material_text",
    "machine_manual_text",
    "shift_handover_text",
    "manual_training_text",
    "faq_entry_text",
    "delete_knowledge_document",
]
