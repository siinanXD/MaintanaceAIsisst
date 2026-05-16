"""Local text knowledge base for AI retrieval."""

import logging
import re
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
from app.security import has_dashboard_permission
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
    visible_documents_query,
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
    extracted_text = (
        manual.current_version.extracted_text if manual.current_version else ""
    )
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


def rebuild_chunks(document, text):
    """Replace all chunks for a knowledge document."""
    KnowledgeChunk.query.filter(KnowledgeChunk.document_id == document.id).delete()
    chunks = chunk_text(text)
    chunk_objects = []
    for index, chunk in enumerate(chunks):
        chunk_object = KnowledgeChunk(
            document_id=document.id,
            chunk_index=index,
            text=chunk,
            token_text=" ".join(sorted(tokens(chunk))),
            created_at=utc_now(),
        )
        db.session.add(chunk_object)
        chunk_objects.append(chunk_object)
    db.session.flush()
    document.chunk_count = len(chunks)
    sync_vector_store_document(document, chunk_objects)


def sync_vector_store_document(document, chunks):
    """Persist indexed chunks in the configured external vector store when enabled."""
    try:
        from app.services.vector_store_service import (
            VectorRecord,
            get_vector_store,
        )
    except ImportError as exc:
        logger.warning("vector_store_import_failed document_id=%s error=%s", document.id, exc)
        return

    store = get_vector_store()
    if getattr(store, "name", "") != "chroma":
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
    except Exception as exc:
        logger.warning("vector_store_sync_failed document_id=%s error=%s", document.id, exc)


def chunk_vector_metadata(document, chunk):
    """Return metadata stored with an external vector record."""
    return {
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
        "url": source_url(document),
        "updated_at": document.updated_at.isoformat() if document.updated_at else "",
    }


def chunk_text(text, max_chars=1400, overlap=160):
    """Split text into stable overlapping chunks."""
    config = ChunkingConfig(max_chars=max_chars, overlap=overlap)
    return [chunk["text"] for chunk in build_text_chunks(text, config=config)]


def tokens(value):
    """Return normalized searchable tokens."""
    return {
        token
        for token in re.sub(
            r"[^a-zA-Z0-9äöüÄÖÜß-]+",
            " ",
            str(value or "").lower(),
        ).split()
        if len(token) >= 3
    }


def search_knowledge_chunks(query_text, user, limit=MAX_RETRIEVAL_CHUNKS):
    """Return ranked knowledge chunks visible to the given user."""
    query_tokens = tokens(query_text)
    if not query_tokens:
        return []

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
        score = len(overlap) * 25
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: (item[0], item[1].document.updated_at), reverse=True)
    return [chunk_payload(chunk, score) for score, chunk in ranked[:limit]]


def can_user_read_knowledge_document(user, document):
    """Return whether a user may use a knowledge document as RAG context."""
    if user.is_admin:
        return True
    if not document.is_public:
        return False
    if document.department and (not user.department or user.department.name != document.department):
        return False
    if document.source_type == "upload":
        return has_dashboard_permission(user, "documents", "view")
    if document.source_type == "generated_document" and document.source_id:
        return (
            visible_documents_query(user).filter(GeneratedDocument.id == document.source_id).first()
            is not None
        )
    if document.source_type == "error_entry" and document.source_id:
        return can_read_error_entry(user, document.source_id)
    if document.source_type == "task" and document.source_id:
        return can_read_task(user, document.source_id)
    if document.source_type == "machine":
        return has_dashboard_permission(user, "machines", "view")
    if document.source_type == "inventory_material":
        return has_dashboard_permission(user, "inventory", "view")
    if document.source_type == "maintenance_plan" and document.source_id:
        return can_read_maintenance_plan(user, document.source_id)
    if document.source_type == "machine_manual":
        return has_dashboard_permission(user, "documents", "view")
    if document.source_type == "shift_handover":
        return has_dashboard_permission(user, "shiftplans", "view")
    if document.source_type == "manual_training" and document.source_id:
        return can_read_training_entry(user, document.source_id)
    return has_dashboard_permission(user, "documents", "view")


def can_read_error_entry(user, error_id):
    """Return whether a user can read an error catalog source."""
    if not has_dashboard_permission(user, "errors", "view"):
        return False
    from app.services.error_service import visible_errors_query

    return visible_errors_query(user).filter(ErrorEntry.id == error_id).first() is not None


def can_read_task(user, task_id):
    """Return whether a user can read a task source."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return False
    from app.services.task_service import visible_tasks_query

    return visible_tasks_query(user).filter(Task.id == task_id).first() is not None


def can_read_maintenance_plan(user, plan_id):
    """Return whether a user can read a recurring maintenance plan source."""
    if not has_dashboard_permission(user, "machines", "view"):
        return False
    from app.machines.maintenance_services import visible_maintenance_plans_query

    return (
        visible_maintenance_plans_query(user)
        .filter(MaintenancePlan.id == plan_id)
        .first()
        is not None
    )


def can_read_training_entry(user, entry_id):
    """Return whether a user can read a manual training source."""
    entry = db.session.get(AssistantTrainingEntry, entry_id)
    if not entry or not entry.is_active:
        return False
    if entry.department and (not user.department or user.department.name != entry.department):
        return False
    return True


def chunk_payload(chunk, score):
    """Return an internal retrieval payload for one chunk."""
    document = chunk.document
    return {
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
        "manual_training": "/admin/ai",
    }
    return urls.get(document.source_type, "/admin/ai")


def knowledge_sources_for_chat(query_text, user):
    """Return context text and public source records for chat retrieval."""
    from app.services.retrieval_service import knowledge_context_for_chat

    return knowledge_context_for_chat(query_text, user, limit=MAX_RETRIEVAL_CHUNKS)


def list_knowledge_documents(args):
    """Return filtered knowledge documents for admin views."""
    query = KnowledgeDocument.query
    q = str(args.get("q") or "").strip()
    status = str(args.get("status") or "").strip()
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
    if source_type:
        query = query.filter(KnowledgeDocument.source_type == source_type)
    return query.order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())


def knowledge_index_status():
    """Return admin-facing RAG index status and searchable source diagnostics."""
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
        "diagnostics": {
            "rag_enabled": bool(current_app.config.get("RAG_ENABLED", True)),
            "vector_store": current_app.config.get("RAG_VECTOR_STORE", "local"),
            "embedding_provider": current_app.config.get("EMBEDDING_PROVIDER", "hashing"),
            "chunk_size": current_app.config.get("RAG_CHUNK_SIZE", 1400),
            "chunk_overlap": current_app.config.get("RAG_CHUNK_OVERLAP", 160),
            "top_k": current_app.config.get("RAG_TOP_K", 4),
            "scan_limit": current_app.config.get("RAG_SCAN_LIMIT", 300),
            "has_errors": errors > 0,
            "ready": bool(indexed and total_chunks and current_app.config.get("RAG_ENABLED", True)),
        },
    }


def reindex_all_knowledge():
    """Register and reindex all supported RAG knowledge documents."""
    ensure_generated_documents_registered()
    ensure_structured_sources_registered()
    documents = KnowledgeDocument.query.order_by(KnowledgeDocument.id.asc()).all()
    for document in documents:
        index_knowledge_document(document)
    db.session.commit()
    return {
        "documents": len(documents),
        "indexed": sum(1 for document in documents if document.status == "indexed"),
        "chunks": sum(document.chunk_count for document in documents),
        "sources": source_type_counts(documents),
    }


def reindex_stale_knowledge():
    """Reindex only stale and pending knowledge documents."""
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
    return {
        "documents": len(documents),
        "indexed": sum(1 for document in documents if document.status == "indexed"),
        "chunks": sum(document.chunk_count for document in documents),
        "sources": source_type_counts(documents),
    }


def reindex_knowledge_document(document):
    """Reindex one knowledge document and commit the result."""
    index_knowledge_document(document)
    db.session.commit()
    return document.to_dict()


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


def existing_source_ids(source_type):
    """Return registered source ids for a knowledge source type."""
    return {
        item.source_id
        for item in KnowledgeDocument.query.filter_by(source_type=source_type).all()
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
    document.error_message = "Task wurde geaendert und muss neu indexiert werden."
    document.updated_at = utc_now()


def mark_training_entry_knowledge_stale(entry):
    """Create or mark a manual training knowledge document as stale after a change."""
    document = source_document("manual_training", entry.id)
    if not document:
        register_training_entry_document(entry)
        return
    document.title = entry.title
    document.department = entry.department
    document.relative_path = "/admin/ai"
    document.status = "stale"
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
    document.error_message = "Fehlerkatalogeintrag wurde geaendert und muss neu indexiert werden."
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
