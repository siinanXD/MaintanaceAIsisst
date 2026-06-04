"""Short-term conversation memory for contextual AI chat turns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from flask import current_app, has_app_context

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import ChatMessage
from app.services.ai_question_normalizer import (
    detect_department,
    detect_status,
    detect_time_range,
    is_structured_follow_up,
    normalize_text,
)
from app.services.ai_retrieval import allowed_ai_scopes
from app.services.ai_structured_context_helpers import STRUCTURED_CONTEXT_FIELD_KEYS

DEFAULT_CONTEXT_MESSAGES = 4
DEFAULT_CONTEXT_TTL_MINUTES = 120
DEFAULT_CONTEXT_MAX_CHARS = 1400
MAX_SESSION_ID_LENGTH = 120
REFERENCE_PATTERNS = (
    "gleiche maschine",
    "selbe maschine",
    "dieselbe maschine",
    "gleiche anlage",
    "selbe anlage",
    "der fehler von eben",
    "fehler von eben",
    "stoerung von eben",
    "stoerung eben",
    "vorherige loesung",
    "letzte loesung",
    "loesung von eben",
    "antwort von eben",
    "von eben",
)
STRUCTURED_CONTEXT_KEYS = STRUCTURED_CONTEXT_FIELD_KEYS
ENTITY_TYPE_SCOPES = {
    "tasks": "tasks",
    "incidents": "errors",
    "errors": "errors",
    "maintenance": "tasks",
    "employees": "employees",
    "vacations": "employees",
    "documents": "documents",
    "machines": "machines",
    "shiftplans": "shiftplans",
    "inventory": "inventory",
}
SCOPE_ENTITY_TYPES = {
    "tasks": "tasks",
    "errors": "incidents",
    "employees": "employees",
    "documents": "documents",
    "machines": "machines",
    "shiftplans": "shiftplans",
    "inventory": "inventory",
}
MACHINE_PATTERN = re.compile(
    r"\b(?:maschine|anlage|presse|linie|station|roboter|ofen)\s*[a-z0-9-]+\b",
    re.IGNORECASE,
)
ERROR_CODE_PATTERN = re.compile(r"\b[A-Z]{0,4}[- ]?\d{2,5}\b", re.IGNORECASE)
SOLUTION_LABEL_PATTERN = re.compile(
    r"(?:loesung|lösung|pruefung|prüfung|naechster schritt|nächster schritt|empfehlung)",
    re.IGNORECASE,
)
SOLUTION_LABEL_TERMS = (
    "loesung",
    "pruefung",
    "naechster schritt",
    "empfehlung",
)
RESPONSE_TYPE_SCOPES = {
    "tasks_today": {"tasks"},
    "tasks_status": {"tasks"},
    "structured_scope": {"tasks", "errors"},
    "employee_count": {"employees"},
    "employee_document_count": {"employees"},
    "employee_document_list": {"employees"},
    "employee_stored_document_list": {"employees"},
    "employee_stored_document_count": {"employees"},
    "employee_department_count": {"employees"},
    "employee_department_list": {"employees"},
    "employee_available": {"employees"},
    "employee_absences": {"employees"},
    "employee_team_lead_unavailable": {"employees"},
    "inventory_count": {"inventory"},
    "inventory_low_stock": {"inventory"},
    "inventory_critical": {"inventory"},
    "inventory_machine_materials": {"inventory"},
    "document_recent": {"documents"},
    "document_outdated": {"documents"},
    "document_this_week": {"documents"},
    "document_department_list": {"documents"},
    "document_machine_list": {"documents"},
    "vacation_own_pending": {"employees"},
    "vacation_own_status": {"employees"},
    "vacation_absences": {"employees"},
    "vacation_pending_count": {"employees"},
    "vacation_pending_list": {"employees"},
    "shiftplan_entries": {"shiftplans"},
    "shiftplan_shift_count": {"shiftplans"},
    "shiftplan_understaffed": {"shiftplans"},
    "machine_downtime": {"machines"},
    "machine_incidents": {"machines", "errors"},
    "error_help": {"errors"},
    "order_plan": {"tasks", "machines", "inventory", "employees"},
}
SAFE_UNSCOPED_RESPONSE_TYPES = {
    "general_chat",
    "permission_denied",
}


@dataclass(frozen=True)
class ConversationContext:
    """Bounded context extracted from recent chat turns."""

    session_id: str
    reference_detected: bool
    message_count: int = 0
    machine_names: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    previous_solution: str = ""
    previous_question: str = ""
    context_text: str = ""
    suggested_scopes: frozenset[str] = field(default_factory=frozenset)
    recent_scopes: tuple[str, ...] = ()
    structured_scope: dict = field(default_factory=dict)
    last_response_type: str = ""

    @property
    def applied(self):
        """Return whether contextual data is available for this turn."""
        return bool(self.reference_detected and self.context_text)

    def retrieval_query(self, message):
        """Return a retrieval query augmented only when a reference needs context."""
        base_message = str(message or "").strip()
        if not self.applied:
            return base_message
        reference_terms = " ".join(
            part
            for part in (
                " ".join(self.machine_names),
                " ".join(self.error_codes),
                self.previous_solution,
                self.previous_question,
            )
            if part
        )
        return f"{base_message}\nKontextreferenzen: {reference_terms[:500]}".strip()

    def prompt_context(self, context=""):
        """Return prompt context with the short conversation memory prepended."""
        base_context = str(context or "").strip()
        if not self.applied:
            return base_context
        if base_context:
            return f"{self.context_text}\n\n{base_context}"
        return self.context_text

    def diagnostics(self):
        """Return content-light diagnostics for audit and debugging."""
        return {
            "enabled": True,
            "session_id_present": bool(self.session_id),
            "reference_detected": self.reference_detected,
            "applied": self.applied,
            "message_count": self.message_count,
            "machine_names": list(self.machine_names),
            "error_codes": list(self.error_codes),
            "suggested_scopes": sorted(self.suggested_scopes),
            "recent_scopes": list(self.recent_scopes),
            "structured_scope": dict(self.structured_scope),
            "last_response_type": self.last_response_type,
        }


def normalize_session_id(value):
    """Return a safe optional chat session identifier."""
    normalized = re.sub(r"[^a-zA-Z0-9_.:-]+", "-", str(value or "").strip())
    return normalized[:MAX_SESSION_ID_LENGTH]


def conversation_context_for_chat(user, message, session_id=""):
    """Build bounded short-term context for one chat turn."""
    normalized_session_id = normalize_session_id(session_id)
    reference_detected = has_context_reference(message)
    if not user:
        return _empty_context(normalized_session_id, reference_detected)

    messages = _recent_session_messages(user, normalized_session_id)
    allowed_scopes = allowed_ai_scopes(user)
    scoped_messages = [
        chat for chat in messages if _chat_allowed_by_current_permissions(chat, allowed_scopes)
    ]
    if not scoped_messages:
        return _empty_context(normalized_session_id, reference_detected)

    machine_names = _unique_limited(
        value
        for chat in scoped_messages
        for value in _extract_machines(f"{chat.message}\n{chat.response}")
    )
    error_codes = _unique_limited(
        value
        for chat in scoped_messages
        for value in _extract_error_codes(f"{chat.message}\n{chat.response}")
    )
    previous_solution = _previous_solution(scoped_messages)
    previous_question = _bounded_text(scoped_messages[-1].message, 220)
    structured_scope = _structured_scope(scoped_messages)
    last_response_type = (
        str(scoped_messages[-1].response_type or "").strip() if scoped_messages else ""
    )
    suggested_scopes = _suggested_scopes(
        reference_detected,
        machine_names,
        error_codes,
        structured_scope,
    )
    recent_scopes = _recent_scopes(scoped_messages)
    context_text = _context_text(
        scoped_messages=scoped_messages,
        machine_names=machine_names,
        error_codes=error_codes,
        previous_solution=previous_solution,
        previous_question=previous_question,
    )
    return ConversationContext(
        session_id=normalized_session_id,
        reference_detected=reference_detected,
        message_count=len(scoped_messages),
        machine_names=tuple(machine_names),
        error_codes=tuple(error_codes),
        previous_solution=previous_solution,
        previous_question=previous_question,
        context_text=context_text,
        suggested_scopes=frozenset(suggested_scopes),
        recent_scopes=recent_scopes,
        structured_scope=structured_scope,
        last_response_type=last_response_type,
    )


def has_context_reference(message):
    """Return whether a message refers to previous chat context."""
    text = _conversation_lookup_text(message)
    return any(pattern in text for pattern in REFERENCE_PATTERNS) or is_structured_follow_up(text)


def structured_scope_to_dashboard_scope(structured_scope):
    """Return the dashboard permission scope for a structured memory payload."""
    entity_type = str((structured_scope or {}).get("entity_type") or "").strip()
    return ENTITY_TYPE_SCOPES.get(entity_type)


def build_structured_context_metadata(message, result, requested_scopes=None):
    """Return compact structured scope metadata to persist with chat diagnostics."""
    explicit = _safe_structured_context(result.get("structured_context") if result else None)
    inferred = _structured_context_from_message(message, requested_scopes or set())
    context = {**inferred, **explicit}
    if not context.get("entity_type"):
        return {}
    return {
        key: value for key, value in context.items() if key in STRUCTURED_CONTEXT_KEYS and value
    }


def _recent_session_messages(user, session_id):
    """Return recent chat messages for the user and session only."""
    since = utc_now() - timedelta(minutes=_context_ttl_minutes())
    query = ChatMessage.query.filter(
        ChatMessage.user_id == user.id,
        ChatMessage.created_at >= since,
    )
    if session_id:
        query = query.filter(ChatMessage.session_id == session_id)
    else:
        query = query.filter(db.or_(ChatMessage.session_id == "", ChatMessage.session_id.is_(None)))
    messages = (
        query.order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(_context_message_limit())
        .all()
    )
    return list(reversed(messages))


def _chat_allowed_by_current_permissions(chat, allowed_scopes):
    """Return whether a prior message can be reused with current permissions."""
    scopes = _chat_scopes(chat)
    if not scopes:
        return str(chat.response_type or "") in SAFE_UNSCOPED_RESPONSE_TYPES
    return scopes <= set(allowed_scopes)


def _chat_scopes(chat):
    """Return stored or inferred permission scopes for a chat message."""
    diagnostics = chat.diagnostics()
    scopes = set(diagnostics.get("scopes") or [])
    if scopes:
        return scopes
    response_type = str(chat.response_type or "")
    if response_type in RESPONSE_TYPE_SCOPES:
        return set(RESPONSE_TYPE_SCOPES[response_type])
    if response_type.endswith("_count"):
        scope = response_type.removesuffix("_count")
        if scope.startswith("employee") or scope.startswith("vacation"):
            return {"employees"}
        if scope.startswith("inventory"):
            return {"inventory"}
        if scope.startswith("document"):
            return {"documents"}
        if scope.startswith("shiftplan"):
            return {"shiftplans"}
        return {"employees" if scope == "employee" else scope}
    return set()


def _recent_scopes(messages):
    """Return the union of scoped modules from recent allowed chat messages."""
    scopes = set()
    for chat in messages:
        scopes |= _chat_scopes(chat)
    return tuple(sorted(scopes))


def _structured_scope(messages):
    """Return the most recent structured scope memory from allowed chat messages."""
    for chat in reversed(messages):
        context = _safe_structured_context(chat.diagnostics().get("structured_context"))
        if context:
            return context
    return {}


def _safe_structured_context(value):
    """Return a sanitized structured context dictionary."""
    if not isinstance(value, dict):
        return {}
    context = {}
    for key in STRUCTURED_CONTEXT_KEYS:
        raw_value = value.get(key)
        if raw_value in (None, ""):
            continue
        context[key] = _bounded_text(raw_value, 120)
    entity_type = context.get("entity_type")
    if entity_type and entity_type not in ENTITY_TYPE_SCOPES:
        return {}
    return context


def _context_text(
    scoped_messages,
    machine_names,
    error_codes,
    previous_solution,
    previous_question,
):
    """Return a compact natural-language context block for AI prompts."""
    parts = ["Kurzzeit-Gespraechskontext dieser Session:"]
    if machine_names:
        parts.append(f"- Zuletzt genannte Maschine: {', '.join(machine_names)}")
    if error_codes:
        parts.append(f"- Zuletzt genannter Fehlercode: {', '.join(error_codes)}")
    if previous_question:
        parts.append(f"- Vorherige Frage: {previous_question}")
    if previous_solution:
        parts.append(f"- Vorherige Loesung/Antwort: {previous_solution}")
    parts.append(
        "- Regel: Nutze diesen Kurzkontext nur zur Aufloesung von Referenzen "
        "wie 'gleiche Maschine', 'Fehler von eben' oder 'vorherige Loesung'.",
    )
    text = "\n".join(parts)
    return text[: _context_max_chars()] if scoped_messages else ""


def _extract_machines(text):
    """Return machine-like labels from text."""
    return [_normalize_label(match.group(0)) for match in MACHINE_PATTERN.finditer(text or "")]


def _extract_error_codes(text):
    """Return likely technical error codes from text."""
    values = []
    for match in ERROR_CODE_PATTERN.finditer(str(text or "").upper()):
        code = match.group(0).strip().replace(" ", "-")
        if code.isdigit() and len(code) < 3:
            continue
        values.append(code)
    return values


def _previous_solution(messages):
    """Return a compact previous solution or answer summary."""
    for chat in reversed(messages):
        summary = _solution_summary(chat.response)
        if summary:
            return summary
    return ""


def _solution_summary(response):
    """Return one bounded answer line useful for reference resolution."""
    lines = [
        _clean_markdown(line) for line in str(response or "").splitlines() if _clean_markdown(line)
    ]
    for line in lines:
        if SOLUTION_LABEL_PATTERN.search(line) or _has_solution_label(line):
            return _bounded_text(line, 280)
    return _bounded_text(lines[0], 220) if lines else ""


def _has_solution_label(value):
    """Return whether a line contains a normalized solution-like label."""
    text = _conversation_lookup_text(value)
    return any(term in text for term in SOLUTION_LABEL_TERMS)


def _suggested_scopes(reference_detected, machine_names, error_codes, structured_scope=None):
    """Return scopes that should be searched when the new message is referential."""
    if not reference_detected:
        return set()
    scopes = set()
    structured_dashboard_scope = structured_scope_to_dashboard_scope(structured_scope)
    if structured_dashboard_scope:
        scopes.add(structured_dashboard_scope)
    if machine_names:
        scopes.add("machines")
    if error_codes:
        scopes.add("errors")
    return scopes


def _structured_context_from_message(message, requested_scopes):
    """Infer structured context fields from the current user message."""
    text = _conversation_lookup_text(message)
    entity_type = _entity_type_from_scopes(requested_scopes) or _entity_type_from_text(text)
    context = {}
    if entity_type:
        context["entity_type"] = entity_type
    status = detect_status(text)
    if status:
        context["status"] = status
    time_range = detect_time_range(text)
    if time_range:
        context["time_range"] = time_range
    department = detect_department(text)
    if department:
        context["department"] = department
    machine_names = _unique_limited(_extract_machines(message), limit=1)
    if machine_names:
        context["machine"] = machine_names[0]
    return context


def _entity_type_from_scopes(scopes):
    """Return the structured entity type for explicit requested scopes."""
    for scope in ("tasks", "errors", "employees", "documents", "machines", "shiftplans"):
        if scope in set(scopes or []):
            return SCOPE_ENTITY_TYPES.get(scope)
    return ""


def _entity_type_from_text(text):
    """Return a structured entity type from normalized user wording."""
    if any(term in text for term in ("task", "tasks", "aufgabe", "aufgaben")):
        return "tasks"
    if any(term in text for term in ("stoerung", "stoerungen", "fehler", "incident")):
        return "incidents"
    if any(term in text for term in ("wartung", "maintenance")):
        return "maintenance"
    if any(term in text for term in ("mitarbeiter", "personal", "employee")):
        return "employees"
    if any(term in text for term in ("dokument", "dokumente", "document")):
        return "documents"
    return ""


def _empty_context(session_id, reference_detected):
    """Return an empty conversation context."""
    return ConversationContext(
        session_id=session_id,
        reference_detected=reference_detected,
    )


def _unique_limited(values, limit=5):
    """Return unique non-empty values preserving order."""
    seen = set()
    result = []
    for value in values:
        normalized = str(value or "").strip()
        key = normalized.lower()
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _normalize_label(value):
    """Return a normalized title-like technical label."""
    return " ".join(str(value or "").strip().split())


def _clean_markdown(value):
    """Return a compact text line without lightweight Markdown decoration."""
    text = re.sub(r"^[#\-\s*]+", "", str(value or "").strip())
    text = text.replace("**", "")
    return " ".join(text.split())


def _conversation_lookup_text(value):
    """Return lowercase text normalized for German umlaut variants."""
    return normalize_text(value, strip_punctuation=False)


def _bounded_text(value, max_chars):
    """Return compact text bounded to a maximum length."""
    text = " ".join(str(value or "").strip().split())
    return text[:max_chars]


def _context_message_limit():
    """Return the number of recent chat turns allowed in memory."""
    return _positive_int_config("AI_SESSION_CONTEXT_MESSAGES", DEFAULT_CONTEXT_MESSAGES)


def _context_ttl_minutes():
    """Return the short-term context lifetime in minutes."""
    return _positive_int_config("AI_SESSION_CONTEXT_TTL_MINUTES", DEFAULT_CONTEXT_TTL_MINUTES)


def _context_max_chars():
    """Return the maximum prompt characters for conversation context."""
    return _positive_int_config("AI_SESSION_CONTEXT_MAX_CHARS", DEFAULT_CONTEXT_MAX_CHARS)


def _positive_int_config(name, default):
    """Return a positive integer config value."""
    value = current_app.config.get(name, default) if has_app_context() else default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
