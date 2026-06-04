"""Structured and local chat answer routing before RAG retrieval."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.ai.briefings import answer_daily_briefing_chat_question
from app.ai.context import (
    answer_count_question,
    count_answer_sources,
    format_employee_count,
    format_tasks_today,
)
from app.ai.handlers.tracing_handler import (
    daily_briefing_scopes,
    finalize_chat_answer,
    structured_diagnostic_status,
)
from app.ai.intent import (
    blocked_requested_scopes,
    format_permission_denied_for_scopes,
    is_multi_scope_count_question,
    looks_like_employee_count_question,
    looks_like_today_tasks_question,
)
from app.ai.status import ai_diagnostics
from app.security import has_dashboard_permission
from app.services.ai_document_structured_answer_service import (
    answer_document_structured_question,
)
from app.services.ai_employee_structured_answer_service import (
    answer_employee_structured_question,
)
from app.services.ai_inventory_structured_answer_service import (
    answer_inventory_structured_question,
)
from app.services.ai_machine_structured_answer_service import (
    answer_machine_structured_question,
)
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_retrieval import retrieve_ai_context
from app.services.ai_shiftplan_structured_answer_service import (
    answer_shiftplan_structured_question,
)
from app.services.ai_structured_scope_answer_service import answer_structured_scope_question
from app.services.ai_task_status_answer_service import answer_task_status_question
from app.services.ai_vacation_structured_answer_service import (
    answer_vacation_structured_question,
)
from app.services.order_planning_service import (
    REQUIRED_SCOPES as REQUIRED_ORDER_PLANNING_SCOPES,
)
from app.services.order_planning_service import (
    format_order_plan_answer,
    order_planning_payload_from_message,
    plan_order,
)

StructuredHandler = Callable[..., dict[str, Any] | None]
ScopeResolver = Callable[[set[str] | None], set[str] | None]


def _finalize_structured(
    user,
    result: dict[str, Any],
    requested_scopes,
    allowed_scopes,
    scope_resolver: ScopeResolver,
    *,
    conversation_context=None,
    message: str | None = None,
) -> dict[str, Any]:
    """Attach diagnostics and audit metadata for one structured handler result."""
    result["diagnostics"] = ai_diagnostics(structured_diagnostic_status(result))
    effective_scopes = scope_resolver(requested_scopes)
    return finalize_chat_answer(
        user,
        result,
        effective_scopes,
        allowed_scopes,
        conversation_context=conversation_context,
        message=message,
    )


def _run_structured_handler(
    handler: StructuredHandler,
    message: str,
    user,
    conversation_context,
    requested_scopes,
    allowed_scopes,
    scope_resolver: ScopeResolver,
) -> dict[str, Any] | None:
    """Execute one structured handler and finalize the result when matched."""
    result = handler(message, user, conversation_context=conversation_context)
    if not result:
        return None
    return _finalize_structured(
        user,
        result,
        requested_scopes,
        allowed_scopes,
        scope_resolver,
        conversation_context=conversation_context,
        message=message,
    )


def try_domain_structured_answers(
    message: str,
    user,
    conversation_context,
    requested_scopes,
    allowed_scopes,
) -> dict[str, Any] | None:
    """Try daily briefing and domain-specific structured answer handlers."""
    daily_briefing_result = answer_daily_briefing_chat_question(message, user)
    if daily_briefing_result:
        daily_briefing_result["diagnostics"] = ai_diagnostics("local_answer")
        return finalize_chat_answer(
            user,
            daily_briefing_result,
            requested_scopes or daily_briefing_scopes(daily_briefing_result),
            allowed_scopes,
            workflow="daily_briefing",
            message=message,
            conversation_context=conversation_context,
        )

    structured_handlers: list[tuple[StructuredHandler, ScopeResolver]] = [
        (
            answer_vacation_structured_question,
            lambda scopes: set(scopes or set()) | {"employees"},
        ),
        (answer_employee_structured_question, lambda scopes: scopes or {"employees"}),
        (answer_document_structured_question, lambda scopes: scopes or {"documents"}),
        (answer_shiftplan_structured_question, lambda scopes: scopes or {"shiftplans"}),
        (answer_inventory_structured_question, lambda scopes: scopes or {"inventory"}),
        (
            answer_machine_structured_question,
            lambda scopes: set(scopes or set()) | {"machines", "errors"},
        ),
    ]
    for handler, scope_resolver in structured_handlers:
        result = _run_structured_handler(
            handler,
            message,
            user,
            conversation_context,
            requested_scopes,
            allowed_scopes,
            scope_resolver,
        )
        if result:
            return result

    return None


def try_local_structured_routes(
    message: str,
    user,
    conversation_context,
    requested_scopes,
    allowed_scopes,
) -> dict[str, Any] | None:
    """Try permission blocks and remaining local structured routes before RAG."""
    blocked_scopes = blocked_requested_scopes(user, requested_scopes)
    if blocked_scopes and len(blocked_scopes) == len(requested_scopes):
        return finalize_chat_answer(
            user,
            {
                "type": "permission_denied",
                "answer": format_permission_denied_for_scopes(blocked_scopes),
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
            return finalize_chat_answer(
                user,
                {
                    "type": "permission_denied",
                    "answer": permission_denied_answer("Tasks", "tasks"),
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
        return finalize_chat_answer(
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

    for handler, default_scope in (
        (answer_structured_scope_question, None),
        (answer_task_status_question, {"tasks"}),
    ):
        result = handler(message, user, conversation_context=conversation_context)
        if not result:
            continue
        if handler is answer_structured_scope_question:
            result_scope = result.get("scope")
            effective_scopes = requested_scopes or ({result_scope} if result_scope else set())
        else:
            effective_scopes = requested_scopes or default_scope
        return _finalize_structured(
            user,
            result,
            requested_scopes,
            allowed_scopes,
            lambda _scopes, resolved=effective_scopes: resolved,
            conversation_context=conversation_context,
            message=message,
        )

    if looks_like_employee_count_question(message) and not is_multi_scope_count_question(
        message,
        requested_scopes,
    ):
        answer, data = format_employee_count(user)
        status = "local_answer" if data else "permission_denied"
        sources = count_answer_sources("employees", data, user)
        return finalize_chat_answer(
            user,
            {
                "type": "employee_count" if data else "permission_denied",
                "answer": answer,
                "diagnostics": ai_diagnostics(status),
                "data": data,
                "sources": sources,
                "structured_context": {"entity_type": "employees"},
            },
            requested_scopes or {"employees"},
            allowed_scopes,
            message=message,
            conversation_context=conversation_context,
        )

    count_result = answer_count_question(message, user, requested_scopes, allowed_scopes)
    if count_result:
        return count_result

    order_payload = order_planning_payload_from_message(message)
    if order_payload:
        plan, error, status_code = plan_order(order_payload, user)
        if error:
            answer = error.get("message") or error.get("error") or "Auftrag nicht planbar."
            diagnostic_status = "permission_denied" if status_code == 403 else "local_answer"
            return finalize_chat_answer(
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
        return finalize_chat_answer(
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

    return None
