"""Langfuse tracing and audit metadata helpers for chat answers."""

from __future__ import annotations

from typing import Any

from app.ai.status import ai_diagnostics, attach_audit_metadata


def structured_diagnostic_status(result: dict[str, Any]) -> str:
    """Return the diagnostics status for a structured chat answer."""
    if result.get("type") == "permission_denied":
        return "permission_denied"
    return "local_answer"


def daily_briefing_scopes(result: dict[str, Any]) -> set[str]:
    """Return dashboard scopes represented by a daily briefing chat answer."""
    source_scopes = {
        str(source.get("module") or "")
        for source in result.get("sources") or []
        if isinstance(source, dict)
    }
    scopes = {
        scope for scope in source_scopes if scope in {"tasks", "errors", "inventory", "documents"}
    }
    section_types = {
        str(section.get("type") or "")
        for section in ((result.get("data") or {}).get("sections") or [])
        if isinstance(section, dict)
    }
    if "recurring_issues" in section_types or "incident_timeline" in section_types:
        scopes.add("errors")
    return scopes


def finalize_chat_answer(
    user,
    payload: dict[str, Any],
    requested_scopes,
    allowed_scopes,
    *,
    conversation_context=None,
    workflow: str | None = None,
    message: str | None = None,
) -> dict[str, Any]:
    """Attach diagnostics and audit metadata to a chat answer payload."""
    if "diagnostics" not in payload:
        payload["diagnostics"] = ai_diagnostics(structured_diagnostic_status(payload))
    return attach_audit_metadata(
        user,
        payload,
        requested_scopes,
        allowed_scopes,
        workflow=workflow,
        message=message,
        conversation_context=conversation_context,
    )
