"""AI orchestration services for permission-aware workflows."""
# ruff: noqa: F401, F821

import logging
import re

from app.security import employee_access_level, has_dashboard_permission
from app.services.ai_prompting import (
    permission_denied_answer,
)

LAST_OPENAI_ERROR = None
OPENAI_PROVIDER = "OpenAI"
logger = logging.getLogger(__name__)

DASHBOARD_SCOPE_LABELS = {
    "tasks": "Tasks",
    "errors": "Fehlerkatalog",
    "employees": "Mitarbeiter",
    "machines": "Maschinen",
    "inventory": "Lager",
    "documents": "Dokumente",
    "shiftplans": "Schichtplanung",
    "admin_users": "Admin Users",
}

SCOPE_KEYWORDS = {
    "tasks": ["task", "tasks", "aufgabe", "aufgaben", "arbeit", "arbeiten", "todo"],
    "errors": [
        "fehler",
        "stoerung",
        "problem",
        "probleme",
        "störung",
        "error",
        "fehlercode",
        "ursache",
    ],
    "employees": [
        "mitarbeiter",
        "personal",
        "personaldaten",
        "gehalt",
        "gehaltsklasse",
        "adresse",
        "geburtsdatum",
        "qualifikation",
    ],
    "machines": [
        "maschine",
        "maschinen",
        "anlage",
        "anlagen",
        "machine",
        "wartungsplan",
        "wartungsplaene",
        "wartungspläne",
        "maintenance",
    ],
    "inventory": ["lager", "bestand", "material", "ersatzteil", "inventory"],
    "documents": [
        "dokument",
        "dokumente",
        "unterlage",
        "unterlagen",
        "doku",
        "bericht",
        "berichte",
        "report",
    ],
    "shiftplans": [
        "schichtplan",
        "schichtplanung",
        "dienstplan",
        "schicht",
        "schichtuebergabe",
        "schichtübergabe",
        "uebergabe",
        "übergabe",
        "handover",
    ],
    "admin_users": [
        "user",
        "users",
        "nutzer",
        "benutzer",
        "accounts",
        "rolle",
        "rollen",
        "berechtigung",
        "berechtigungen",
        "permissions",
    ],
}

COUNT_WORDS = [
    "wie viele",
    "wie vile",
    "wieviele",
    "wievile",
    "anzahl",
    "count",
    "many",
]

GENERAL_KNOWLEDGE_PREFIXES = (
    "was ist",
    "was bedeutet",
    "wie funktioniert",
    "warum",
    "wer ist",
    "erklaere",
    "erkläre",
    "what is",
    "how does",
    "why",
)

APP_DATA_INTENT_PHRASES = (
    "bei uns",
    "im system",
    "in der app",
    "in unserer datenbank",
    "meine",
    "mein",
    "unsere",
    "unser",
    "sichtbar",
    "vorhanden",
    "angelegt",
    "offen",
    "heute",
    "morgen",
    "anstehend",
    "dringend",
    "eilig",
    "zeige",
    "liste",
    "auflisten",
    "anzeigen",
    "gibt es",
    "erstellen",
    "anlegen",
    "loeschen",
    "löschen",
    "aendern",
    "ändern",
)


def looks_like_today_tasks_question(message):
    """Check whether a message asks for today's visible tasks."""
    text = message.lower()
    task_words = ["task", "tasks", "aufgabe", "aufgaben", "arbeit", "arbeiten", "todo"]
    today_words = ["heute", "heutige", "heutigen", "today", "anstehend"]
    return any(word in text for word in task_words) and any(word in text for word in today_words)


def extract_error_query(message):
    """Extract a likely error code or machine reference from a user message."""
    code_match = re.search(r"\b[A-Z]?\d{2,5}\b", message.upper())
    if code_match:
        return code_match.group(0)

    machine_match = re.search(r"(maschine|machine)\s+[\w-]+", message, re.IGNORECASE)
    if machine_match:
        return machine_match.group(0)
    return message


def looks_like_employee_question(message):
    """Check whether a message asks for employee or personnel data."""
    text = message.lower()
    employee_words = [
        "mitarbeiter",
        "personal",
        "personaldaten",
        "gehalt",
        "gehaltsklasse",
        "adresse",
        "geburtsdatum",
        "qualifikation",
        "schicht",
    ]
    return any(word in text for word in employee_words)


def looks_like_employee_count_question(message):
    """Check whether a message asks for the number of employees."""
    text = message.lower()
    employee_words = ["mitarbeiter", "personal", "employees"]
    return any(word in text for word in COUNT_WORDS) and any(
        word in text for word in employee_words
    )


def looks_like_natural_task_data_question(message):
    """Check whether natural wording asks for task data without saying task."""
    text = message.lower()
    return any(
        phrase in text
        for phrase in (
            "muss noch erledigt",
            "müssen noch erledigt",
            "muessen noch erledigt",
            "mussen noch erledigt",
            "noch erledigt werden",
            "noch zu erledigen",
            "steht noch aus",
            "stehen noch aus",
            "steht aus",
            "stehen aus",
            "was wurde erledigt",
            "was ist erledigt",
            "was wurde abgeschlossen",
            "was ist abgeschlossen",
            "was ist dringend",
            "was ist eilig",
        )
    )


def looks_like_problem_incident_question(message):
    """Check whether generic problem wording asks for incident data."""
    text = message.lower()
    return "gibt es" in text and any(word in text for word in ("problem", "probleme"))


def looks_like_count_question(message):
    """Check whether a message asks for a count of a visible module."""
    text = message.lower()
    return any(word in text for word in COUNT_WORDS)


def looks_like_error_question(message):
    """Check whether a message asks for error catalog or fault help."""
    text = str(message or "").lower()
    has_error_word = any(word in text for word in SCOPE_KEYWORDS["errors"])
    return _contains_error_code(message, require_context=not has_error_word) or has_error_word


def looks_like_general_knowledge_question(message):
    """Return whether a scoped keyword is used as a general knowledge question."""
    text = " ".join(str(message or "").lower().split())
    if not any(text.startswith(prefix) for prefix in GENERAL_KNOWLEDGE_PREFIXES):
        return False
    if looks_like_count_question(text) or looks_like_today_tasks_question(text):
        return False
    if _contains_error_code(message, require_context=True):
        return False
    return not any(phrase in text for phrase in APP_DATA_INTENT_PHRASES)


def detect_requested_scopes(message):
    """Return dashboard scopes explicitly referenced by a user message."""
    text = str(message or "").lower()
    scopes = {
        scope
        for scope, keywords in SCOPE_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    }
    if _contains_error_code(message, require_context=True):
        scopes.add("errors")
    if looks_like_today_tasks_question(message):
        scopes.add("tasks")
    if looks_like_natural_task_data_question(message):
        scopes.add("tasks")
    if looks_like_problem_incident_question(message):
        scopes.add("errors")
    if looks_like_employee_question(message):
        scopes.add("employees")
    return scopes


def _contains_error_code(message, require_context=False):
    """Return whether text contains an error-code-like token, excluding plain years."""
    raw_text = str(message or "")
    match = re.search(r"\b[A-Z]{0,3}\d{2,5}\b", raw_text.upper())
    if not match:
        return False
    token = match.group(0)
    if any(char.isalpha() for char in token):
        return True
    text = raw_text.lower()
    if require_context:
        return any(word in text for word in SCOPE_KEYWORDS["errors"])
    return not (1900 <= int(token) <= 2099)


def blocked_requested_scopes(user, scopes):
    """Return explicitly requested scopes the user may not view."""
    return [
        scope
        for scope in scopes
        if not has_dashboard_permission(user, scope, "view")
        or (scope == "employees" and not can_read_employee_context(user))
    ]


def format_permission_denied_for_scopes(scopes):
    """Return a combined permission answer for blocked assistant scopes."""
    labels = [DASHBOARD_SCOPE_LABELS[scope] for scope in scopes]
    if len(labels) == 1:
        return permission_denied_answer(labels[0], scopes[0])
    return (
        "## Berechtigungen\n"
        "- **Status:** Keine Berechtigung fuer die angefragten Bereiche\n"
        f"- **Betroffene Bereiche:** {', '.join(labels)}\n"
        "- **Naechster Schritt:** Bitte die Berechtigungen beim Admin anfragen"
    )


def can_read_employee_context(user):
    """Return whether the user may read employee context through the assistant."""
    return (
        has_dashboard_permission(user, "employees", "view")
        and employee_access_level(user) != "none"
    )


__all__ = [
    "looks_like_today_tasks_question",
    "extract_error_query",
    "looks_like_employee_question",
    "looks_like_employee_count_question",
    "looks_like_natural_task_data_question",
    "looks_like_problem_incident_question",
    "looks_like_count_question",
    "looks_like_error_question",
    "looks_like_general_knowledge_question",
    "detect_requested_scopes",
    "blocked_requested_scopes",
    "format_permission_denied_for_scopes",
    "can_read_employee_context",
]
