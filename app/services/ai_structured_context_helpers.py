"""Shared helpers for structured AI answers and session follow-ups."""

from __future__ import annotations

from app.services.ai_question_normalizer import (
    contains_any_lookup_term,
    is_structured_follow_up,
    normalize_text,
)

LIST_FOLLOW_UP_TERMS = ("welche", "zeige", "zeig", "liste", "auflisten", "anzeigen")
DOMAIN_ENTITY_TYPES = frozenset(
    {
        "employees",
        "vacations",
        "documents",
        "inventory",
        "shiftplans",
        "machines",
    }
)
STRUCTURED_CONTEXT_FIELD_KEYS = (
    "entity_type",
    "department",
    "status",
    "time_range",
    "machine",
    "query",
    "shift",
)
TASK_SCOPE_TERMS = (
    "task",
    "tasks",
    "aufgabe",
    "aufgaben",
    "arbeit",
    "arbeiten",
    "todo",
)
INCIDENT_SCOPE_TERMS = (
    "stoerung",
    "stoerungen",
    "stoerfall",
    "stoerfaelle",
    "fehler",
    "problem",
    "probleme",
    "incident",
    "incidents",
)
EMPLOYEE_DOCUMENT_TERMS = (
    "dokument",
    "dokumente",
    "unterlage",
    "unterlagen",
    "datei",
    "dateien",
)
DOMAIN_SCOPE_BY_ENTITY = {
    "employees": "employees",
    "vacations": "employees",
    "documents": "documents",
    "inventory": "inventory",
    "shiftplans": "shiftplans",
    "machines": "machines",
}


def inherited_structured_scope(conversation_context):
    """Return the structured scope payload inherited from recent chat turns."""
    return dict(getattr(conversation_context, "structured_scope", {}) or {})


def build_structured_context(entity_type, **fields):
    """Return a compact structured memory payload for chat diagnostics."""
    context = {"entity_type": str(entity_type or "").strip()}
    for key in STRUCTURED_CONTEXT_FIELD_KEYS:
        if key == "entity_type":
            continue
        value = fields.get(key)
        if value in (None, ""):
            continue
        context[key] = str(value).strip()[:120]
    if not context.get("entity_type"):
        return {}
    return context


def is_list_follow_up(text):
    """Return whether a follow-up asks to list or refine visible structured rows."""
    normalized = normalize_text(text)
    return is_structured_follow_up(normalized) and any(
        term in normalized for term in LIST_FOLLOW_UP_TERMS
    )


def mentions_employee_documents(text):
    """Return whether the text refers to employee-attached documents."""
    normalized = normalize_text(text)
    return any(term in normalized for term in EMPLOYEE_DOCUMENT_TERMS)


def explicit_task_or_incident_entity(text):
    """Return whether the text explicitly asks for tasks or incidents."""
    normalized = normalize_text(text)
    if contains_any_lookup_term(normalized, TASK_SCOPE_TERMS):
        return "tasks"
    if any(term in normalized for term in INCIDENT_SCOPE_TERMS):
        return "incidents"
    return ""


def should_defer_structured_scope_follow_up(text, conversation_context):
    """Return whether a follow-up should stay on a domain structured handler."""
    normalized = normalize_text(text)
    if not is_structured_follow_up(normalized):
        return False
    if explicit_task_or_incident_entity(normalized):
        return False
    if mentions_employee_documents(normalized):
        structured = inherited_structured_scope(conversation_context)
        if structured.get("entity_type") == "employees":
            return True
        recent_scopes = set(getattr(conversation_context, "recent_scopes", ()) or ())
        return "employees" in recent_scopes

    structured = inherited_structured_scope(conversation_context)
    entity_type = str(structured.get("entity_type") or "").strip()
    if entity_type in DOMAIN_ENTITY_TYPES:
        return True

    recent_scopes = set(getattr(conversation_context, "recent_scopes", ()) or ())
    if recent_scopes & set(DOMAIN_SCOPE_BY_ENTITY.values()):
        return any(
            marker in normalized
            for marker in LIST_FOLLOW_UP_TERMS + ("davon", "noch offen", "nur die")
        )
    return False
