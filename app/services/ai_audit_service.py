"""AI audit and analytics services."""

import json
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import AIAuditEvent, AIFeedback


def create_ai_audit_event(
    user,
    workflow,
    diagnostics,
    requested_scopes=None,
    allowed_scopes=None,
    source_count=0,
):
    """Persist one metadata-only AI event and return its id."""
    diagnostics = diagnostics or {}
    event = AIAuditEvent(
        user_id=getattr(user, "id", None),
        workflow=workflow,
        status=str(diagnostics.get("status") or "unknown")[:80],
        provider=str(diagnostics.get("provider") or "")[:80],
        model=str(diagnostics.get("model") or "")[:120],
        model_tier=str(diagnostics.get("model_tier") or "")[:40],
        temperature=_float_value(diagnostics.get("temperature")),
        latency_ms=_int_value(diagnostics.get("latency_ms")),
        input_tokens=_int_value(diagnostics.get("input_tokens")),
        output_tokens=_int_value(diagnostics.get("output_tokens")),
        cached_tokens=_int_value(diagnostics.get("cached_tokens")),
        total_tokens=_int_value(diagnostics.get("total_tokens")),
        estimated_cost_usd=_float_value(diagnostics.get("estimated_cost_usd")),
        fallback_used=bool(diagnostics.get("fallback_used")),
        requested_scopes=_json_list(requested_scopes),
        allowed_scopes=_json_list(allowed_scopes),
        source_count=int(source_count or 0),
        error_category=str(diagnostics.get("error") or "")[:120],
    )
    db.session.add(event)
    try:
        db.session.flush()
        return event.id
    except SQLAlchemyError:
        db.session.rollback()
        raise


def ai_analytics_summary(days=7):
    """Return admin-facing AI usage and feedback analytics."""
    since = datetime.now(UTC) - timedelta(days=days)
    events = (
        AIAuditEvent.query.filter(AIAuditEvent.created_at >= since)
        .order_by(AIAuditEvent.created_at.desc())
        .all()
    )
    feedback_entries = (
        AIFeedback.query.filter(AIFeedback.created_at >= since)
        .order_by(AIFeedback.created_at.desc())
        .all()
    )
    status_counts = Counter(event.status for event in events)
    workflow_counts = Counter(event.workflow for event in events)
    error_counts = Counter(event.error_category for event in events if event.error_category)
    helpful_count = sum(1 for item in feedback_entries if item.rating == "helpful")
    not_helpful_count = sum(1 for item in feedback_entries if item.rating == "not_helpful")
    feedback_total = helpful_count + not_helpful_count
    helpful_rate = round(helpful_count / feedback_total, 2) if feedback_total else None
    input_tokens = sum(event.input_tokens for event in events)
    output_tokens = sum(event.output_tokens for event in events)
    cached_tokens = sum(event.cached_tokens for event in events)
    total_tokens = sum(event.total_tokens for event in events)
    latency_values = [event.latency_ms for event in events if event.latency_ms]
    average_latency_ms = round(sum(latency_values) / len(latency_values)) if latency_values else 0
    return {
        "window_days": days,
        "events_total": len(events),
        "fallback_count": sum(1 for event in events if event.fallback_used),
        "average_latency_ms": average_latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
        "cache_rate": round(cached_tokens / input_tokens, 2) if input_tokens else 0,
        "estimated_cost_usd": round(
            sum(event.estimated_cost_usd for event in events),
            6,
        ),
        "status_counts": dict(status_counts),
        "workflow_counts": dict(workflow_counts),
        "workflow_metrics": _workflow_metrics(events),
        "error_counts": dict(error_counts),
        "feedback": {
            "total": feedback_total,
            "helpful": helpful_count,
            "not_helpful": not_helpful_count,
            "helpful_rate": helpful_rate,
            "latest": [item.to_dict() for item in feedback_entries[:5]],
        },
        "latest_events": [event.to_dict() for event in events[:10]],
    }


def _json_list(values):
    """Serialize a list-like value for compact audit storage."""
    return json.dumps(sorted(set(values or [])), ensure_ascii=True)


def _workflow_metrics(events):
    """Return aggregate usage metrics grouped by workflow."""
    metrics = {}
    for event in events:
        item = metrics.setdefault(
            event.workflow,
            {
                "events": 0,
                "fallbacks": 0,
                "latency_ms_total": 0,
                "latency_count": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "cached_tokens": 0,
                "total_tokens": 0,
                "estimated_cost_usd": 0.0,
            },
        )
        item["events"] += 1
        item["fallbacks"] += 1 if event.fallback_used else 0
        if event.latency_ms:
            item["latency_ms_total"] += event.latency_ms
            item["latency_count"] += 1
        item["input_tokens"] += event.input_tokens
        item["output_tokens"] += event.output_tokens
        item["cached_tokens"] += event.cached_tokens
        item["total_tokens"] += event.total_tokens
        item["estimated_cost_usd"] += event.estimated_cost_usd
    for item in metrics.values():
        latency_count = item.pop("latency_count")
        latency_total = item.pop("latency_ms_total")
        item["average_latency_ms"] = round(latency_total / latency_count) if latency_count else 0
        item["estimated_cost_usd"] = round(item["estimated_cost_usd"], 6)
    return metrics


def _int_value(value):
    """Return a safe integer for audit metadata."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float_value(value):
    """Return a safe float for audit metadata."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
