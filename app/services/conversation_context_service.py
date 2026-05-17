"""Short-term conversation memory for contextual AI chat turns."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import timedelta

from flask import current_app, has_app_context

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import ChatMessage
from app.services.ai_retrieval import allowed_ai_scopes

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
    "employee_count": {"employees"},
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
    suggested_scopes = _suggested_scopes(reference_detected, machine_names, error_codes)
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
    )


def has_context_reference(message):
    """Return whether a message refers to previous chat context."""
    text = _normalized_lookup_text(message)
    return any(pattern in text for pattern in REFERENCE_PATTERNS)


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
        return {"employees" if scope == "employee" else scope}
    return set()


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
        _clean_markdown(line)
        for line in str(response or "").splitlines()
        if _clean_markdown(line)
    ]
    for line in lines:
        if SOLUTION_LABEL_PATTERN.search(line) or _has_solution_label(line):
            return _bounded_text(line, 280)
    return _bounded_text(lines[0], 220) if lines else ""


def _has_solution_label(value):
    """Return whether a line contains a normalized solution-like label."""
    text = _normalized_lookup_text(value)
    return any(term in text for term in SOLUTION_LABEL_TERMS)


def _suggested_scopes(reference_detected, machine_names, error_codes):
    """Return scopes that should be searched when the new message is referential."""
    if not reference_detected:
        return set()
    scopes = set()
    if machine_names:
        scopes.add("machines")
    if error_codes:
        scopes.add("errors")
    return scopes


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


def _normalized_lookup_text(value):
    """Return lowercase text normalized for German umlaut variants."""
    text = " ".join(str(value or "").lower().split())
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
    }
    for source, target in replacements.items():
        text = text.replace(source, target)
    return text


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
