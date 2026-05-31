"""Shared redacted AI provider readiness helpers."""

from app.services.ai_service import ai_api_key_configured, ai_provider_status
from app.services.embedding_service import embedding_provider_status


def ai_provider_readiness_snapshot(config, last_error=None):
    """Return a redacted provider readiness snapshot without external calls."""
    provider = str(config.get("AI_PROVIDER", "openai") or "openai").strip().lower()
    api_key_configured = ai_api_key_configured(config)
    provider_status = ai_provider_status(provider, api_key_configured, config)
    embedding_status = embedding_provider_status(config)
    readiness = ai_readiness_summary(provider_status, embedding_status, last_error)
    return {
        "provider": provider,
        "api_key_configured": api_key_configured,
        "provider_status": provider_status,
        "embedding_provider_status": embedding_status,
        "ready": readiness["ready"],
        "readiness": readiness,
    }


def ai_readiness_summary(provider_status, embedding_status, last_error=None):
    """Return redacted aggregate AI readiness details for admin payloads."""
    degraded_components = []
    reasons = []
    actions = []
    if not provider_status.get("ready"):
        degraded_components.append("provider")
        reason = str(provider_status.get("reason") or "provider_not_ready")
        reasons.append(reason)
        actions.append(_readiness_action("provider", reason, provider_status))
    if not embedding_status.get("ready"):
        degraded_components.append("embedding_provider")
        reason = str(embedding_status.get("reason") or "embedding_not_ready")
        prefixed_reason = f"embedding_{reason}"
        reasons.append(prefixed_reason)
        actions.append(_readiness_action("embedding_provider", prefixed_reason, embedding_status))
    if last_error is not None:
        degraded_components.append("last_error")
        reason = str(last_error)
        reasons.append(reason)
        actions.append(
            {
                "component": "last_error",
                "reason": reason,
                "configuration_action": "review_last_ai_error",
                "recommended_action": "Letzten AI-Fehler im Admin-Log pruefen.",
            }
        )
    ready = not degraded_components
    return {
        "ready": ready,
        "status": "ok" if ready else "degraded",
        "degraded_components": degraded_components,
        "reasons": reasons,
        "actions": actions,
        "next_action": actions[0] if actions else None,
    }


def _readiness_action(component, reason, status):
    """Return one admin-facing readiness remediation action row."""
    return {
        "component": component,
        "reason": reason,
        "configuration_action": status.get(
            "configuration_action",
            f"review_{component}_configuration",
        ),
        "recommended_action": status.get("recommended_action", ""),
    }
