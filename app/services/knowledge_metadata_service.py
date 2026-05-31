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
)


def _public_source_entity_metadata(metadata):
    """Return source metadata that is safe to expose in answer source cards."""
    safe = {}
    for key in ("machine", "department", "document_type"):
        value = metadata.get(key) if isinstance(metadata, dict) else None
        if value not in (None, ""):
            safe[key] = str(value)[:180]
    return safe


def stored_chunk_metadata(chunk):
    """Return section-aware metadata stored on a knowledge chunk."""
    reader = getattr(chunk, "retrieval_metadata", None)
    if not callable(reader):
        return {}
    return _safe_chunk_metadata(reader())


def _chunk_payload_text(chunk_payload):
    """Return the chunk text from a chunking-service payload."""
    if isinstance(chunk_payload, dict):
        return str(chunk_payload.get("text") or "")
    return str(chunk_payload or "")


def _chunk_payload_metadata(chunk_payload, index):
    """Return safe metadata from a chunking-service payload."""
    if not isinstance(chunk_payload, dict):
        return {"chunk_index": index, "chunk_order": index}
    metadata = dict(chunk_payload.get("metadata") or {})
    metadata.setdefault("chunk_index", index)
    metadata.setdefault("chunk_order", index)
    return _safe_chunk_metadata(metadata)


def _entities_to_json_with_chunk_metadata(entities, chunk_metadata):
    """Serialize technical entities with optional section-aware chunk metadata."""
    payload = json.loads(entities_to_json(entities))
    metadata = _safe_chunk_metadata(chunk_metadata)
    if metadata:
        payload["_chunk_metadata"] = metadata
    return json.dumps(payload, ensure_ascii=True, sort_keys=True)


def _safe_chunk_metadata(metadata):
    """Return bounded chunk metadata safe for vector and audit use."""
    if not isinstance(metadata, dict):
        return {}
    safe = {}
    for key in (
        "chunk_index",
        "chunk_order",
        "chunk_char_count",
        "chunk_line_count",
        "chunk_token_count",
        "chunk_block_count",
        "chunk_block_kinds",
        "source_offset",
        "source_section",
        "section_title",
        "chunking_mode",
        "semantic_group",
        "semantic_break_distance",
        "embedding_model",
    ):
        value = metadata.get(key)
        if value in (None, ""):
            continue
        if key in {
            "chunk_index",
            "chunk_order",
            "chunk_char_count",
            "chunk_line_count",
            "chunk_token_count",
            "chunk_block_count",
            "source_offset",
            "semantic_group",
        }:
            safe[key] = _optional_int(value)
            continue
        if key == "semantic_break_distance":
            safe[key] = _optional_float(value)
            continue
        safe[key] = str(value)[:180]
    return {key: value for key, value in safe.items() if value is not None}


def _optional_int(value):
    """Return an integer value when parsing succeeds."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value):
    """Return a float value when parsing succeeds."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def document_entity_metadata(document):
    """Return source-level metadata used to enrich every chunk entity payload."""
    metadata = {
        "title": document.title,
        "department": document.department,
        "source_type": document.source_type,
    }
    source_metadata = _source_entity_metadata(document)
    metadata.update(source_metadata)
    return metadata


def _source_entity_metadata(document):
    """Return entity-relevant metadata from a structured knowledge source."""
    if not document.source_id:
        return {}
    if document.source_type == "generated_document":
        return _generated_document_entity_metadata(document.source_id)
    if document.source_type == "error_entry":
        return _error_entry_entity_metadata(document.source_id)
    if document.source_type == "task":
        return _task_entity_metadata(document.source_id)
    if document.source_type == "machine":
        return _machine_entity_metadata(document.source_id)
    if document.source_type == "inventory_material":
        return _inventory_entity_metadata(document.source_id)
    if document.source_type == "maintenance_plan":
        return _maintenance_plan_entity_metadata(document.source_id)
    if document.source_type == "machine_manual":
        return _machine_manual_entity_metadata(document.source_id)
    if document.source_type == "shift_handover":
        return _shift_handover_entity_metadata(document.source_id)
    if document.source_type == "manual_training":
        return _manual_training_entity_metadata(document.source_id)
    return {}


def structured_source_record(document):
    """Return the structured source row for metadata enrichment."""
    if not getattr(document, "source_id", None):
        return None
    model_by_type = {
        "generated_document": GeneratedDocument,
        "error_entry": ErrorEntry,
        "machine": Machine,
        "task": Task,
        "inventory_material": InventoryMaterial,
        "maintenance_plan": MaintenancePlan,
        "machine_manual": MachineManual,
        "shift_handover": ShiftHandover,
    }
    model = model_by_type.get(str(getattr(document, "source_type", "") or ""))
    if model is None:
        return None
    return db.session.get(model, document.source_id)


def structured_source_created_at(document):
    """Return source creation time for structured sources when available."""
    source = structured_source_record(document)
    created_at = getattr(source, "created_at", None) if source else None
    return created_at.isoformat() if created_at else ""


def structured_source_machine_id(document):
    """Return the source-linked machine id when the source model exposes one."""
    source = structured_source_record(document)
    if not source:
        return None
    if str(getattr(document, "source_type", "") or "") == "machine":
        return _optional_int(getattr(source, "id", None))
    machine_id = getattr(source, "machine_id", None)
    if machine_id not in (None, ""):
        return _optional_int(machine_id)
    machine = getattr(source, "machine", None)
    return _optional_int(getattr(machine, "id", None))


def _generated_document_entity_metadata(document_id):
    """Return entity metadata for a generated document source."""
    source = db.session.get(GeneratedDocument, document_id)
    if not source:
        return {}
    return {
        "machine": source.machine,
        "department": source.department,
        "document_type": source.document_type,
    }


def _error_entry_entity_metadata(error_id):
    """Return entity metadata for an error catalog source."""
    entry = db.session.get(ErrorEntry, error_id)
    if not entry:
        return {}
    return {
        "machine": entry.machine,
        "error_code": entry.error_code,
        "department": entry.department.name if entry.department else "",
    }


def _task_entity_metadata(task_id):
    """Return entity metadata for a task source."""
    task = db.session.get(Task, task_id)
    if not task:
        return {}
    return {
        "department": task.department.name if task.department else "",
        "task_status": task.status.value if task.status else "",
        "task_priority": task.priority.value if task.priority else "",
    }


def _machine_entity_metadata(machine_id):
    """Return entity metadata for a machine source."""
    machine = db.session.get(Machine, machine_id)
    if not machine:
        return {}
    return {
        "machine": machine.name,
        "component": machine.produced_item,
    }


def _inventory_entity_metadata(material_id):
    """Return entity metadata for an inventory source."""
    material = db.session.get(InventoryMaterial, material_id)
    if not material:
        return {}
    return {
        "inventory_part": material.name,
        "manufacturer": material.manufacturer,
        "machine": material.machine.name if material.machine else "",
    }


def _maintenance_plan_entity_metadata(plan_id):
    """Return entity metadata for a maintenance-plan source."""
    plan = db.session.get(MaintenancePlan, plan_id)
    if not plan:
        return {}
    return {
        "machine": plan.machine.name if plan.machine else "",
        "department": plan.department.name if plan.department else "",
    }


def _machine_manual_entity_metadata(manual_id):
    """Return entity metadata for an uploaded machine manual source."""
    manual = db.session.get(MachineManual, manual_id)
    if not manual:
        return {}
    return {
        "machine": manual.machine.name if manual.machine else "",
        "department": manual.department,
    }


def _shift_handover_entity_metadata(handover_id):
    """Return entity metadata for a shift handover source."""
    handover = db.session.get(ShiftHandover, handover_id)
    if not handover:
        return {}
    return {
        "machine": handover.machine.name if handover.machine else "",
        "department": handover.department,
        "shift_type": handover.shift_type,
    }


def _manual_training_entity_metadata(entry_id):
    """Return entity metadata for manual assistant training."""
    entry = db.session.get(AssistantTrainingEntry, entry_id)
    if not entry:
        return {}
    return {
        "department": entry.department,
        "category": entry.category,
        "keywords": entry.keywords,
    }


__all__ = [
    "_public_source_entity_metadata",
    "stored_chunk_metadata",
    "_chunk_payload_text",
    "_chunk_payload_metadata",
    "_entities_to_json_with_chunk_metadata",
    "_safe_chunk_metadata",
    "_optional_int",
    "document_entity_metadata",
    "_source_entity_metadata",
    "structured_source_record",
    "structured_source_created_at",
    "structured_source_machine_id",
    "_generated_document_entity_metadata",
    "_error_entry_entity_metadata",
    "_task_entity_metadata",
    "_machine_entity_metadata",
    "_inventory_entity_metadata",
    "_maintenance_plan_entity_metadata",
    "_machine_manual_entity_metadata",
    "_shift_handover_entity_metadata",
    "_manual_training_entity_metadata",
]
