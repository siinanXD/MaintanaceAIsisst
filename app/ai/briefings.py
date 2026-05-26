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


def daily_briefing(user):
    """Return a local daily maintenance briefing for the current user."""
    sections = []
    if has_dashboard_permission(user, "tasks", "view"):
        sections.append(task_briefing_section(user))
    if has_dashboard_permission(user, "inventory", "view") and has_dashboard_permission(
        user, "tasks", "view"
    ):
        sections.append(inventory_briefing_section(user))
    if has_dashboard_permission(user, "errors", "view"):
        sections.append(error_briefing_section(user))
        sections.append(recurring_issue_briefing_section(user))
        sections.append(daily_briefing_timeline_section(user))
    if has_dashboard_permission(user, "documents", "view"):
        sections.append(document_briefing_section(user))
    sections.append(rag_briefing_section(user))

    visible_sections = [section for section in sections if section]
    important_count = sum(section["count"] for section in visible_sections)
    if important_count:
        summary = f"Heute gibt es {important_count} wichtige Hinweise."
    else:
        summary = "Heute sind keine kritischen Hinweise sichtbar."
    return {
        "date": date.today().isoformat(),
        "summary": summary,
        "sections": visible_sections,
        "diagnostics": {
            "status": "local_answer",
            "provider": "local_briefing",
            "rag_source_count": sum(
                section.get("rag_source_count", 0) for section in visible_sections
            ),
        },
    }


def task_briefing_section(user):
    """Return today's and overdue task briefing items."""
    today = date.today()
    tasks = (
        visible_tasks_query(user)
        .filter(Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]))
        .order_by(Task.due_date.asc(), Task.id.desc())
        .limit(20)
        .all()
    )
    items = []
    for task in tasks:
        if task.due_date > today and task.priority.value != "urgent":
            continue
        items.append(
            {
                "title": task.title,
                "severity": "critical" if task.due_date < today else "high",
                "summary": (
                    f"{task.priority.value}, {task.status.value}, "
                    f"faellig {task.due_date.isoformat()}"
                ),
                "url": f"/api/tasks/{task.id}",
            }
        )
    return {
        "type": "tasks",
        "title": "Tasks",
        "count": len(items),
        "items": items[:5],
    }


def inventory_briefing_section(user):
    """Return critical inventory forecast briefing items."""
    forecast, error, _status = forecast_inventory_risks(
        {"status": "open", "limit": 20, "low_stock_threshold": 5},
        user,
    )
    if error:
        return None
    items = [
        {
            "title": item["material"]["name"],
            "severity": item["risk_level"],
            "summary": item["recommended_action"],
            "url": "/inventory",
        }
        for item in forecast.get("items", [])
        if item["risk_level"] in {"critical", "high"}
    ]
    return {
        "type": "inventory",
        "title": "Lager",
        "count": len(items),
        "items": items[:5],
    }


def error_briefing_section(user):
    """Return recently created error catalog briefing items."""
    since = date.today() - timedelta(days=1)
    entries = (
        ErrorEntry.query
        if user.is_admin
        else ErrorEntry.query.filter(ErrorEntry.department_id == user.department_id)
    )
    entries = (
        entries.filter(ErrorEntry.created_at >= since)
        .order_by(ErrorEntry.created_at.desc())
        .limit(5)
        .all()
    )
    items = [
        {
            "title": f"{entry.error_code} - {entry.title}",
            "severity": "medium",
            "summary": entry.machine,
            "url": f"/api/errors/{entry.id}",
        }
        for entry in entries
    ]
    return {
        "type": "errors",
        "title": "Neue Fehler",
        "count": len(items),
        "items": items,
    }


def recurring_issue_briefing_section(user):
    """Return recurring error trends as briefing items."""
    trends = analyze_recurring_issues(user, days=30, min_occurrences=2, limit=3)
    items = [
        {
            "title": f"{item['affected_machine']} {item['error_code']}".strip(),
            "severity": item["risk_level"],
            "summary": item["recommendation"],
            "url": "/errors",
            "occurrence_count": item["occurrence_count"],
        }
        for item in trends.get("items", [])
    ]
    if not items:
        return None
    return {
        "type": "recurring_issues",
        "title": "Wiederkehrende Fehler",
        "count": len(items),
        "items": items,
        "diagnostics": trends.get("diagnostics", {}),
    }


def document_briefing_section(user):
    """Return recent document briefing items as review candidates."""
    documents = (
        visible_documents_query(user)
        .filter(GeneratedDocument.created_at >= date.today() - timedelta(days=7))
        .order_by(GeneratedDocument.created_at.desc())
        .limit(5)
        .all()
    )
    items = [
        {
            "title": document.title,
            "severity": "info",
            "summary": "Dokumentpruefung bei Bedarf ausfuehren",
            "url": document.to_dict()["detail_url"],
        }
        for document in documents
    ]
    return {
        "type": "documents",
        "title": "Dokumente",
        "count": len(items),
        "items": items,
    }


def rag_briefing_section(user):
    """Return visible RAG knowledge sources relevant for today's briefing."""
    department = user.department.name if user.department else ""
    query_text = " ".join(
        part
        for part in (
            "heute kritisch stoerung wartung instandhaltung maschine",
            department,
        )
        if part
    )
    _context, sources = knowledge_context_for_chat(query_text, user, limit=3)
    if not sources:
        return None
    items = [
        {
            "title": source["title"],
            "severity": "info",
            "summary": source["reason"],
            "url": source["url"],
        }
        for source in sources
    ]
    return {
        "type": "knowledge",
        "title": "AI-Wissenskontext",
        "count": len(items),
        "items": items,
        "rag_source_count": len(sources),
    }


__all__ = [
    "daily_briefing",
    "task_briefing_section",
    "inventory_briefing_section",
    "error_briefing_section",
    "recurring_issue_briefing_section",
    "document_briefing_section",
    "rag_briefing_section",
]
