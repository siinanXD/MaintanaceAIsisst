"""AI orchestration services for permission-aware workflows."""
# ruff: noqa: F401, F821

import logging
import re
from datetime import date, timedelta

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.inventory.services import forecast_inventory_risks
from app.models import (
    Employee,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    Machine,
    ShiftPlan,
    Task,
    TaskStatus,
    User,
)
from app.security import employee_access_level, has_dashboard_permission
from app.services.ai_audit_service import ai_analytics_summary, create_ai_audit_event
from app.services.ai_confidence_service import attach_confidence_to_result
from app.services.ai_history_service import save_chat_exchange
from app.services.ai_prompting import (
    permission_denied_answer,
    permission_denied_context,
)
from app.services.ai_retrieval import allowed_ai_scopes, retrieve_ai_context
from app.services.ai_routing import local_metadata, workflow_profile
from app.services.ai_safety_service import (
    apply_post_generation_safety_to_result,
    apply_safety_payload_warning,
    apply_safety_warning,
    assess_ai_safety,
    enforce_post_generation_safety,
)
from app.services.ai_service import AIServiceError, MockAIProvider, get_ai_provider
from app.services.conversation_context_service import conversation_context_for_chat
from app.services.document_service import visible_documents_query
from app.services.empty_retrieval_response_service import build_empty_retrieval_answer
from app.services.error_service import search_errors
from app.services.incident_timeline_service import daily_briefing_timeline_section
from app.services.knowledge_service import knowledge_sources_for_chat
from app.services.order_planning_service import (
    REQUIRED_SCOPES as REQUIRED_ORDER_PLANNING_SCOPES,
)
from app.services.order_planning_service import (
    format_order_plan_answer,
    order_planning_payload_from_message,
    plan_order,
)
from app.services.query_understanding_service import classify_query
from app.services.rag_service import build_rag_context
from app.services.recurring_issue_service import analyze_recurring_issues
from app.services.retrieval_debug_service import (
    is_retrieval_debug_visible,
    public_retrieval_debug,
)
from app.services.retrieval_explainability_service import retrieval_explainability_summary
from app.services.retrieval_service import knowledge_context_for_chat
from app.services.task_service import visible_tasks_query

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
    "tasks": ["task", "tasks", "aufgabe", "aufgaben", "todo"],
    "errors": [
        "fehler",
        "stoerung",
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
    "machines": ["maschine", "maschinen", "anlage", "anlagen", "machine"],
    "inventory": ["lager", "bestand", "material", "ersatzteil", "inventory"],
    "documents": ["dokument", "dokumente", "bericht", "berichte", "report"],
    "shiftplans": ["schichtplan", "schichtplanung", "dienstplan", "schicht"],
    "admin_users": ["user", "users", "nutzer", "benutzer", "accounts"],
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
    task_words = ["task", "tasks", "aufgabe", "aufgaben"]
    today_words = ["heute", "today", "anstehend"]
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


def looks_like_count_question(message):
    """Check whether a message asks for a count of a visible module."""
    text = message.lower()
    return any(word in text for word in COUNT_WORDS)


def looks_like_error_question(message):
    """Check whether a message asks for error catalog or fault help."""
    text = message.lower()
    return bool(re.search(r"\b[A-Z]{0,3}\d{2,5}\b", message.upper())) or any(
        word in text for word in SCOPE_KEYWORDS["errors"]
    )


def looks_like_general_knowledge_question(message):
    """Return whether a scoped keyword is used as a general knowledge question."""
    text = " ".join(str(message or "").lower().split())
    if not any(text.startswith(prefix) for prefix in GENERAL_KNOWLEDGE_PREFIXES):
        return False
    if looks_like_count_question(text) or looks_like_today_tasks_question(text):
        return False
    if re.search(r"\b[A-Z]{0,3}\d{2,5}\b", str(message or "").upper()):
        return False
    return not any(phrase in text for phrase in APP_DATA_INTENT_PHRASES)


def detect_requested_scopes(message):
    """Return dashboard scopes explicitly referenced by a user message."""
    text = message.lower()
    scopes = {
        scope
        for scope, keywords in SCOPE_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    }
    if re.search(r"\b[A-Z]{0,3}\d{2,5}\b", message.upper()):
        scopes.add("errors")
    if looks_like_today_tasks_question(message):
        scopes.add("tasks")
    if looks_like_employee_question(message):
        scopes.add("employees")
    return scopes


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
    "looks_like_count_question",
    "looks_like_error_question",
    "looks_like_general_knowledge_question",
    "detect_requested_scopes",
    "blocked_requested_scopes",
    "format_permission_denied_for_scopes",
    "can_read_employee_context",
]
