"""Shared helpers for structured AI answers and session follow-ups."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import (
    contains_any_lookup_term,
    is_structured_follow_up,
    normalize_text,
)
from app.services.ai_structured_constants import MAX_ANSWER_ITEMS

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
    "employee_id",
    "employee_name",
)
BARE_LIST_FOLLOW_UP_RESPONSE_TYPES = frozenset(
    {
        "inventory_count",
        "shiftplan_shift_count",
        "structured_scope",
        "vacation_pending_count",
        "employee_document_count",
    }
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


def is_bare_list_refinement(text):
    """Return whether a message is only a short list refinement such as 'welche'."""
    normalized = normalize_text(text)
    if not normalized:
        return False
    tokens = normalized.split()
    if len(tokens) > 2:
        return False
    return normalized in LIST_FOLLOW_UP_TERMS or normalized in {"davon", "nochmal"}


def supports_bare_list_follow_up(conversation_context):
    """Return whether a bare list refinement can continue the previous structured answer."""
    if not conversation_context:
        return False
    last_response_type = str(getattr(conversation_context, "last_response_type", "") or "")
    if last_response_type in BARE_LIST_FOLLOW_UP_RESPONSE_TYPES:
        return True
    inherited = inherited_structured_scope(conversation_context)
    return bool(inherited.get("entity_type"))


def is_list_follow_up(text, conversation_context=None):
    """Return whether a follow-up asks to list or refine visible structured rows."""
    normalized = normalize_text(text)
    if is_bare_list_refinement(normalized):
        return supports_bare_list_follow_up(conversation_context)
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


def structured_permission_denied(
    *,
    dashboard_label: str,
    scope: str,
    entity_type: str,
) -> dict[str, Any]:
    """Return a permission-denied structured answer envelope."""
    return build_structured_result(
        response_type="permission_denied",
        answer=permission_denied_answer(dashboard_label, scope),
        data=[],
        sources=[],
        scope=scope,
        structured_context=build_structured_context(entity_type),
    )


def build_structured_result(
    *,
    response_type: str,
    answer: str,
    data: Any,
    sources: list[Any],
    scope: str,
    structured_context: dict[str, Any],
) -> dict[str, Any]:
    """Return the standard structured answer payload used by domain services."""
    return {
        "type": response_type,
        "answer": answer,
        "data": data,
        "sources": sources,
        "scope": scope,
        "structured_context": structured_context,
    }


def format_structured_list_answer(
    *,
    title: str,
    label: str,
    items: Sequence[Any],
    count_label: str,
    formatter: Callable[[Any], str],
    source: str = "Strukturierte Daten",
    total_count: int | None = None,
    overflow_suffix: str = "weitere Eintraege",
    empty_message: str = "Keine sichtbaren Eintraege fuer diese Anfrage gefunden.",
) -> str:
    """Return a compact German markdown list answer for structured rows."""
    visible_total = total_count if total_count is not None else len(items)
    lines = [
        f"## {title}",
        f"- **Filter:** {label}",
        f"- **{count_label}:** {visible_total}",
        f"- **Quelle:** {source}",
    ]
    if total_count is not None and total_count > len(items):
        lines.append(
            f"- **Hinweis:** {len(items)} von {total_count} sichtbaren Eintraegen angezeigt"
        )
    if not items:
        lines.append("")
        lines.append(empty_message)
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Eintraege:")
    for item in items[:MAX_ANSWER_ITEMS]:
        lines.append(formatter(item))
    if len(items) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(items) - MAX_ANSWER_ITEMS} {overflow_suffix}")
    return "\n".join(lines)
