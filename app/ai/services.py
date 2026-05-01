import logging
import re
from datetime import date, timedelta
from sqlalchemy.exc import SQLAlchemyError

from flask import current_app

from app.errors.services import search_errors
from app.inventory.services import forecast_inventory_risks
from app.extensions import db
from app.models import (
    ChatMessage,
    Employee,
    ErrorEntry,
    GeneratedDocument,
    Task,
    TaskStatus,
)
from app.security import employee_access_level, has_dashboard_permission
from app.services.document_service import visible_documents_query
from app.services.ai_service import AIServiceError, get_ai_provider
from app.tasks.services import visible_tasks_query


LAST_OPENAI_ERROR = None
OPENAI_PROVIDER = "OpenAI"
logger = logging.getLogger(__name__)


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
    count_words = ["wie viele", "wieviele", "anzahl", "count", "many"]
    employee_words = ["mitarbeiter", "personal", "employees"]
    return (
        any(word in text for word in count_words)
        and any(word in text for word in employee_words)
    )


def can_read_employee_context(user):
    """Return whether the user may read employee context through the assistant."""
    return (
        has_dashboard_permission(user, "employees", "view")
        and employee_access_level(user) != "none"
    )


def permission_denied_answer(scope):
    """Return a short structured permission message for the assistant."""
    return (
        f"## {scope}\n"
        "- **Status:** Keine Berechtigung\n"
        "- **Naechster Schritt:** Rechte beim Admin pruefen"
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
        return "Keine Berechtigung fuer Taskdaten."

    tasks = (
        visible_tasks_query(user)
        .order_by(Task.due_date.asc(), Task.id.desc())
        .limit(20)
        .all()
    )
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
        return "Keine Berechtigung fuer Fehlerkatalogdaten."

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
        return "Keine Berechtigung fuer Mitarbeiterdaten.", []

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


def format_employee_count(user):
    """Return a local answer for employee count questions."""
    if not can_read_employee_context(user):
        return permission_denied_answer("Mitarbeiter"), []

    count = Employee.query.count()
    answer = (
        "## Mitarbeiter\n"
        f"- **Gesamt:** {count}\n"
        "- **Quelle:** Mitarbeiterdatenbank"
    )
    return answer, {"count": count}


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


def ai_diagnostics(status, fallback_used=False, error=None, provider=None):
    """Build a safe diagnostic payload without exposing secrets."""
    payload = {
        "status": status,
        "fallback_used": fallback_used,
        "provider": provider or OPENAI_PROVIDER,
        "model": current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
    }
    if error:
        payload["error"] = error
    return payload


def ai_status():
    """Return redacted OpenAI configuration status for admins."""
    api_key_configured = bool(current_app.config.get("OPENAI_API_KEY"))
    provider = current_app.config.get("AI_PROVIDER", "openai")
    return {
        "api_key_configured": api_key_configured,
        "model": current_app.config.get("OPENAI_MODEL", "gpt-4o-mini"),
        "provider": provider,
        "ready": api_key_configured and LAST_OPENAI_ERROR is None,
        "last_error": LAST_OPENAI_ERROR,
    }


def daily_briefing(user):
    """Return a local daily maintenance briefing for the current user."""
    sections = []
    if has_dashboard_permission(user, "tasks", "view"):
        sections.append(task_briefing_section(user))
    if (
        has_dashboard_permission(user, "inventory", "view")
        and has_dashboard_permission(user, "tasks", "view")
    ):
        sections.append(inventory_briefing_section(user))
    if has_dashboard_permission(user, "errors", "view"):
        sections.append(error_briefing_section(user))
    if has_dashboard_permission(user, "documents", "view"):
        sections.append(document_briefing_section(user))

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
        "diagnostics": {"status": "local_answer", "provider": "local_briefing"},
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


def redacted_openai_error(error):
    """Return a user-safe error category for OpenAI failures."""
    name = error.__class__.__name__
    return name if name.endswith("Error") else "OpenAIError"


def openai_error_answer(message, error_context, task_context, employee_context):
    """Generate an AI answer using OpenAI and the provided maintenance context."""
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
        )

    context = (
        f"Fehlerkatalog:\n{error_context}\n\n"
        f"Tasks:\n{task_context}\n\n"
        f"Mitarbeiterdaten:\n{employee_context}"
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
        )

    LAST_OPENAI_ERROR = None
    if provider.name == "mock":
        return answer, ai_diagnostics("local_answer", provider=provider.name)
    return answer, ai_diagnostics("openai_used", provider=provider.name)


def answer_chat(message, user):
    """Route the user message to the correct assistant behavior."""
    if looks_like_today_tasks_question(message):
        answer, data = format_tasks_today(user)
        return {
            "type": "tasks_today",
            "answer": answer,
            "diagnostics": ai_diagnostics("local_answer"),
            "data": data,
        }

    if looks_like_employee_count_question(message):
        answer, data = format_employee_count(user)
        status = "local_answer" if data else "permission_denied"
        return {
            "type": "employee_count" if data else "permission_denied",
            "answer": answer,
            "diagnostics": ai_diagnostics(status),
            "data": data,
        }

    employee_context, employee_data = build_employee_context(user)
    if (
        looks_like_employee_question(message)
        and not employee_data
        and not can_read_employee_context(user)
    ):
        answer = permission_denied_answer("Mitarbeiter")
        return {
            "type": "permission_denied",
            "answer": answer,
            "diagnostics": ai_diagnostics("permission_denied"),
            "data": [],
        }

    entries = []
    if has_dashboard_permission(user, "errors", "view"):
        entries = search_errors(extract_error_query(message), user)
    error_context = build_catalog_context(user, entries)
    task_context = build_task_context(user)
    answer, diagnostics = openai_error_answer(
        message,
        error_context,
        task_context,
        employee_context,
    )
    if not answer:
        logger.warning("ai_fallback workflow=chat type=error_help")
        answer = fallback_error_answer(entries)
        diagnostics = diagnostics or ai_diagnostics("fallback_used", fallback_used=True)
    return {
        "type": "error_help",
        "answer": answer,
        "diagnostics": diagnostics,
        "data": [entry.to_dict() for entry in entries],
    }


def save_chat_message(user, message, response):
    """Persist a chat message and its assistant response in the database."""
    chat = ChatMessage(user_id=user.id, message=message, response=response)

    db.session.add(chat)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("ai_chat_save_failed user_id=%s", user.id)
