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


def ensure_generated_documents_registered():
    """Register generated documents in the knowledge base when missing."""
    documents = GeneratedDocument.query.order_by(GeneratedDocument.id.asc()).all()
    existing = {
        item.source_id
        for item in KnowledgeDocument.query.filter_by(source_type="generated_document").all()
    }
    for document in documents:
        if document.id in existing:
            continue
        db.session.add(
            KnowledgeDocument(
                source_type="generated_document",
                source_id=document.id,
                title=document.title,
                original_filename=Path(document.relative_path).name,
                relative_path=document.relative_path,
                content_type="text/html",
                department=document.department or "",
                status="pending",
                quality_status=default_quality_status_for_source("generated_document"),
                is_public=True,
                created_by=document.created_by,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
    db.session.flush()


def ensure_structured_sources_registered():
    """Register structured app records as RAG knowledge documents."""
    registered = 0
    registered += ensure_error_entries_registered()
    registered += ensure_tasks_registered()
    registered += ensure_machines_registered()
    registered += ensure_inventory_materials_registered()
    registered += ensure_maintenance_plans_registered()
    registered += ensure_machine_manuals_registered()
    registered += ensure_shift_handovers_registered()
    registered += ensure_assistant_training_entries_registered()
    registered += ensure_faq_entries_registered()
    return registered


def ensure_error_entries_registered():
    """Register error catalog entries in the knowledge base."""
    existing = existing_source_ids("error_entry")
    count = 0
    for entry in ErrorEntry.query.order_by(ErrorEntry.id.asc()).all():
        if entry.id in existing:
            continue
        register_error_entry_document(entry)
        count += 1
    db.session.flush()
    return count


def ensure_tasks_registered():
    """Register maintenance tasks in the knowledge base."""
    existing = existing_source_ids("task")
    count = 0
    for task in Task.query.order_by(Task.id.asc()).all():
        if task.id in existing:
            continue
        register_task_document(task)
        count += 1
    db.session.flush()
    return count


def ensure_maintenance_plans_registered():
    """Register recurring maintenance plans in the knowledge base."""
    existing = existing_source_ids("maintenance_plan")
    count = 0
    for plan in MaintenancePlan.query.order_by(MaintenancePlan.id.asc()).all():
        if plan.id in existing:
            continue
        register_source_document(
            source_type="maintenance_plan",
            source_id=plan.id,
            title=plan.title,
            department=plan.department.name if plan.department else "",
            created_by=plan.created_by,
            created_at=plan.created_at,
            url_path=f"/api/v1/machines/maintenance-plans/{plan.id}",
        )
        count += 1
    db.session.flush()
    return count


def ensure_machines_registered():
    """Register production machines in the knowledge base."""
    existing = existing_source_ids("machine")
    count = 0
    for machine in Machine.query.order_by(Machine.id.asc()).all():
        if machine.id in existing:
            continue
        register_source_document(
            source_type="machine",
            source_id=machine.id,
            title=machine.name,
            created_by=None,
            created_at=machine.created_at,
            url_path="/machines",
        )
        count += 1
    db.session.flush()
    return count


def ensure_inventory_materials_registered():
    """Register inventory materials in the knowledge base."""
    existing = existing_source_ids("inventory_material")
    count = 0
    for material in InventoryMaterial.query.order_by(InventoryMaterial.id.asc()).all():
        if material.id in existing:
            continue
        register_source_document(
            source_type="inventory_material",
            source_id=material.id,
            title=material.name,
            created_by=None,
            created_at=material.created_at,
            url_path="/inventory",
        )
        count += 1
    db.session.flush()
    return count


def ensure_machine_manuals_registered():
    """Register machine manuals in the knowledge base."""
    existing = existing_source_ids("machine_manual")
    count = 0
    for manual in MachineManual.query.order_by(MachineManual.id.asc()).all():
        if manual.id in existing:
            continue
        register_source_document(
            source_type="machine_manual",
            source_id=manual.id,
            title=manual.title,
            original_filename=manual.original_filename,
            department=manual.department,
            created_by=manual.created_by,
            created_at=manual.created_at,
            url_path=f"/api/v1/documents/manuals/{manual.id}/download",
        )
        count += 1
    db.session.flush()
    return count


def ensure_shift_handovers_registered():
    """Register shift handover records in the knowledge base."""
    existing = existing_source_ids("shift_handover")
    count = 0
    for handover in ShiftHandover.query.order_by(ShiftHandover.id.asc()).all():
        if handover.id in existing:
            continue
        register_source_document(
            source_type="shift_handover",
            source_id=handover.id,
            title=f"{handover.shift_date.isoformat()} {handover.shift_type}",
            department=handover.department,
            created_by=handover.handed_over_by,
            created_at=handover.created_at,
            url_path=f"/api/v1/handover/{handover.id}",
        )
        count += 1
    db.session.flush()
    return count


def ensure_assistant_training_entries_registered():
    """Register active manual assistant training entries in the knowledge base."""
    existing = existing_source_ids("manual_training")
    count = 0
    entries = (
        AssistantTrainingEntry.query.filter_by(is_active=True)
        .order_by(AssistantTrainingEntry.priority.desc(), AssistantTrainingEntry.id.asc())
        .all()
    )
    for entry in entries:
        if entry.id in existing:
            continue
        register_training_entry_document(entry)
        count += 1
    db.session.flush()
    return count


def ensure_faq_entries_registered():
    """Register approved FAQ entries in the knowledge base."""
    existing = existing_source_ids("faq")
    count = 0
    entries = (
        AIFAQEntry.query.filter_by(status="approved")
        .order_by(AIFAQEntry.updated_at.desc(), AIFAQEntry.id.asc())
        .all()
    )
    for entry in entries:
        if entry.id in existing:
            continue
        register_faq_entry_document(entry)
        count += 1
    db.session.flush()
    return count


def existing_source_ids(source_type):
    """Return registered source ids for a knowledge source type."""
    return {
        item.source_id for item in KnowledgeDocument.query.filter_by(source_type=source_type).all()
    }


def register_source_document(
    source_type,
    source_id,
    title,
    department="",
    created_by=None,
    created_at=None,
    original_filename="",
    url_path="",
):
    """Register one structured source as a pending knowledge document."""
    db.session.add(
        KnowledgeDocument(
            source_type=source_type,
            source_id=source_id,
            title=str(title or source_type)[:220],
            original_filename=str(original_filename or ""),
            relative_path=str(url_path or ""),
            content_type="text/plain",
            department=str(department or "")[:120],
            status="pending",
            quality_status=default_quality_status_for_source(source_type),
            is_public=True,
            created_by=created_by,
            created_at=created_at or utc_now(),
            updated_at=utc_now(),
        )
    )


def register_error_entry_document(entry):
    """Register one error catalog entry as a pending knowledge document."""
    register_source_document(
        source_type="error_entry",
        source_id=entry.id,
        title=f"{entry.error_code} - {entry.title}",
        department=entry.department.name if entry.department else "",
        created_at=entry.created_at,
        url_path=f"/api/v1/errors/{entry.id}",
    )


def register_task_document(task):
    """Register one maintenance task as a pending knowledge document."""
    register_source_document(
        source_type="task",
        source_id=task.id,
        title=task.title,
        department=task.department.name if task.department else "",
        created_by=task.created_by,
        created_at=task.created_at,
        url_path=f"/api/v1/tasks/{task.id}",
    )


def register_training_entry_document(entry):
    """Register one manual assistant training entry as a pending knowledge document."""
    register_source_document(
        source_type="manual_training",
        source_id=entry.id,
        title=entry.title,
        department=entry.department,
        created_by=entry.created_by,
        created_at=entry.created_at,
        url_path="/admin/ai",
    )


def register_faq_entry_document(entry):
    """Register one approved FAQ entry as a pending knowledge document."""
    register_source_document(
        source_type="faq",
        source_id=entry.id,
        title=entry.question[:220],
        department=entry.department,
        created_by=entry.created_by,
        created_at=entry.created_at,
        url_path="/admin/ai/prompt-faq",
    )


def mark_faq_entry_knowledge_stale(entry):
    """Create or mark an FAQ knowledge document as stale after a change."""
    if entry.status != "approved":
        delete_source_knowledge_document("faq", entry.id)
        return
    document = source_document("faq", entry.id)
    if not document:
        register_faq_entry_document(entry)
        return
    document.title = entry.question[:220]
    document.department = entry.department
    document.relative_path = "/admin/ai/prompt-faq"
    document.status = "stale"
    mark_quality_outdated_if_reviewed(document)
    document.error_message = "FAQ wurde geaendert und muss neu indexiert werden."
    document.updated_at = utc_now()


def mark_task_knowledge_stale(task):
    """Create or mark the task knowledge document as stale after a data change."""
    document = source_document("task", task.id)
    if not document:
        register_task_document(task)
        return
    document.title = task.title
    document.department = task.department.name if task.department else ""
    document.relative_path = f"/api/v1/tasks/{task.id}"
    document.status = "stale"
    mark_quality_outdated_if_reviewed(document)
    document.error_message = "Task wurde geaendert und muss neu indexiert werden."
    document.updated_at = utc_now()


def mark_training_entry_knowledge_stale(entry):
    """Create or mark a manual training knowledge document as stale after a change."""
    if not entry.is_active:
        delete_source_knowledge_document("manual_training", entry.id)
        return
    document = source_document("manual_training", entry.id)
    if not document:
        register_training_entry_document(entry)
        return
    document.title = entry.title
    document.department = entry.department
    document.relative_path = "/admin/ai"
    document.status = "stale"
    mark_quality_outdated_if_reviewed(document)
    document.error_message = "Trainingseintrag wurde geaendert und muss neu indexiert werden."
    document.updated_at = utc_now()


def mark_error_entry_knowledge_stale(entry):
    """Create or mark the error-entry knowledge document as stale after a change."""
    document = source_document("error_entry", entry.id)
    if not document:
        register_error_entry_document(entry)
        return
    document.title = f"{entry.error_code} - {entry.title}"
    document.department = entry.department.name if entry.department else ""
    document.relative_path = f"/api/v1/errors/{entry.id}"
    document.status = "stale"
    mark_quality_outdated_if_reviewed(document)
    document.error_message = "Fehlerkatalogeintrag wurde geaendert und muss neu indexiert werden."
    document.updated_at = utc_now()


def mark_machine_knowledge_stale(machine):
    """Create or mark the machine knowledge document as stale after a change."""
    document = source_document("machine", machine.id)
    if not document:
        register_source_document(
            source_type="machine",
            source_id=machine.id,
            title=machine.name,
            created_by=None,
            created_at=machine.created_at,
            url_path="/machines",
        )
        return
    document.title = machine.name
    document.relative_path = "/machines"
    document.status = "stale"
    mark_quality_outdated_if_reviewed(document)
    document.error_message = (
        "Maschinenstammdaten wurden geaendert und muessen neu indexiert werden."
    )
    document.updated_at = utc_now()


def delete_source_knowledge_document(source_type, source_id):
    """Delete the knowledge document linked to one structured source."""
    document = source_document(source_type, source_id)
    if document:
        db.session.delete(document)


def source_document(source_type, source_id):
    """Return the knowledge document linked to one structured source, if any."""
    return KnowledgeDocument.query.filter_by(
        source_type=source_type,
        source_id=source_id,
    ).first()


__all__ = [
    "ensure_generated_documents_registered",
    "ensure_structured_sources_registered",
    "ensure_error_entries_registered",
    "ensure_tasks_registered",
    "ensure_maintenance_plans_registered",
    "ensure_machines_registered",
    "ensure_inventory_materials_registered",
    "ensure_machine_manuals_registered",
    "ensure_shift_handovers_registered",
    "ensure_assistant_training_entries_registered",
    "ensure_faq_entries_registered",
    "existing_source_ids",
    "register_source_document",
    "register_error_entry_document",
    "register_task_document",
    "register_training_entry_document",
    "register_faq_entry_document",
    "mark_task_knowledge_stale",
    "mark_training_entry_knowledge_stale",
    "mark_faq_entry_knowledge_stale",
    "mark_error_entry_knowledge_stale",
    "mark_machine_knowledge_stale",
    "delete_source_knowledge_document",
    "source_document",
]
