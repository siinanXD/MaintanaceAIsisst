"""SQL keyword fallback retrieval for structured maintenance data."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from sqlalchemy import or_

from app.models import (
    AssistantTrainingEntry,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeDocument,
    Machine,
    MachineManual,
    MaintenancePlan,
    ShiftHandover,
    Task,
)
from app.security import has_dashboard_permission
from app.services.document_service import visible_documents_query, visible_manuals_query
from app.services.error_service import visible_errors_query
from app.services.retrieval_candidate_service import (
    RetrievalCandidate,
    normalize_retrieval_score,
    rank_candidates,
)
from app.services.retrieval_debug_service import retrieval_debug_decision
from app.services.source_visibility_policy import SOURCE_VISIBILITY_POLICY
from app.services.structured_retrieval_metadata_service import (
    structured_record_scope_metadata,
)
from app.services.task_service import visible_tasks_query
from app.services.text_normalization_service import normalize_text, tokenize_text

MAX_SQL_FALLBACK_PER_SOURCE = 20
EXACT_MATCH_SCORE = 180.0
PHRASE_MATCH_SCORE = 90.0
TOKEN_MATCH_SCORE = 16.0
SOURCE_PRIORITY = {
    "error": 30.0,
    "task": 24.0,
    "machine": 22.0,
    "inventory": 18.0,
    "maintenance_plan": 16.0,
    "document": 14.0,
    "machine_manual": 14.0,
    "shift_handover": 12.0,
    "manual_training": 10.0,
}
TOKEN_SYNONYMS = {
    "anlage": {"maschine", "machine"},
    "anlagen": {"maschine", "maschinen", "machine"},
    "anleitung": {"handbuch", "manual", "dokument"},
    "auftrag": {"task", "aufgabe"},
    "aufgabe": {"task", "auftrag"},
    "defekt": {"fehler", "stoerung"},
    "dokument": {"bericht", "report", "handbuch"},
    "dokumente": {"berichte", "reports", "handbuch"},
    "error": {"fehler", "stoerung"},
    "ersatzteil": {"material", "lager"},
    "fehler": {"error", "stoerung", "defekt"},
    "handbuch": {"manual", "anleitung", "dokument"},
    "lager": {"inventory", "material", "ersatzteil"},
    "machine": {"maschine", "anlage"},
    "manual": {"handbuch", "anleitung", "dokument"},
    "material": {"ersatzteil", "lager", "inventory"},
    "maschine": {"anlage", "machine"},
    "maschinen": {"anlagen", "machine"},
    "report": {"bericht", "dokument"},
    "stoerung": {"fehler", "error", "defekt"},
    "halt": {"not-halt", "notaus", "not-aus"},
    "kreis": {"not-halt-kreis", "sicherheitskreis"},
    "task": {"aufgabe", "auftrag"},
    "teil": {"material", "ersatzteil"},
}
TASK_ID_PATTERN = re.compile(r"\b(?:task|aufgabe)\s*#?\s*(\d+)\b", re.IGNORECASE)
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SqlKeywordHit:
    """Internal SQL fallback hit carrying its candidate and safe payload."""

    candidate: RetrievalCandidate
    data_key: str
    payload: dict


def retrieve_sql_keyword_fallback(message, user, existing_sources=None, limit=6):
    """Return visible structured SQL fallback candidates for a retrieval query.

    The fallback supplements vector/RAG retrieval with bounded ``ilike`` searches
    across structured maintenance tables. It expands normalized query tokens with
    a small synonym map, boosts exact identifiers such as task ids and error
    codes, and still delegates visibility to the existing dashboard queries and
    ``SourceVisibilityPolicy``.
    """
    tokens = _query_tokens(message)
    if not tokens:
        return _result([], used=False)

    existing_keys = _existing_source_keys(existing_sources)
    hits = []
    hits.extend(_task_hits(message, user, tokens, existing_keys))
    hits.extend(_error_hits(message, user, tokens, existing_keys))
    hits.extend(_machine_hits(message, user, tokens, existing_keys))
    hits.extend(_inventory_hits(message, user, tokens, existing_keys))
    hits.extend(_maintenance_plan_hits(message, user, tokens, existing_keys))
    hits.extend(_generated_document_hits(message, user, tokens, existing_keys))
    hits.extend(_machine_manual_hits(message, user, tokens, existing_keys))
    hits.extend(_shift_handover_hits(message, user, tokens, existing_keys))
    hits.extend(_manual_training_hits(message, user, tokens, existing_keys))

    ranked_candidates = rank_candidates([hit.candidate for hit in hits], limit)
    selected_hits = _hits_for_candidates(hits, ranked_candidates)
    return _result(selected_hits, used=bool(selected_hits))


def _task_hits(message, user, tokens, existing_keys):
    """Return visible task fallback hits."""
    query = visible_tasks_query(user)
    task_id = _requested_task_id(message)
    if task_id:
        query = query.filter(Task.id == task_id)
    else:
        query = query.filter(
            _ilike_any((Task.title, Task.description, Task.blocked_reason), tokens)
        )
    return [
        _hit(
            record=task,
            data_key="tasks",
            source_type="task",
            source_id=task.id,
            title=task.title,
            module="tasks",
            url="/tasks",
            content=_task_context(task),
            query_text=message,
            searchable_text=_task_text(task),
            exact_texts=(str(task.id), task.title),
            exact_match=bool(task_id and task.id == task_id),
            source_document_type="task",
        )
        for task in query.order_by(Task.updated_at.desc()).limit(MAX_SQL_FALLBACK_PER_SOURCE).all()
        if _source_allowed(user, "task", task.id) and ("task", task.id, None) not in existing_keys
    ]


def _error_hits(message, user, tokens, existing_keys):
    """Return visible error-entry fallback hits."""
    query = visible_errors_query(user).filter(
        _ilike_any(
            (
                ErrorEntry.error_code,
                ErrorEntry.machine,
                ErrorEntry.title,
                ErrorEntry.description,
                ErrorEntry.possible_causes,
                ErrorEntry.solution,
            ),
            tokens,
        )
    )
    return [
        _hit(
            record=entry,
            data_key="errors",
            source_type="error",
            source_id=entry.id,
            title=f"{entry.error_code} - {entry.title}",
            module="errors",
            url="/errors",
            content=_error_context(entry),
            query_text=message,
            searchable_text=_error_text(entry),
            exact_texts=(entry.error_code,),
            source_document_type="error_entry",
        )
        for entry in query.order_by(ErrorEntry.created_at.desc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "error_entry", entry.id)
        and ("error", entry.id, None) not in existing_keys
    ]


def _machine_hits(message, user, tokens, existing_keys):
    """Return visible machine fallback hits."""
    if not has_dashboard_permission(user, "machines", "view"):
        return []
    query = Machine.query.filter(
        _ilike_any((Machine.name, Machine.produced_item, Machine.status), tokens)
    )
    return [
        _hit(
            record=machine,
            data_key="machines",
            source_type="machine",
            source_id=machine.id,
            title=machine.name,
            module="machines",
            url="/machines",
            content=_machine_context(machine),
            query_text=message,
            searchable_text=_machine_text(machine),
            exact_texts=(machine.name,),
            source_document_type="machine",
        )
        for machine in query.order_by(Machine.name.asc()).limit(MAX_SQL_FALLBACK_PER_SOURCE).all()
        if _source_allowed(user, "machine", machine.id)
        and ("machine", machine.id, None) not in existing_keys
    ]


def _inventory_hits(message, user, tokens, existing_keys):
    """Return visible inventory fallback hits."""
    if not has_dashboard_permission(user, "inventory", "view"):
        return []
    query = InventoryMaterial.query.outerjoin(Machine).filter(
        _ilike_any((InventoryMaterial.name, InventoryMaterial.manufacturer, Machine.name), tokens)
    )
    return [
        _hit(
            record=material,
            data_key="inventory",
            source_type="inventory",
            source_id=material.id,
            title=material.name,
            module="inventory",
            url="/inventory",
            content=_material_context(material),
            query_text=message,
            searchable_text=_material_text(material),
            exact_texts=(material.name,),
            source_document_type="inventory_material",
        )
        for material in query.order_by(InventoryMaterial.name.asc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "inventory_material", material.id)
        and ("inventory", material.id, None) not in existing_keys
    ]


def _maintenance_plan_hits(message, user, tokens, existing_keys):
    """Return visible maintenance-plan fallback hits."""
    if not has_dashboard_permission(user, "machines", "view"):
        return []
    from app.machines.maintenance_services import visible_maintenance_plans_query

    query = (
        visible_maintenance_plans_query(user)
        .outerjoin(Machine)
        .filter(
            _ilike_any((MaintenancePlan.title, MaintenancePlan.description, Machine.name), tokens)
        )
    )
    return [
        _hit(
            record=plan,
            data_key="maintenance_plans",
            source_type="maintenance_plan",
            source_id=plan.id,
            title=plan.title,
            module="machines",
            url="/machines",
            content=_maintenance_plan_context(plan),
            query_text=message,
            searchable_text=_maintenance_plan_text(plan),
            exact_texts=(plan.title,),
            source_document_type="maintenance_plan",
        )
        for plan in query.order_by(MaintenancePlan.updated_at.desc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "maintenance_plan", plan.id)
        and ("maintenance_plan", plan.id, None) not in existing_keys
    ]


def _generated_document_hits(message, user, tokens, existing_keys):
    """Return visible generated-document fallback hits."""
    if not has_dashboard_permission(user, "documents", "view"):
        return []
    query = visible_documents_query(user).filter(
        _ilike_any(
            (
                GeneratedDocument.title,
                GeneratedDocument.document_type,
                GeneratedDocument.department,
                GeneratedDocument.machine,
                GeneratedDocument.summary,
            ),
            tokens,
        )
    )
    return [
        _hit(
            record=document,
            data_key="documents",
            source_type="document",
            source_id=document.id,
            title=document.title,
            module="documents",
            url="/documents",
            content=_document_context(document),
            query_text=message,
            searchable_text=_document_text(document),
            exact_texts=(document.title,),
            source_document_type="generated_document",
        )
        for document in query.order_by(GeneratedDocument.created_at.desc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "generated_document", document.id)
        and ("document", document.id, None) not in existing_keys
    ]


def _machine_manual_hits(message, user, tokens, existing_keys):
    """Return visible machine-manual fallback hits."""
    if not has_dashboard_permission(user, "documents", "view"):
        return []
    query = (
        visible_manuals_query(user)
        .outerjoin(Machine)
        .filter(
            _ilike_any(
                (
                    MachineManual.title,
                    MachineManual.original_filename,
                    MachineManual.summary,
                    MachineManual.analysis,
                    Machine.name,
                ),
                tokens,
            )
        )
    )
    return [
        _hit(
            record=manual,
            data_key="machine_manuals",
            source_type="machine_manual",
            source_id=manual.id,
            title=manual.title,
            module="documents",
            url="/documents",
            content=_machine_manual_context(manual),
            query_text=message,
            searchable_text=_machine_manual_text(manual),
            exact_texts=(manual.title, manual.original_filename),
            source_document_type="machine_manual",
        )
        for manual in query.order_by(MachineManual.updated_at.desc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "machine_manual", manual.id)
        and ("machine_manual", manual.id, None) not in existing_keys
    ]


def _shift_handover_hits(message, user, tokens, existing_keys):
    """Return visible shift-handover fallback hits."""
    if not has_dashboard_permission(user, "shiftplans", "view"):
        return []
    query = ShiftHandover.query
    if not getattr(user, "is_admin", False):
        department = getattr(getattr(user, "department", None), "name", "")
        query = query.filter(ShiftHandover.department == department)
    query = query.filter(
        _ilike_any(
            (
                ShiftHandover.department,
                ShiftHandover.shift_type,
                ShiftHandover.status,
                ShiftHandover.content,
                ShiftHandover.open_tasks,
                ShiftHandover.machine_notes,
                ShiftHandover.next_notes,
            ),
            tokens,
        )
    )
    return [
        _hit(
            record=handover,
            data_key="shift_handovers",
            source_type="shift_handover",
            source_id=handover.id,
            title=f"Schichtuebergabe {handover.shift_date.isoformat()}",
            module="shiftplans",
            url="/handover",
            content=_shift_handover_context(handover),
            query_text=message,
            searchable_text=_shift_handover_text(handover),
            exact_texts=(handover.shift_date.isoformat(),),
            source_document_type="shift_handover",
        )
        for handover in query.order_by(ShiftHandover.shift_date.desc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "shift_handover", handover.id)
        and ("shift_handover", handover.id, None) not in existing_keys
    ]


def _manual_training_hits(message, user, tokens, existing_keys):
    """Return visible manual-training fallback hits."""
    if not has_dashboard_permission(user, "documents", "view"):
        return []
    query = AssistantTrainingEntry.query.filter(AssistantTrainingEntry.is_active.is_(True))
    if not getattr(user, "is_admin", False):
        department = getattr(getattr(user, "department", None), "name", "")
        query = query.filter(
            or_(
                AssistantTrainingEntry.department == "",
                AssistantTrainingEntry.department == department,
            )
        )
    query = query.filter(
        _ilike_any(
            (
                AssistantTrainingEntry.title,
                AssistantTrainingEntry.question,
                AssistantTrainingEntry.answer,
                AssistantTrainingEntry.keywords,
                AssistantTrainingEntry.category,
            ),
            tokens,
        )
    )
    return [
        _hit(
            record=entry,
            data_key="manual_training",
            source_type="manual_training",
            source_id=entry.id,
            title=entry.title,
            module="admin_ai",
            url="/admin/ai",
            content=_manual_training_context(entry),
            query_text=message,
            searchable_text=_manual_training_text(entry),
            exact_texts=(entry.title,),
            source_document_type="manual_training",
        )
        for entry in query.order_by(AssistantTrainingEntry.priority.desc())
        .limit(MAX_SQL_FALLBACK_PER_SOURCE)
        .all()
        if _source_allowed(user, "manual_training", entry.id)
        and ("manual_training", entry.id, None) not in existing_keys
    ]


def _hit(
    record,
    data_key,
    source_type,
    source_id,
    title,
    module,
    url,
    content,
    query_text,
    searchable_text,
    exact_texts,
    source_document_type,
    exact_match=False,
):
    """Return one SQL keyword hit with calibrated fallback score."""
    raw_score, reason = _score_match(query_text, searchable_text, exact_texts, exact_match)
    final_score = raw_score + SOURCE_PRIORITY.get(source_type, 0.0)
    candidate = RetrievalCandidate(
        source_type=source_type,
        source_id=source_id,
        title=title,
        content=content,
        module=module,
        url=url,
        raw_score=final_score,
        normalized_score=normalize_retrieval_score(final_score, "structured"),
        permission_scope=module,
        explanation=f"SQL-Keyword-Fallback: {reason}",
        metadata={
            "source_kind": "sql_keyword_fallback",
            "knowledge_source_type": source_document_type,
            "module": module,
            "source_record_id": source_id,
            **_safe_source_metadata(record),
        },
    )
    return SqlKeywordHit(candidate=candidate, data_key=data_key, payload=record.to_dict())


def _safe_source_metadata(record):
    """Return display-safe metadata for SQL fallback sources."""
    metadata = structured_record_scope_metadata(record)
    if isinstance(record, Task):
        metadata.update({"department": record.department.name if record.department else ""})
        return metadata
    if isinstance(record, ErrorEntry):
        metadata.update(
            {
                "machine": record.machine,
                "department": record.department.name if record.department else "",
            }
        )
        return metadata
    if isinstance(record, Machine):
        metadata.update({"machine": record.name})
        return metadata
    if isinstance(record, InventoryMaterial):
        metadata.update({"machine": record.machine.name if record.machine else ""})
        return metadata
    if isinstance(record, MaintenancePlan):
        metadata.update(
            {
                "machine": record.machine.name if record.machine else "",
                "department": record.department.name if record.department else "",
            }
        )
        return metadata
    if isinstance(record, GeneratedDocument):
        metadata.update(
            {
                "machine": record.machine,
                "department": record.department,
                "document_type": record.document_type,
            }
        )
        return metadata
    if isinstance(record, MachineManual):
        metadata.update(
            {
                "machine": record.machine.name if record.machine else "",
                "department": record.department,
            }
        )
        return metadata
    if isinstance(record, ShiftHandover):
        metadata.update({"department": record.department})
        return metadata
    if isinstance(record, AssistantTrainingEntry):
        metadata.update({"department": record.department})
        return metadata
    return metadata


def _score_match(query_text, searchable_text, exact_texts, exact_match=False):
    """Return a fallback score and reason for one SQL candidate."""
    normalized_query = normalize_text(query_text)
    normalized_text = normalize_text(searchable_text)
    if exact_match or any(_exact_value_matches(normalized_query, item) for item in exact_texts):
        return EXACT_MATCH_SCORE, "exakter strukturierter Treffer"
    if normalized_query and normalized_query in normalized_text:
        return PHRASE_MATCH_SCORE, "Phrasentreffer in strukturierten Daten"
    overlap = _query_tokens(query_text) & _query_tokens(searchable_text)
    score = max(len(overlap), 1) * TOKEN_MATCH_SCORE
    return score, f"{len(overlap)} SQL-Keyword-Treffer"


def _source_allowed(user, source_type, source_id):
    """Return whether a linked knowledge source permits this SQL fallback hit."""
    documents = KnowledgeDocument.query.filter_by(
        source_type=source_type,
        source_id=source_id,
    ).all()
    if not documents:
        return True
    return any(SOURCE_VISIBILITY_POLICY.can_read(user, document) for document in documents)


def _ilike_any(columns, tokens):
    """Return an OR filter matching any token against the given columns."""
    filters = []
    for token in _bounded_tokens(tokens):
        pattern = f"%{token}%"
        filters.extend(column.ilike(pattern) for column in columns)
    if not filters:
        return False
    return or_(*filters)


def _query_tokens(value):
    """Return normalized SQL fallback query tokens expanded with simple synonyms."""
    tokens = set(tokenize_text(value))
    expanded = set(tokens)
    for token in tokens:
        expanded.update(TOKEN_SYNONYMS.get(str(token).lower(), set()))
    return expanded


def _bounded_tokens(tokens):
    """Return deterministic tokens for SQL ilike filters."""
    values = [str(token or "").strip().lower() for token in tokens if str(token or "").strip()]
    values = [token for token in values if len(token) >= 2]
    values.sort(key=lambda item: (-len(item), item))
    return values[:8]


def _existing_source_keys(sources):
    """Return public source keys already present in retrieval results."""
    keys = set()
    for source in sources or []:
        keys.add((source.get("type"), source.get("id"), source.get("chunk_id")))
    return keys


def _hits_for_candidates(hits, candidates):
    """Return hits matching selected ranked candidates."""
    hit_by_key = {(hit.candidate.source_type, hit.candidate.source_id): hit for hit in hits}
    selected = []
    seen = set()
    for candidate in candidates:
        key = (candidate.source_type, candidate.source_id)
        hit = hit_by_key.get(key)
        if hit and key not in seen:
            selected.append(hit)
            seen.add(key)
    return selected


def _result(hits, used):
    """Return the normalized SQL fallback payload."""
    candidates = [hit.candidate for hit in hits]
    data = {}
    for hit in hits:
        data.setdefault(hit.data_key, []).append(hit.payload)
    logger.info(
        "sql_keyword_retrieval used=%s candidates=%s by_type=%s",
        bool(used),
        len(candidates),
        _count_by_type(candidates),
    )
    return {
        "candidates": candidates,
        "data": data,
        "debug": {
            "keyword_candidates_found": len(candidates),
            "sql_keyword_fallback_used": bool(used),
            "sql_keyword_fallback_candidates_found": len(candidates),
            "sql_keyword_fallback_by_type": _count_by_type(candidates),
            "decision_trace": [
                retrieval_debug_decision(
                    "sql_keyword_fallback",
                    "ok" if candidates else "empty",
                    "ranked_visible_keyword_candidates",
                    {
                        "candidate_count": len(candidates),
                        "used": bool(used),
                        "source_types": _count_by_type(candidates),
                    },
                )
            ],
        },
    }


def _count_by_type(candidates):
    """Return fallback candidate counts grouped by source type."""
    counts = {}
    for candidate in candidates:
        counts[candidate.source_type] = counts.get(candidate.source_type, 0) + 1
    return counts


def _requested_task_id(message):
    """Return an explicitly requested task id from a query, if present."""
    match = TASK_ID_PATTERN.search(str(message or ""))
    return int(match.group(1)) if match else None


def _exact_value_matches(normalized_query, value):
    """Return whether a normalized query contains an exact field value."""
    normalized_value = normalize_text(value)
    return bool(normalized_value and normalized_value in normalized_query)


def _task_text(task):
    """Return searchable task text."""
    return " ".join([task.title, task.description, task.blocked_reason, str(task.id)])


def _task_context(task):
    """Return compact task context."""
    return (
        f"Task #{task.id}: {task.title} | Status: {task.status.value} | "
        f"Prioritaet: {task.priority.value} | Faellig: {task.due_date.isoformat()} | "
        f"Bereich: {task.department.name if task.department else ''} | "
        f"Beschreibung: {task.description}"
    )


def _error_text(entry):
    """Return searchable error text."""
    return " ".join(
        [entry.machine, entry.error_code, entry.title, entry.description, entry.solution]
    )


def _error_context(entry):
    """Return compact error-entry context."""
    return (
        f"Fehler: {entry.error_code} | Maschine: {entry.machine} | Titel: {entry.title} | "
        f"Ursache: {entry.possible_causes} | Loesung: {entry.solution}"
    )


def _machine_text(machine):
    """Return searchable machine text."""
    return " ".join([machine.name, machine.produced_item, machine.status, machine.criticality])


def _machine_context(machine):
    """Return compact machine context."""
    return (
        f"Maschine: {machine.name} | Status: {machine.status} | "
        f"Kritikalitaet: {machine.criticality} | Produkt: {machine.produced_item}"
    )


def _material_text(material):
    """Return searchable inventory material text."""
    machine_name = material.machine.name if material.machine else ""
    return " ".join([material.name, material.manufacturer, material.criticality, machine_name])


def _material_context(material):
    """Return compact inventory material context."""
    machine_name = material.machine.name if material.machine else "nicht zugeordnet"
    return (
        f"Material: {material.name} | Bestand: {material.quantity} | "
        f"Mindestbestand: {material.min_quantity} | Maschine: {machine_name}"
    )


def _maintenance_plan_text(plan):
    """Return searchable maintenance-plan text."""
    machine_name = plan.machine.name if plan.machine else ""
    return " ".join([plan.title, plan.description, machine_name])


def _maintenance_plan_context(plan):
    """Return compact maintenance-plan context."""
    machine_name = plan.machine.name if plan.machine else "nicht zugeordnet"
    return (
        f"Wartungsplan: {plan.title} | Maschine: {machine_name} | "
        f"Intervall: {plan.interval_days} Tage | Naechste Faelligkeit: {plan.next_due_date}"
    )


def _document_text(document):
    """Return searchable generated-document text."""
    return " ".join([document.title, document.document_type, document.machine, document.summary])


def _document_context(document):
    """Return compact generated-document context."""
    return (
        f"Dokument: {document.title} | Typ: {document.document_type} | "
        f"Maschine: {document.machine} | Status: {document.status}"
    )


def _machine_manual_text(manual):
    """Return searchable machine-manual text."""
    machine_name = manual.machine.name if manual.machine else ""
    return " ".join(
        [manual.title, manual.original_filename, manual.summary, manual.analysis, machine_name]
    )


def _machine_manual_context(manual):
    """Return compact machine-manual context."""
    machine_name = manual.machine.name if manual.machine else "nicht zugeordnet"
    return (
        f"Handbuch: {manual.title} | Maschine: {machine_name} | "
        f"Zusammenfassung: {manual.summary}"
    )


def _shift_handover_text(handover):
    """Return searchable shift-handover text."""
    return " ".join(
        [
            handover.department,
            handover.shift_type,
            handover.status,
            handover.content,
            handover.open_tasks,
            handover.machine_notes,
            handover.next_notes,
        ]
    )


def _shift_handover_context(handover):
    """Return compact shift-handover context."""
    return (
        f"Schichtuebergabe: {handover.shift_date.isoformat()} | "
        f"Bereich: {handover.department} | Status: {handover.status} | "
        f"Maschinenhinweise: {handover.machine_notes}"
    )


def _manual_training_text(entry):
    """Return searchable manual-training text."""
    return " ".join([entry.title, entry.question, entry.answer, entry.keywords, entry.category])


def _manual_training_context(entry):
    """Return compact manual-training context."""
    return (
        f"Training: {entry.title} | Kategorie: {entry.category} | "
        f"Frage: {entry.question} | Antwort: {entry.answer}"
    )
