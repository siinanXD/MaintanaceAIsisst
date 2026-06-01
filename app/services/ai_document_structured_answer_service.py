"""Structured AI answers for document metadata questions."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.models import GeneratedDocument, MachineManual
from app.security import has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import detect_department, normalize_text
from app.services.ai_structured_source_service import (
    document_source_cards,
    manual_source_cards,
    module_count_source_card,
)
from app.services.document_service import visible_documents_query, visible_manuals_query

MAX_ITEMS = 20
MAX_ANSWER_ITEMS = 10
OUTDATED_STATUSES = {"outdated", "stale", "veraltet"}


def answer_document_structured_question(message, user):
    """Return a structured document answer for supported metadata questions."""
    text = normalize_text(message)
    if not _is_document_question(text) or _is_content_question(text):
        return None
    if not has_dashboard_permission(user, "documents", "view"):
        return _permission_denied()
    if _is_recent_question(text):
        return _answer_recent_documents(user)
    if _is_outdated_question(text):
        return _answer_outdated_documents(user)
    if _is_this_week_question(text):
        return _answer_this_week_documents(user)
    department = detect_department(message)
    if department:
        return _answer_department_documents(user, department)
    machine = _requested_machine(message, user)
    if machine:
        return _answer_machine_documents(user, machine)
    return None


def _permission_denied():
    """Return a permission-denied document answer."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer("Dokumente", "documents"),
        "data": [],
        "sources": [],
        "scope": "documents",
        "structured_context": {"entity_type": "documents"},
    }


def _answer_recent_documents(user):
    """Return recently changed visible document metadata."""
    documents = visible_documents_query(user).limit(MAX_ITEMS).all()
    manuals = visible_manuals_query(user).limit(MAX_ITEMS).all()
    items = sorted(
        [_document_item(document) for document in documents]
        + [_manual_item(manual) for manual in manuals],
        key=lambda item: item.get("updated_at") or item.get("created_at") or "",
        reverse=True,
    )[:MAX_ITEMS]
    return _document_result("document_recent", "Zuletzt geaenderte Dokumente", items, user)


def _answer_outdated_documents(user):
    """Return visible documents marked as outdated in structured metadata."""
    documents = [
        document
        for document in visible_documents_query(user).limit(MAX_ITEMS).all()
        if _is_outdated_document(document)
    ]
    items = [_document_item(document) for document in documents]
    return _document_result("document_outdated", "Veraltete Dokumente", items, user)


def _answer_this_week_documents(user):
    """Return visible documents created or uploaded during the current week."""
    start = _week_start()
    documents = (
        visible_documents_query(user)
        .filter(GeneratedDocument.created_at >= start)
        .order_by(GeneratedDocument.created_at.desc(), GeneratedDocument.id.desc())
        .limit(MAX_ITEMS)
        .all()
    )
    manuals = (
        visible_manuals_query(user)
        .filter(MachineManual.created_at >= start)
        .order_by(MachineManual.created_at.desc(), MachineManual.id.desc())
        .limit(MAX_ITEMS)
        .all()
    )
    items = sorted(
        [_document_item(document) for document in documents]
        + [_manual_item(manual) for manual in manuals],
        key=lambda item: item.get("created_at") or "",
        reverse=True,
    )[:MAX_ITEMS]
    return _document_result("document_this_week", "Diese Woche hochgeladen", items, user)


def _answer_department_documents(user, department):
    """Return visible documents for one department."""
    documents = (
        visible_documents_query(user)
        .filter(GeneratedDocument.department.ilike(department))
        .order_by(GeneratedDocument.created_at.desc(), GeneratedDocument.id.desc())
        .limit(MAX_ITEMS)
        .all()
    )
    manuals = (
        visible_manuals_query(user)
        .filter(MachineManual.department.ilike(department))
        .order_by(MachineManual.created_at.desc(), MachineManual.id.desc())
        .limit(MAX_ITEMS)
        .all()
    )
    items = [_document_item(document) for document in documents] + [
        _manual_item(manual) for manual in manuals
    ]
    return _document_result(
        "document_department_list",
        f"Dokumente {department}",
        items,
        user,
    )


def _answer_machine_documents(user, machine):
    """Return visible documents for one machine name."""
    documents = [
        document
        for document in visible_documents_query(user).limit(MAX_ITEMS).all()
        if normalize_text(machine) in normalize_text(document.machine)
    ]
    manuals = [
        manual
        for manual in visible_manuals_query(user).limit(MAX_ITEMS).all()
        if normalize_text(machine) in normalize_text(_manual_machine_name(manual))
    ]
    items = [_document_item(document) for document in documents] + [
        _manual_item(manual) for manual in manuals
    ]
    return _document_result("document_machine_list", f"Dokumente zu {machine}", items, user)


def _document_result(response_type, title, items, user):
    """Return a structured document result."""
    answer = _format_document_answer(title, items)
    documents = [item["record"] for item in items if item["kind"] == "generated_document"]
    manuals = [item["record"] for item in items if item["kind"] == "machine_manual"]
    sources = document_source_cards(documents) + manual_source_cards(manuals)
    if not sources:
        aggregate_source = module_count_source_card("documents", len(items), user)
        sources = [aggregate_source] if aggregate_source else []
    public_items = [
        {key: value for key, value in item.items() if key != "record"} for item in items
    ]
    return {
        "type": response_type,
        "answer": answer,
        "data": {
            "entity_type": "documents",
            "query": response_type,
            "count": len(public_items),
            "items": public_items,
        },
        "sources": sources,
        "scope": "documents",
        "structured_context": {"entity_type": "documents"},
    }


def _document_item(document):
    """Return safe generated-document metadata for structured answers."""
    return {
        "kind": "generated_document",
        "id": document.id,
        "title": document.title,
        "document_type": document.document_type,
        "department": document.department,
        "machine": document.machine,
        "machine_id": document.machine_id,
        "status": document.status,
        "quality_status": document.quality_status,
        "created_at": document.created_at.isoformat() if document.created_at else "",
        "updated_at": _document_updated_at(document),
        "record": document,
    }


def _manual_item(manual):
    """Return safe machine-manual metadata for structured answers."""
    return {
        "kind": "machine_manual",
        "id": manual.id,
        "title": manual.title,
        "document_type": "machine_manual",
        "department": manual.department,
        "machine": _manual_machine_name(manual),
        "machine_id": manual.machine_id,
        "created_at": manual.created_at.isoformat() if manual.created_at else "",
        "updated_at": manual.updated_at.isoformat() if manual.updated_at else "",
        "record": manual,
    }


def _format_document_answer(title, items):
    """Return a compact German document metadata answer."""
    lines = [
        f"## {title}",
        f"- **Sichtbare Dokumente:** {len(items)}",
        "- **Quelle:** Strukturierte Dokument-Metadaten",
    ]
    if not items:
        lines.append("")
        lines.append("Keine sichtbaren Dokumente fuer diese Anfrage gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Dokumente:")
    for item in items[:MAX_ANSWER_ITEMS]:
        machine = f", Maschine {item['machine']}" if item.get("machine") else ""
        lines.append(f"- {item['title']} ({item['department']}{machine})")
    if len(items) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(items) - MAX_ANSWER_ITEMS} weitere sichtbare Dokumente")
    return "\n".join(lines)


def _requested_machine(message, user):
    """Return a visible machine name mentioned in the question."""
    text = normalize_text(message)
    if not any(term in text for term in ("maschine", "anlage")):
        return ""
    for machine_name in _visible_machine_names(user):
        if machine_name and normalize_text(machine_name) in text:
            return machine_name
    return ""


def _visible_machine_names(user):
    """Return machine names found in visible documents and manuals."""
    names = {
        document.machine
        for document in visible_documents_query(user).with_entities(GeneratedDocument.machine)
    }
    manual_names = {
        _manual_machine_name(manual)
        for manual in visible_manuals_query(user).limit(MAX_ITEMS).all()
    }
    return sorted(name for name in names | manual_names if name)


def _manual_machine_name(manual):
    """Return the machine name linked to a manual."""
    machine = getattr(manual, "machine", None)
    return str(getattr(machine, "name", "") or "")


def _document_updated_at(document):
    """Return the latest safe timestamp for a generated document."""
    version = getattr(document, "current_version", None)
    updated_at = getattr(version, "created_at", None) or getattr(document, "created_at", None)
    return updated_at.isoformat() if updated_at else ""


def _is_outdated_document(document):
    """Return whether structured document metadata marks a document as outdated."""
    return (
        str(getattr(document, "status", "") or "").lower() in OUTDATED_STATUSES
        or str(getattr(document, "quality_status", "") or "").lower() in OUTDATED_STATUSES
    )


def _week_start():
    """Return the start datetime for the current calendar week."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    return datetime.combine(monday, time.min)


def _is_document_question(text):
    """Return whether the text is a supported document metadata question."""
    return any(term in text for term in ("dokument", "dokumente", "manual", "handbuch"))


def _is_content_question(text):
    """Return whether RAG should answer a document content question."""
    return any(term in text for term in ("was steht", "inhalt", "zusammenfassung"))


def _is_recent_question(text):
    """Return whether the text asks for recently changed documents."""
    return "zuletzt" in text and any(term in text for term in ("geaendert", "geandert"))


def _is_outdated_question(text):
    """Return whether the text asks for outdated documents."""
    return any(term in text for term in ("veraltet", "stale", "outdated"))


def _is_this_week_question(text):
    """Return whether the text asks for this week's uploads."""
    return "diese woche" in text and any(term in text for term in ("hochgeladen", "erstellt"))
