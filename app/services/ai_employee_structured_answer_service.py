"""Structured AI answers for employee visibility and availability questions."""

from __future__ import annotations

from typing import Any

from app.services.ai_employee_core_service import try_employee_core_structured_answer
from app.services.ai_employee_document_service import (
    try_employee_document_structured_answer,
    visible_employees_with_documents_query,
)


def answer_employee_structured_question(
    message: str,
    user: Any,
    conversation_context: Any | None = None,
) -> dict[str, Any] | None:
    """Return a structured employee answer for supported German questions."""
    document_answer = try_employee_document_structured_answer(
        message,
        user,
        conversation_context=conversation_context,
    )
    if document_answer is not None:
        return document_answer
    return try_employee_core_structured_answer(
        message,
        user,
        conversation_context=conversation_context,
    )


__all__ = [
    "answer_employee_structured_question",
    "visible_employees_with_documents_query",
]
