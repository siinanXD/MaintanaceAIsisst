"""AI orchestration services for permission-aware workflows."""

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
from app.services.ai_service import AIServiceError, MockAIProvider, get_ai_provider
from app.services.conversation_context_service import conversation_context_for_chat
from app.services.document_service import visible_documents_query
from app.services.error_service import search_errors
from app.services.knowledge_service import knowledge_sources_for_chat
from app.services.order_planning_service import (
    REQUIRED_SCOPES as REQUIRED_ORDER_PLANNING_SCOPES,
)
from app.services.order_planning_service import (
    format_order_plan_answer,
    order_planning_payload_from_message,
    plan_order,
)
from app.services.rag_service import build_rag_context
from app.services.recurring_issue_service import analyze_recurring_issues
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
    return bool(re.search(r"\b[A-Z]?\d{2,5}\b", message.upper())) or any(
        word in text for word in SCOPE_KEYWORDS["errors"]
    )


def looks_like_general_knowledge_question(message):
    """Return whether a scoped keyword is used as a general knowledge question."""
    text = " ".join(str(message or "").lower().split())
    if not any(text.startswith(prefix) for prefix in GENERAL_KNOWLEDGE_PREFIXES):
        return False
    if looks_like_count_question(text) or looks_like_today_tasks_question(text):
        return False
    if re.search(r"\b[A-Z]?\d{2,5}\b", str(message or "").upper()):
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
    if re.search(r"\b[A-Z]?\d{2,5}\b", message.upper()):
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


def format_tasks_today(user):
    """Return a formatted answer and structured data for today's visible tasks."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return permission_denied_answer("Tasks"), []

    tasks = (
        visible_tasks_query(user)
        .filter(Task.due_date == date.today())
        .order_by(Task.priority.asc(), Task.id.desc())
        .all()
    )
    if not tasks:
        return (
            "## Heutige Tasks\n"
            "- **Status:** Keine Tasks fuer heute\n"
            "- **Bereich:** Keine offenen Eintraege sichtbar"
        ), []

    lines = ["## Heutige Tasks"]
    for task in tasks:
        lines.append(
            f"- **{task.title}:** {task.priority.value}, {task.status.value}, "
            f"{task.department.name}"
        )
    return "\n".join(lines), [task.to_dict() for task in tasks]


def build_error_context(entries):
    """Build a text context block from matching error catalog entries."""
    if not entries:
        return ""
    blocks = []
    for entry in entries:
        blocks.append(
            "\n".join(
                [
                    f"Maschine: {entry.machine}",
                    f"Fehlercode: {entry.error_code}",
                    f"Titel: {entry.title}",
                    f"Beschreibung: {entry.description}",
                    f"Mögliche Ursachen: {entry.possible_causes}",
                    f"Lösung: {entry.solution}",
                    f"Bereich: {entry.department.name}",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_task_context(user):
    """Build a text context block from the user's visible tasks."""
    if not has_dashboard_permission(user, "tasks", "view"):
        return permission_denied_context("Tasks", "tasks")

    tasks = visible_tasks_query(user).order_by(Task.due_date.asc(), Task.id.desc()).limit(20).all()
    if not tasks:
        return "Keine sichtbaren Tasks vorhanden."
    lines = []
    for task in tasks:
        lines.append(
            " | ".join(
                [
                    f"Titel: {task.title}",
                    f"Status: {task.status.value}",
                    f"Prioritaet: {task.priority.value}",
                    f"Faellig: {task.due_date.isoformat()}",
                    f"Bereich: {task.department.name}",
                    f"Beschreibung: {task.description}",
                ]
            )
        )
    return "\n".join(lines)


def build_catalog_context(user, preferred_entries):
    """Build a combined error catalog context for the AI assistant."""
    if not has_dashboard_permission(user, "errors", "view"):
        return permission_denied_context("Fehlerkatalog", "errors")

    entries = list(preferred_entries)
    seen = {entry.id for entry in entries}
    query = ErrorEntry.query
    if not user.is_admin:
        query = query.filter(ErrorEntry.department_id == user.department_id)
    for entry in query.order_by(ErrorEntry.created_at.desc()).limit(20).all():
        if entry.id not in seen:
            entries.append(entry)
            seen.add(entry.id)
    return build_error_context(entries) or "Keine sichtbaren Fehlerkatalogeintraege vorhanden."


def build_employee_context(user):
    """Build a filtered employee context for the AI assistant."""
    if not can_read_employee_context(user):
        return permission_denied_context("Mitarbeiter", "employees"), []

    access_level = employee_access_level(user)
    employees = Employee.query.order_by(Employee.name.asc()).limit(30).all()
    if not employees:
        return "Keine sichtbaren Mitarbeiterdaten vorhanden.", []

    lines = []
    for employee in employees:
        data = employee.to_dict(access_level)
        parts = [
            f"Personalnummer: {data.get('personnel_number')}",
            f"Name: {data.get('name')}",
            f"Abteilung: {data.get('department')}",
            f"Team: {data.get('team')}",
        ]
        if access_level in ("shift", "confidential"):
            parts.extend(
                [
                    f"Schichtmodell: {data.get('shift_model')}",
                    f"Aktuelle Schicht: {data.get('current_shift')}",
                    f"Qualifikationen: {data.get('qualifications')}",
                    f"Favoritenmaschine: {data.get('favorite_machine')}",
                ]
            )
        if access_level == "confidential":
            parts.extend(
                [
                    f"Geburtsdatum: {data.get('birth_date')}",
                    f"Wohnort: {data.get('postal_code')} {data.get('city')}",
                    f"Strasse: {data.get('street')}",
                    f"Gehaltsklasse: {data.get('salary_group')}",
                ]
            )
        lines.append(" | ".join(parts))
    return "\n".join(lines), [employee.to_dict(access_level) for employee in employees]


def build_machine_context(user):
    """Build a compact machine context for the AI assistant."""
    if not has_dashboard_permission(user, "machines", "view"):
        return permission_denied_context("Maschinen", "machines"), []

    machines = Machine.query.order_by(Machine.name.asc()).limit(30).all()
    if not machines:
        return "Keine sichtbaren Maschinen vorhanden.", []

    lines = []
    for machine in machines:
        lines.append(
            " | ".join(
                [
                    f"Maschine: {machine.name}",
                    f"Produkt: {machine.produced_item}",
                    f"Personalbedarf: {machine.required_employees}",
                ]
            )
        )
    return "\n".join(lines), [machine.to_dict() for machine in machines]


def build_inventory_context(user):
    """Build a compact inventory context for the AI assistant."""
    if not has_dashboard_permission(user, "inventory", "view"):
        return permission_denied_context("Lager", "inventory"), []

    materials = (
        InventoryMaterial.query.order_by(
            InventoryMaterial.quantity.asc(),
            InventoryMaterial.name.asc(),
        )
        .limit(30)
        .all()
    )
    if not materials:
        return "Keine sichtbaren Lagerdaten vorhanden.", []

    lines = []
    for material in materials:
        machine_name = material.machine.name if material.machine else "nicht zugeordnet"
        lines.append(
            " | ".join(
                [
                    f"Material: {material.name}",
                    f"Bestand: {material.quantity}",
                    f"Maschine: {machine_name}",
                    f"Hersteller: {material.manufacturer}",
                ]
            )
        )
    return "\n".join(lines), [material.to_dict() for material in materials]


def build_document_context(user):
    """Build a compact generated-document context for the AI assistant."""
    if not has_dashboard_permission(user, "documents", "view"):
        return permission_denied_context("Dokumente", "documents"), []

    documents = (
        visible_documents_query(user).order_by(GeneratedDocument.created_at.desc()).limit(20).all()
    )
    if not documents:
        return "Keine sichtbaren Dokumente vorhanden.", []

    lines = []
    for document in documents:
        lines.append(
            " | ".join(
                [
                    f"Titel: {document.title}",
                    f"Typ: {document.document_type}",
                    f"Maschine: {document.machine}",
                    f"Bereich: {document.department}",
                    f"Erstellt: {document.created_at.isoformat()}",
                ]
            )
        )
    return "\n".join(lines), [document.to_dict() for document in documents]


def build_shiftplan_context(user):
    """Build a compact shift-plan context for the AI assistant."""
    if not has_dashboard_permission(user, "shiftplans", "view"):
        return permission_denied_context("Schichtplanung", "shiftplans"), []

    query = ShiftPlan.query.order_by(ShiftPlan.created_at.desc())
    if not user.is_admin:
        query = query.filter(ShiftPlan.status == "published")
    plans = query.limit(10).all()
    if not plans:
        return "Keine sichtbaren Schichtplaene vorhanden.", []

    access_level = employee_access_level(user)
    lines = []
    for plan in plans:
        lines.append(
            " | ".join(
                [
                    f"Titel: {plan.title}",
                    f"Start: {plan.start_date.isoformat()}",
                    f"Tage: {plan.days}",
                    f"Bereich: {plan.department}",
                    f"Status: {plan.status}",
                ]
            )
        )
    return "\n".join(lines), [plan.to_dict(access_level) for plan in plans]


def format_employee_count(user):
    """Return a local answer for employee count questions."""
    if not can_read_employee_context(user):
        return permission_denied_answer("Mitarbeiter"), []

    count = Employee.query.count()
    answer = "## Mitarbeiter\n" f"- **Gesamt:** {count}\n" "- **Quelle:** Mitarbeiterdatenbank"
    return answer, {"count": count}


def format_module_count(user, scope):
    """Return a local count answer for one permission-aware module."""
    if scope == "employees":
        return format_employee_count(user)
    if scope == "admin_users":
        if not has_dashboard_permission(user, "admin_users", "view"):
            return permission_denied_answer("Admin Users", "admin_users"), []
        count = User.query.count()
        return ("## Admin Users\n" f"- **Gesamt:** {count}\n" "- **Quelle:** Nutzerverwaltung"), {
            "count": count
        }
    if not has_dashboard_permission(user, scope, "view"):
        return permission_denied_answer(DASHBOARD_SCOPE_LABELS[scope], scope), []

    count_query_map = {
        "tasks": visible_tasks_query(user),
        "errors": ErrorEntry.query
        if user.is_admin
        else ErrorEntry.query.filter(
            ErrorEntry.department_id == user.department_id,
        ),
        "machines": Machine.query,
        "inventory": InventoryMaterial.query,
        "documents": visible_documents_query(user),
        "shiftplans": ShiftPlan.query
        if user.is_admin
        else ShiftPlan.query.filter(
            ShiftPlan.status == "published",
        ),
    }
    query = count_query_map.get(scope)
    if query is None:
        return None, None
    count = query.count()
    label = DASHBOARD_SCOPE_LABELS[scope]
    answer = f"## {label}\n" f"- **Gesamt:** {count}\n" f"- **Quelle:** {label}"
    return answer, {"count": count}


def answer_count_question(message, user, requested_scopes, allowed_scopes):
    """Return a local answer for explicit count questions."""
    if not looks_like_count_question(message):
        return None
    count_scopes = [
        scope
        for scope in (
            "admin_users",
            "employees",
            "tasks",
            "errors",
            "machines",
            "inventory",
            "documents",
            "shiftplans",
        )
        if scope in requested_scopes
    ]
    if not count_scopes:
        return None
    scope = count_scopes[0]
    answer, data = format_module_count(user, scope)
    if answer is None:
        return None
    status = "local_answer" if data else "permission_denied"
    return attach_audit_metadata(
        user,
        {
            "type": f"{scope}_count" if data else "permission_denied",
            "answer": answer,
            "diagnostics": ai_diagnostics(status),
            "data": data or [],
            "sources": [],
        },
        requested_scopes or {scope},
        allowed_scopes,
        message=message,
    )


def should_use_general_hybrid_mode(message, requested_scopes):
    """Return whether the message should be answered as a general AI question."""
    if looks_like_general_knowledge_question(message):
        return True
    if requested_scopes:
        return False
    if looks_like_count_question(message):
        return False
    if looks_like_error_question(message):
        return False
    if looks_like_today_tasks_question(message):
        return False
    if looks_like_employee_question(message):
        return False
    return True


def fallback_error_answer(entries):
    """Return a local fallback answer when no OpenAI response is available."""
    if not entries:
        return (
            "## Fehlerhilfe\n"
            "- **Status:** Kein passender Eintrag gefunden\n"
            "- **Naechster Schritt:** Fehler im Katalog dokumentieren"
        )

    entry = entries[0]
    return (
        "## Fehlerhilfe\n"
        f"- **Code:** {entry.error_code} an {entry.machine}\n"
        f"- **Titel:** {entry.title}\n"
        f"- **Ursache:** {entry.possible_causes or 'keine Ursachen hinterlegt'}\n"
        f"- **Pruefung:** {entry.solution or 'keine Loesung hinterlegt'}"
    )


def ai_diagnostics(
    status,
    fallback_used=False,
    error=None,
    provider=None,
    metadata=None,
):
    """Build a safe diagnostic payload without exposing secrets."""
    metadata = metadata or {}
    if not metadata and status in {"local_answer", "permission_denied"}:
        metadata = local_metadata("local", status)
    default_profile = workflow_profile("chat")
    payload = {
        "status": status,
        "fallback_used": fallback_used,
        "provider": provider or metadata.get("provider") or OPENAI_PROVIDER,
        "model": metadata.get("model") or default_profile.model,
    }
    for key in (
        "workflow",
        "model_tier",
        "temperature",
        "max_tokens",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "cached_tokens",
        "total_tokens",
        "estimated_cost_usd",
    ):
        if key in metadata:
            payload[key] = metadata[key]
    if error:
        payload["error"] = error
    return payload


def attach_audit_metadata(
    user,
    result,
    requested_scopes=None,
    allowed_scopes=None,
    workflow=None,
    message="",
    conversation_context=None,
):
    """Attach source diagnostics and metadata-only audit id to a chat result."""
    diagnostics = result.setdefault("diagnostics", ai_diagnostics("local_answer"))
    if conversation_context is not None:
        diagnostics["conversation_context"] = conversation_context.diagnostics()
        diagnostics["session_id"] = conversation_context.session_id
    result = attach_confidence_to_result(message, result)
    diagnostics = result.setdefault("diagnostics", ai_diagnostics("local_answer"))
    sources = result.get("sources") or []
    diagnostics["source_count"] = len(sources)
    diagnostics["scopes"] = sorted(requested_scopes or [])
    diagnostics["retrieval_explainability"] = retrieval_explainability_summary(sources)
    event_id = create_ai_audit_event(
        user,
        workflow or result.get("type", "assistant"),
        diagnostics,
        requested_scopes=requested_scopes or [],
        allowed_scopes=allowed_scopes or [],
        source_count=len(sources),
    )
    diagnostics["audit_event_id"] = event_id
    return result


def redacted_status_error(error):
    """Return an admin-safe AI status error label without secret-related wording."""
    if not error:
        return None
    if error == "api_key_missing":
        return "configuration_missing"
    return str(error)


def ai_status():
    """Return redacted OpenAI configuration status for admins."""
    api_key_configured = bool(current_app.config.get("OPENAI_API_KEY"))
    provider = current_app.config.get("AI_PROVIDER", "openai")
    last_error = redacted_status_error(LAST_OPENAI_ERROR)
    return {
        "api_key_configured": api_key_configured,
        "model": workflow_profile("chat").model,
        "model_profiles": {
            "fast": workflow_profile("task_suggestion").to_dict(),
            "balanced": workflow_profile("chat").to_dict(),
            "quality": workflow_profile("quality_analysis").to_dict(),
        },
        "provider": provider,
        "streaming_enabled": bool(current_app.config.get("AI_ENABLE_STREAMING", True)),
        "ready": api_key_configured and last_error is None,
        "last_error": last_error,
        "analytics": ai_analytics_summary(7),
    }


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


def redacted_openai_error(error):
    """Return a user-safe error category for OpenAI failures."""
    if isinstance(error, AIServiceError):
        return error.error_code
    name = error.__class__.__name__
    return name if name.endswith("Error") else "OpenAIError"


def openai_assistant_answer(message, context):
    """Generate an AI answer using OpenAI and permission-aware context."""
    global LAST_OPENAI_ERROR
    provider = get_ai_provider()

    configured_provider = current_app.config.get("AI_PROVIDER", "openai").lower()
    if provider.name == "mock" and configured_provider != "mock":
        LAST_OPENAI_ERROR = "api_key_missing"
        logger.warning("ai_fallback workflow=chat reason=api_key_missing")
        return None, ai_diagnostics(
            "api_key_missing",
            fallback_used=True,
            error="OPENAI_API_KEY is not configured in .env",
            metadata=local_metadata("local", "chat"),
        )

    try:
        answer = provider.answer_question(message, context)
    except AIServiceError as exc:
        LAST_OPENAI_ERROR = redacted_openai_error(exc)
        logger.exception("ai_call_failed workflow=chat provider=%s", provider.name)
        return None, ai_diagnostics(
            "openai_error",
            fallback_used=True,
            error=LAST_OPENAI_ERROR,
            provider=provider.name,
            metadata=getattr(provider, "last_call_metadata", {}),
        )

    LAST_OPENAI_ERROR = None
    metadata = getattr(provider, "last_call_metadata", {})
    if provider.name == "mock":
        return answer, ai_diagnostics(
            "local_answer",
            provider=provider.name,
            metadata=metadata,
        )
    return answer, ai_diagnostics(
        "openai_used",
        provider=provider.name,
        metadata=metadata,
    )


def general_tracking_notice():
    """Return the required tracking notice for hybrid-mode answers."""
    return (
        "\n\n- **Hinweis:** Allgemeine AI-Fragen werden in der Chat-Historie "
        "und als AI-Nutzungsmetadaten protokolliert."
    )


def with_general_tracking_notice(answer):
    """Return an answer with exactly one general-chat tracking notice."""
    text = str(answer or "").strip()
    notice = general_tracking_notice().strip()
    if notice in text:
        return text
    return f"{text}\n\n{notice}" if text else notice


def local_general_chat_answer(reason):
    """Return a concise local fallback for general questions."""
    if reason == "api_key_missing":
        return (
            "## Allgemeine Antwort\n"
            "- **Status:** OpenAI ist nicht konfiguriert\n"
            "- **Naechster Schritt:** OPENAI_API_KEY in der .env setzen und Server neu starten"
        )
    if reason in {"model_not_found", "model_not_allowed"}:
        return (
            "## Allgemeine Antwort\n"
            "- **Status:** Das konfigurierte OpenAI-Modell ist nicht freigeschaltet\n"
            "- **Naechster Schritt:** OPENAI_MODEL auf ein verfuegbares Modell setzen"
        )
    if reason == "rate_limit":
        return (
            "## Allgemeine Antwort\n"
            "- **Status:** OpenAI-Rate-Limit erreicht\n"
            "- **Naechster Schritt:** Kurz warten oder ein Modell mit hoeherem Limit nutzen"
        )
    if reason == "authentication_error":
        return (
            "## Allgemeine Antwort\n"
            "- **Status:** OpenAI-Key wurde abgelehnt\n"
            "- **Naechster Schritt:** OPENAI_API_KEY pruefen oder neu erstellen"
        )
    if reason in {"connection_error", "timeout"}:
        return (
            "## Allgemeine Antwort\n"
            "- **Status:** Verbindung zu OpenAI nicht erfolgreich\n"
            "- **Naechster Schritt:** Netzwerk, Firewall und Timeout-Konfiguration pruefen"
        )
    return (
        "## Allgemeine Antwort\n"
        "- **Status:** OpenAI ist gerade nicht erreichbar\n"
        "- **Naechster Schritt:** API-Key, Modellname, Netzwerk und OpenAI-Status pruefen"
    )


def openai_general_answer(message, context=""):
    """Generate a short general AI answer for hybrid mode."""
    global LAST_OPENAI_ERROR
    provider = get_ai_provider()
    configured_provider = current_app.config.get("AI_PROVIDER", "openai").lower()
    if provider.name == "mock" and configured_provider != "mock":
        LAST_OPENAI_ERROR = "api_key_missing"
        answer = local_general_chat_answer("api_key_missing")
        return with_general_tracking_notice(answer), ai_diagnostics(
            "api_key_missing",
            fallback_used=True,
            error="OPENAI_API_KEY is not configured in .env",
            metadata=local_metadata("local", "general_chat"),
        )

    try:
        if context:
            answer = provider.answer_question(message, context, workflow="general_chat")
        else:
            answer = provider.answer_general_question(message)
    except AIServiceError as exc:
        LAST_OPENAI_ERROR = redacted_openai_error(exc)
        logger.exception(
            "ai_call_failed workflow=general_chat provider=%s",
            provider.name,
        )
        fallback = local_general_chat_answer(LAST_OPENAI_ERROR)
        return with_general_tracking_notice(fallback), ai_diagnostics(
            "openai_error",
            fallback_used=True,
            error=LAST_OPENAI_ERROR,
            provider=provider.name,
            metadata=getattr(provider, "last_call_metadata", {}),
        )

    LAST_OPENAI_ERROR = None
    metadata = getattr(provider, "last_call_metadata", {})
    status = "local_answer" if provider.name == "mock" else "openai_used"
    return with_general_tracking_notice(answer), ai_diagnostics(
        status,
        provider=provider.name,
        metadata=metadata,
    )


def fallback_general_answer(context_data, blocked_scopes=None):
    """Return a local read-only answer from allowed context counts."""
    blocked_scopes = blocked_scopes or []
    counts = {
        "Fehler": len(context_data.get("errors", [])),
        "Mitarbeiter": len(context_data.get("employees", [])),
        "Maschinen": len(context_data.get("machines", [])),
        "Lagerpositionen": len(context_data.get("inventory", [])),
        "Dokumente": len(context_data.get("documents", [])),
        "Schichtplaene": len(context_data.get("shiftplans", [])),
    }
    visible = [f"{label}: {count}" for label, count in counts.items() if count]
    lines = [
        "## Ergebnis",
        "- **Status:** Freigegebene Daten geprueft",
    ]
    if visible:
        lines.append(f"- **Sichtbarer Kontext:** {', '.join(visible[:4])}")
    else:
        lines.append("- **Sichtbarer Kontext:** Keine passenden Daten gefunden")
    if blocked_scopes:
        labels = [DASHBOARD_SCOPE_LABELS[scope] for scope in blocked_scopes]
        blocked_labels = ", ".join(labels)
        lines.append(f"- **Eingeschraenkt:** Keine Berechtigung fuer {blocked_labels}")
        lines.append("- **Naechster Schritt:** Berechtigung beim Admin anfragen")
    else:
        lines.append("- **Naechster Schritt:** Frage bei Bedarf konkreter stellen")
    return "\n".join(lines)


def build_action_preview(message, user, sources):
    """Return a read-only action preview that can fill existing forms."""
    text = message.lower()
    if looks_like_count_question(message):
        return None
    if has_dashboard_permission(user, "tasks", "write") and _wants_task_preview(text):
        suggestion = MockAIProvider().suggest_task(
            message,
            {
                "role": user.role.value,
                "department": user.department.name if user.department else "",
            },
        )
        return {
            "type": "task_draft",
            "label": "Task-Entwurf uebernehmen",
            "target": "tasks",
            "url": "/tasks",
            "payload": suggestion,
        }
    if has_dashboard_permission(user, "errors", "write") and _wants_error_preview(text):
        analysis = MockAIProvider().analyze_error(
            message,
            {
                "role": user.role.value,
                "department": user.department.name if user.department else "",
            },
        )
        return {
            "type": "error_draft",
            "label": "Fehleranalyse uebernehmen",
            "target": "errors",
            "url": "/errors",
            "payload": analysis,
        }
    document_source = next((source for source in sources if source["type"] == "document"), None)
    if document_source and _wants_document_review(text):
        return {
            "type": "document_review",
            "label": "Dokumentpruefung oeffnen",
            "target": "documents",
            "url": "/documents",
            "payload": {"document_id": document_source["id"]},
        }
    machine_source = next((source for source in sources if source["type"] == "machine"), None)
    if machine_source and has_dashboard_permission(user, "machines", "view"):
        return {
            "type": "machine_assistant",
            "label": "Maschinenassistent oeffnen",
            "target": "machines",
            "url": "/machines",
            "payload": {
                "machine_id": machine_source["id"],
                "question": message,
            },
        }
    return None


def _wants_task_preview(text):
    """Return whether the message asks for a task draft."""
    return any(
        phrase in text
        for phrase in (
            "task erstellen",
            "task anlegen",
            "aufgabe erstellen",
            "aufgabe anlegen",
            "task vorschlag",
        )
    )


def _wants_error_preview(text):
    """Return whether the message asks for an error draft."""
    return any(
        phrase in text
        for phrase in (
            "fehler anlegen",
            "fehleranalyse",
            "fehler dokumentieren",
            "stoerung dokumentieren",
            "störung dokumentieren",
        )
    )


def _wants_document_review(text):
    """Return whether the message asks to review a document."""
    return "dokument" in text and any(
        word in text for word in ("pruefen", "prüfen", "review", "check")
    )


def answer_chat(message, user, session_id=""):
    """Route the user message to the correct assistant behavior."""
    conversation_context = conversation_context_for_chat(user, message, session_id)
    requested_scopes = detect_requested_scopes(message)
    if conversation_context.applied:
        requested_scopes |= set(conversation_context.suggested_scopes)
    allowed_scopes = allowed_ai_scopes(user)
    if should_use_general_hybrid_mode(message, requested_scopes):
        knowledge_context, knowledge_sources = knowledge_context_for_chat(
            message,
            user,
            conversation_context=conversation_context,
        )
        answer, diagnostics = openai_general_answer(message, knowledge_context)
        return attach_audit_metadata(
            user,
            {
                "type": "general_chat",
                "answer": answer,
                "diagnostics": diagnostics,
                "data": {},
                "sources": knowledge_sources,
            },
            requested_scopes,
            allowed_scopes,
            workflow="general_chat",
            message=message,
            conversation_context=conversation_context,
        )

    blocked_scopes = blocked_requested_scopes(user, requested_scopes)
    if blocked_scopes and len(blocked_scopes) == len(requested_scopes):
        answer = format_permission_denied_for_scopes(blocked_scopes)
        return attach_audit_metadata(
            user,
            {
                "type": "permission_denied",
                "answer": answer,
                "diagnostics": ai_diagnostics("permission_denied"),
                "data": [],
                "sources": [],
            },
            requested_scopes,
            allowed_scopes,
            message=message,
        )

    if looks_like_today_tasks_question(message):
        if not has_dashboard_permission(user, "tasks", "view"):
            answer = permission_denied_answer("Tasks", "tasks")
            return attach_audit_metadata(
                user,
                {
                    "type": "permission_denied",
                    "answer": answer,
                    "diagnostics": ai_diagnostics("permission_denied"),
                    "data": [],
                    "sources": [],
                },
                requested_scopes,
                allowed_scopes,
                message=message,
            )
        answer, data = format_tasks_today(user)
        retrieval = retrieve_ai_context(message, user, {"tasks"})
        return attach_audit_metadata(
            user,
            {
                "type": "tasks_today",
                "answer": answer,
                "diagnostics": ai_diagnostics("local_answer"),
                "data": data,
                "sources": retrieval["sources"],
            },
            requested_scopes or {"tasks"},
            allowed_scopes,
            message=message,
        )

    if looks_like_employee_count_question(message):
        answer, data = format_employee_count(user)
        status = "local_answer" if data else "permission_denied"
        return attach_audit_metadata(
            user,
            {
                "type": "employee_count" if data else "permission_denied",
                "answer": answer,
                "diagnostics": ai_diagnostics(status),
                "data": data,
                "sources": [],
            },
            requested_scopes or {"employees"},
            allowed_scopes,
            message=message,
        )

    count_result = answer_count_question(
        message,
        user,
        requested_scopes,
        allowed_scopes,
    )
    if count_result:
        return count_result

    order_payload = order_planning_payload_from_message(message)
    if order_payload:
        plan, error, status_code = plan_order(order_payload, user)
        if error:
            answer = error.get("message") or error.get("error") or "Auftrag nicht planbar."
            diagnostic_status = "permission_denied" if status_code == 403 else "local_answer"
            return attach_audit_metadata(
                user,
                {
                    "type": "permission_denied" if status_code == 403 else "order_plan",
                    "answer": answer,
                    "diagnostics": ai_diagnostics(diagnostic_status),
                    "data": error,
                    "sources": [],
                },
                requested_scopes or REQUIRED_ORDER_PLANNING_SCOPES,
                allowed_scopes,
                message=message,
            )
        return attach_audit_metadata(
            user,
            {
                "type": "order_plan",
                "answer": format_order_plan_answer(plan),
                "diagnostics": plan["diagnostics"],
                "data": plan,
                "sources": plan["sources"],
            },
            requested_scopes or REQUIRED_ORDER_PLANNING_SCOPES,
            allowed_scopes,
            message=message,
        )

    retrieval = build_rag_context(
        message,
        user,
        requested_scopes,
        conversation_context=conversation_context,
    )
    answer, diagnostics = openai_assistant_answer(message, retrieval["context"])
    if not answer:
        logger.warning("ai_fallback workflow=chat type=assistant")
        retrieval_message = conversation_context.retrieval_query(message)
        if looks_like_error_question(message) and has_dashboard_permission(
            user,
            "errors",
            "view",
        ):
            entries = search_errors(extract_error_query(retrieval_message), user)
            answer = fallback_error_answer(entries)
        else:
            answer = fallback_general_answer(retrieval["data"], blocked_scopes)
        diagnostics = diagnostics or ai_diagnostics("fallback_used", fallback_used=True)
    retrieval_message = conversation_context.retrieval_query(message)
    response_type = (
        "error_help"
        if looks_like_error_question(retrieval_message)
        else "assistant"
    )
    response_data = (
        retrieval["data"].get("errors", []) if response_type == "error_help" else retrieval["data"]
    )
    action_preview = build_action_preview(message, user, retrieval["sources"])
    result = {
        "type": response_type,
        "answer": answer,
        "diagnostics": diagnostics,
        "data": response_data,
        "sources": retrieval["sources"],
    }
    if action_preview:
        result["action_preview"] = action_preview
    return attach_audit_metadata(
        user,
        result,
        retrieval["requested_scopes"],
        retrieval["allowed_scopes"],
        message=message,
        conversation_context=conversation_context,
    )


def save_chat_message(user, message, response, session_id=""):
    """Persist a chat message and its assistant response in the database."""
    result = response if isinstance(response, dict) else {"answer": response}
    chat = save_chat_exchange(user, message, result, session_id=session_id)
    db.session.add(chat)

    try:
        db.session.commit()
        return chat
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("ai_chat_save_failed user_id=%s", user.id)
        return None


def with_knowledge_context(retrieval, message, user):
    """Append local knowledge chunks to an AI retrieval payload."""
    knowledge_context, knowledge_sources = knowledge_sources_for_chat(message, user)
    if not knowledge_sources:
        return retrieval
    if retrieval.get("context"):
        retrieval["context"] = f"{retrieval['context']}\n\n{knowledge_context}"
    else:
        retrieval["context"] = knowledge_context
    retrieval["sources"] = (retrieval.get("sources") or []) + knowledge_sources
    retrieval["data"].setdefault("knowledge", knowledge_sources)
    return retrieval
