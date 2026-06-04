"""AI orchestration services for permission-aware workflows."""

from __future__ import annotations

import logging

from sqlalchemy.exc import SQLAlchemyError

from app.ai.handlers.rag_handler import answer_with_rag, try_general_hybrid_answer
from app.ai.handlers.structured_handler import (
    try_domain_structured_answers,
    try_local_structured_routes,
)
from app.ai.intent import detect_requested_scopes
from app.extensions import db
from app.security import has_dashboard_permission
from app.services.ai_history_service import save_chat_exchange
from app.services.ai_retrieval import allowed_ai_scopes
from app.services.ai_service import MockAIProvider
from app.services.conversation_context_service import conversation_context_for_chat
from app.services.knowledge_service import knowledge_sources_for_chat

logger = logging.getLogger(__name__)


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

    domain_result = try_domain_structured_answers(
        message,
        user,
        conversation_context,
        requested_scopes,
        allowed_scopes,
    )
    if domain_result:
        return domain_result

    general_result = try_general_hybrid_answer(
        message,
        user,
        conversation_context,
        requested_scopes,
        allowed_scopes,
    )
    if general_result:
        return general_result

    local_result = try_local_structured_routes(
        message,
        user,
        conversation_context,
        requested_scopes,
        allowed_scopes,
    )
    if local_result:
        return local_result

    return answer_with_rag(
        message,
        user,
        conversation_context,
        requested_scopes,
        allowed_scopes,
        build_action_preview=build_action_preview,
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


def looks_like_count_question(message):
    """Proxy count-question detection for action preview helpers."""
    from app.ai.intent import looks_like_count_question as _looks_like_count_question

    return _looks_like_count_question(message)


__all__ = [
    "build_action_preview",
    "_wants_task_preview",
    "_wants_error_preview",
    "_wants_document_review",
    "answer_chat",
    "save_chat_message",
    "with_knowledge_context",
]
