"""AI audit and analytics services."""

import json
from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import AIAuditEvent, AIFeedback
from app.services.retrieval_explainability_service import explainability_to_json
from app.services.retrieval_telemetry_service import retrieval_quality_analytics


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
    confidence = diagnostics.get("confidence") or {}
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
        confidence_score=_optional_int_value(
            diagnostics.get("confidence_score") or confidence.get("score"),
        ),
        confidence_level=str(
            diagnostics.get("confidence_level") or confidence.get("level") or "",
        )[:40],
        retrieval_explainability_json=explainability_to_json(
            diagnostics.get("retrieval_explainability") or {},
        ),
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
    partially_helpful_count = sum(
        1 for item in feedback_entries if item.rating == "partially_helpful"
    )
    feedback_total = helpful_count + not_helpful_count + partially_helpful_count
    helpful_rate = round(helpful_count / feedback_total, 2) if feedback_total else None
    input_tokens = sum(event.input_tokens for event in events)
    output_tokens = sum(event.output_tokens for event in events)
    cached_tokens = sum(event.cached_tokens for event in events)
    total_tokens = sum(event.total_tokens for event in events)
    latency_values = [event.latency_ms for event in events if event.latency_ms]
    average_latency_ms = round(sum(latency_values) / len(latency_values)) if latency_values else 0
    fallback_count = sum(1 for event in events if event.fallback_used)
    error_count = sum(1 for event in events if _is_error_event(event))
    estimated_cost_usd = round(sum(event.estimated_cost_usd for event in events), 6)
    workflow_metrics = _workflow_metrics(events)
    fallback_rate = _rate(fallback_count, len(events))
    error_rate = _rate(error_count, len(events))
    cache_rate = _rate(cached_tokens, input_tokens)
    return {
        "window_days": days,
        "events_total": len(events),
        "fallback_count": fallback_count,
        "fallback_rate": fallback_rate,
        "error_count": error_count,
        "error_rate": error_rate,
        "average_latency_ms": average_latency_ms,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cached_tokens": cached_tokens,
        "total_tokens": total_tokens,
        "cache_rate": cache_rate,
        "estimated_cost_usd": estimated_cost_usd,
        "cost_per_1k_tokens": _cost_per_1k_tokens(estimated_cost_usd, total_tokens),
        "status_counts": dict(status_counts),
        "workflow_counts": dict(workflow_counts),
        "workflow_metrics": workflow_metrics,
        "top_workflows": _top_workflows(workflow_metrics),
        "error_counts": dict(error_counts),
        "top_errors": _top_errors(error_counts),
        "readiness": _ai_readiness(
            events_total=len(events),
            fallback_rate=fallback_rate,
            error_rate=error_rate,
            average_latency_ms=average_latency_ms,
            feedback_total=feedback_total,
            helpful_count=helpful_count,
            not_helpful_count=not_helpful_count,
        ),
        "feedback": {
            "total": feedback_total,
            "helpful": helpful_count,
            "not_helpful": not_helpful_count,
            "partially_helpful": partially_helpful_count,
            "helpful_rate": helpful_rate,
            "latest": [item.to_dict() for item in feedback_entries[:5]],
        },
        "retrieval_quality": retrieval_quality_analytics(days=days),
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
                "errors": 0,
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
        item["errors"] += 1 if _is_error_event(event) else 0
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
        item["fallback_rate"] = _rate(item["fallbacks"], item["events"])
        item["error_rate"] = _rate(item["errors"], item["events"])
        item["cache_rate"] = _rate(item["cached_tokens"], item["input_tokens"])
        item["cost_per_1k_tokens"] = _cost_per_1k_tokens(
            item["estimated_cost_usd"],
            item["total_tokens"],
        )
        item["estimated_cost_usd"] = round(item["estimated_cost_usd"], 6)
    return metrics


def _top_workflows(workflow_metrics):
    """Return workflow metrics sorted for admin overview cards and tables."""
    items = []
    for workflow, metrics in workflow_metrics.items():
        item = {"workflow": workflow}
        item.update(metrics)
        items.append(item)
    return sorted(
        items,
        key=lambda item: (
            item["errors"],
            item["fallbacks"],
            item["events"],
            item["estimated_cost_usd"],
        ),
        reverse=True,
    )


def _top_errors(error_counts):
    """Return error counts sorted for admin diagnostics."""
    return [
        {"error_category": category, "count": count}
        for category, count in error_counts.most_common()
    ]


def _ai_readiness(
    events_total,
    fallback_rate,
    error_rate,
    average_latency_ms,
    feedback_total,
    helpful_count,
    not_helpful_count,
):
    """Return an admin-facing AI readiness status and actionable reasons."""
    severity = 0
    reasons = []
    if events_total == 0:
        severity = max(severity, 1)
        reasons.append("Noch keine AI-Events im Zeitraum.")
    if error_rate >= 0.25:
        severity = max(severity, 2)
        reasons.append("AI-Fehlerrate liegt bei mindestens 25 Prozent.")
    elif error_rate > 0:
        severity = max(severity, 1)
        reasons.append("AI-Events enthalten Fehler.")
    if fallback_rate >= 0.75 and events_total:
        severity = max(severity, 1)
        reasons.append("Fallback-Anteil liegt bei mindestens 75 Prozent.")
    if average_latency_ms >= 5000:
        severity = max(severity, 1)
        reasons.append("Durchschnittliche AI-Latenz liegt bei mindestens 5 Sekunden.")
    if feedback_total and not_helpful_count > helpful_count:
        severity = max(severity, 1)
        reasons.append("Negatives Feedback ueberwiegt positives Feedback.")
    if not reasons:
        reasons.append("AI-Betrieb wirkt stabil.")
    status = {0: "ok", 1: "warning", 2: "critical"}[severity]
    return {"status": status, "reasons": reasons}


def _is_error_event(event):
    """Return whether an audit event should count as an operational AI error."""
    return bool(event.error_category) or "error" in str(event.status or "").lower()


def _rate(numerator, denominator):
    """Return a rounded ratio or zero when no denominator is available."""
    return round(numerator / denominator, 2) if denominator else 0


def _cost_per_1k_tokens(cost_usd, total_tokens):
    """Return estimated cost per thousand tokens."""
    return round((cost_usd / total_tokens) * 1000, 6) if total_tokens else 0


def _int_value(value):
    """Return a safe integer for audit metadata."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _optional_int_value(value):
    """Return an optional integer for audit metadata."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float_value(value):
    """Return a safe float for audit metadata."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0
