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
from app.services.ai_structured_scope_answer_service import answer_structured_scope_question
from app.services.ai_task_status_answer_service import answer_task_status_question
from app.services.conversation_context_service import conversation_context_for_chat
from app.services.document_service import visible_documents_query
from app.services.empty_retrieval_response_service import build_empty_retrieval_answer
from app.services.error_service import search_errors
from app.services.incident_timeline_service import daily_briefing_timeline_section
from app.services.knowledge_service import knowledge_sources_for_chat
from app.services.langfuse_service import langfuse_trace_context
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
        with langfuse_trace_context(
            "general_chat",
            user=user,
            session_id=conversation_context.session_id,
            metadata={"source_count": len(knowledge_sources)},
            tags=["chat", "general"],
        ):
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

    structured_scope_result = answer_structured_scope_question(
        message,
        user,
        conversation_context=conversation_context,
    )
    if structured_scope_result:
        status = (
            "permission_denied"
            if structured_scope_result.get("type") == "permission_denied"
            else "local_answer"
        )
        structured_scope_result["diagnostics"] = ai_diagnostics(status)
        result_scope = structured_scope_result.get("scope")
        return attach_audit_metadata(
            user,
            structured_scope_result,
            requested_scopes or ({result_scope} if result_scope else set()),
            allowed_scopes,
            message=message,
            conversation_context=conversation_context,
        )

    task_status_result = answer_task_status_question(
        message,
        user,
        conversation_context=conversation_context,
    )
    if task_status_result:
        status = (
            "permission_denied"
            if task_status_result.get("type") == "permission_denied"
            else "local_answer"
        )
        task_status_result["diagnostics"] = ai_diagnostics(status)
        return attach_audit_metadata(
            user,
            task_status_result,
            requested_scopes or {"tasks"},
            allowed_scopes,
            message=message,
            conversation_context=conversation_context,
        )

    if looks_like_employee_count_question(message):
        answer, data = format_employee_count(user)
        status = "local_answer" if data else "permission_denied"
        sources = count_answer_sources("employees", data, user)
        return attach_audit_metadata(
            user,
            {
                "type": "employee_count" if data else "permission_denied",
                "answer": answer,
                "diagnostics": ai_diagnostics(status),
                "data": data,
                "sources": sources,
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
    if retrieval_has_evidence(retrieval) or should_generate_without_evidence():
        with langfuse_trace_context(
            "chat",
            user=user,
            session_id=conversation_context.session_id,
            metadata={"source_count": len(retrieval.get("sources") or [])},
            tags=["chat", "rag", *sorted(retrieval.get("requested_scopes") or [])],
        ):
            answer, diagnostics = openai_assistant_answer(message, retrieval["context"])
    else:
        answer = grounded_empty_retrieval_answer(message, retrieval=retrieval, user=user)
        diagnostics = ai_diagnostics("local_answer", fallback_used=True)
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
    response_type = "error_help" if looks_like_error_question(retrieval_message) else "assistant"
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
        "rag": retrieval.get("rag", {}),
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


__all__ = [
    "build_action_preview",
    "_wants_task_preview",
    "_wants_error_preview",
    "_wants_document_review",
    "answer_chat",
    "save_chat_message",
    "with_knowledge_context",
]
