"""Configurable AI governance alert evaluation."""

from __future__ import annotations

from dataclasses import dataclass

from flask import current_app, has_app_context

from app.services.vector_sync_status_service import vector_store_drift_status

SEVERITY_ORDER = {"ok": 0, "warning": 1, "critical": 2}


@dataclass(frozen=True)
class GovernanceRule:
    """One configurable AI governance rule threshold."""

    key: str
    metric: str
    warning: float
    critical: float
    direction: str
    title: str
    recommended_action: str

    def to_dict(self):
        """Return a prompt-safe rule definition."""
        return {
            "key": self.key,
            "metric": self.metric,
            "warning": self.warning,
            "critical": self.critical,
            "direction": self.direction,
            "title": self.title,
            "recommended_action": self.recommended_action,
        }


DEFAULT_RULES = {
    "high_no_source_rate": GovernanceRule(
        key="high_no_source_rate",
        metric="no_source_rate",
        warning=0.2,
        critical=0.4,
        direction="high",
        title="Hohe No-Source-Rate",
        recommended_action=(
            "Knowledge-Gaps, Berechtigungen und strukturierte Datenabdeckung pruefen."
        ),
    ),
    "retrieval_degradation": GovernanceRule(
        key="retrieval_degradation",
        metric="retrieval_hit_rate",
        warning=0.8,
        critical=0.6,
        direction="low",
        title="Retrieval-Degradation",
        recommended_action="Retrieval-Evaluation, Reranking und Quellenindex pruefen.",
    ),
    "retrieval_latency": GovernanceRule(
        key="retrieval_latency",
        metric="p95_retrieval_ms",
        warning=1200,
        critical=3000,
        direction="high",
        title="Hohe Retrieval-Latenz",
        recommended_action="Vector Store, Query-Filter und Indexstatus pruefen.",
    ),
    "excessive_token_usage": GovernanceRule(
        key="excessive_token_usage",
        metric="total_tokens",
        warning=100000,
        critical=250000,
        direction="high",
        title="Exzessive Token-Nutzung",
        recommended_action="Prompt-Kontext, Top-K und Antwortlaengen begrenzen.",
    ),
    "hallucination_risk": GovernanceRule(
        key="hallucination_risk",
        metric="hallucination_warning_count",
        warning=1,
        critical=5,
        direction="high",
        title="Halluzinationsrisiko",
        recommended_action="No-answer Guardrails, Quellenabdeckung und Confidence-Regeln pruefen.",
    ),
    "sync_failures": GovernanceRule(
        key="sync_failures",
        metric="vector_sync_failure_count",
        warning=1,
        critical=3,
        direction="high",
        title="Vector-Sync-Fehler",
        recommended_action="Vector-Store-Sync reparieren und betroffene Dokumente neu indexieren.",
    ),
    "atlas_errors": GovernanceRule(
        key="atlas_errors",
        metric="atlas_errors",
        warning=1,
        critical=3,
        direction="high",
        title="Atlas Vector Search Fehler",
        recommended_action="Atlas-Erreichbarkeit, Index und Query-Pipeline pruefen.",
    ),
    "atlas_unavailable": GovernanceRule(
        key="atlas_unavailable",
        metric="atlas_unavailable",
        warning=1,
        critical=1,
        direction="high",
        title="Atlas Vector Search nicht verfuegbar",
        recommended_action="Atlas-Verbindung, pymongo, Secrets und Netzwerkzugriff pruefen.",
    ),
    "atlas_fallbacks": GovernanceRule(
        key="atlas_fallbacks",
        metric="atlas_fallbacks",
        warning=1,
        critical=1,
        direction="high",
        title="Atlas Vector Search Fallback aktiv",
        recommended_action="Atlas-Konfiguration reparieren und Fallback-Zustand beenden.",
    ),
    "atlas_sync_failures": GovernanceRule(
        key="atlas_sync_failures",
        metric="atlas_sync_failures",
        warning=1,
        critical=3,
        direction="high",
        title="Atlas Sync-Fehler",
        recommended_action=(
            "Atlas-Sync reparieren und betroffene Knowledge-Dokumente neu indexieren."
        ),
    ),
    "atlas_sync_drift": GovernanceRule(
        key="atlas_sync_drift",
        metric="atlas_sync_drift",
        warning=1,
        critical=1,
        direction="high",
        title="Atlas Sync-Drift",
        recommended_action="Atlas-Count-Mismatch pruefen und Knowledge-Dokumente neu indexieren.",
    ),
    "atlas_latency_degradation": GovernanceRule(
        key="atlas_latency_degradation",
        metric="atlas_latency",
        warning=500,
        critical=1500,
        direction="high",
        title="Atlas Latenz-Degradation",
        recommended_action="Atlas-Index, numCandidates, Netzwerk und Cluster-Auslastung pruefen.",
    ),
    "atlas_retrieval_degradation": GovernanceRule(
        key="atlas_retrieval_degradation",
        metric="atlas_retrieval_hit_rate",
        warning=0.8,
        critical=0.6,
        direction="low",
        title="Atlas Retrieval-Degradation",
        recommended_action="Atlas-Recall, Sync-Status, Embedding-Dimensionen und Filter pruefen.",
    ),
}


def evaluate_governance_alerts(
    metrics,
    quality_metrics=None,
    retrieval_monitoring=None,
    telemetry=None,
    provider_readiness=None,
    vector_drift=None,
):
    """Return AI governance alerts from existing observability metadata."""
    if not _alerts_enabled():
        return _empty_payload(disabled=True)

    metrics = metrics or {}
    telemetry = telemetry or {}
    vector_drift = vector_drift if vector_drift is not None else _safe_vector_drift_status()
    values = _governance_values(
        metrics,
        quality_metrics,
        retrieval_monitoring,
        telemetry,
        vector_drift,
    )
    alerts = []
    for rule in _rules():
        if rule.key == "retrieval_degradation" and _float_value(metrics.get("total_requests")) == 0:
            continue
        if rule.key == "atlas_retrieval_degradation" and values.get("atlas_queries", 0) == 0:
            continue
        value = values.get(rule.metric, 0)
        status = _rule_status(value, rule)
        if status == "ok":
            continue
        alerts.append(_alert(rule, value, status))

    alerts.extend(_cost_spike_alerts(metrics))
    alerts.extend(_vector_store_alerts(vector_drift))
    alerts.sort(key=lambda item: (SEVERITY_ORDER[item["severity"]], item["rule"]), reverse=True)
    return {
        "status": _worst_status(alert["severity"] for alert in alerts),
        "alert_count": len(alerts),
        "critical_count": sum(1 for alert in alerts if alert["severity"] == "critical"),
        "warning_count": sum(1 for alert in alerts if alert["severity"] == "warning"),
        "alerts": alerts,
        "rules": [rule.to_dict() for rule in _rules()],
        "config": _config_summary(),
        "privacy": {
            "stores_prompt_text": False,
            "stores_answer_text": False,
            "stores_chunk_text": False,
            "source": "ai_observability_metrics_and_vector_drift_metadata",
        },
    }


def _governance_values(metrics, quality_metrics, retrieval_monitoring, telemetry, vector_drift):
    """Return normalized metric values used by governance rules."""
    quality_metrics = quality_metrics or {}
    retrieval_monitoring = retrieval_monitoring or {}
    telemetry = telemetry or {}
    vector_drift = vector_drift or {}
    retrieval_slo = metrics.get("retrieval_slo") or telemetry.get("retrieval_slo") or {}
    last_values = retrieval_slo.get("last_values") or {}
    atlas_queries = _metric_value("atlas_queries", metrics, last_values, vector_drift)
    atlas_retrieval_hit_rate = _metric_value(
        "atlas_retrieval_hit_rate",
        metrics,
        last_values,
        vector_drift,
    )
    if atlas_retrieval_hit_rate == 0 and _atlas_context(vector_drift) and atlas_queries:
        atlas_retrieval_hit_rate = _float_value(
            metrics.get("retrieval_hit_rate", quality_metrics.get("retrieval_hit_rate")),
        )
    return {
        "no_source_rate": _float_value(metrics.get("no_source_rate")),
        "retrieval_hit_rate": _float_value(
            metrics.get("retrieval_hit_rate", quality_metrics.get("retrieval_hit_rate")),
        ),
        "p95_retrieval_ms": _float_value(metrics.get("p95_retrieval_ms")),
        "total_tokens": _float_value(metrics.get("total_tokens")),
        "hallucination_warning_count": _float_value(
            metrics.get("hallucination_warning_count"),
        ),
        "vector_sync_failure_count": _float_value(
            vector_drift.get("vector_sync_failure_count")
            or last_values.get("vector_sync_failure_count")
            or metrics.get("vector_sync_failure_count"),
        ),
        "atlas_queries": atlas_queries,
        "atlas_errors": _metric_value("atlas_errors", metrics, last_values, vector_drift),
        "atlas_unavailable": _atlas_unavailable_value(vector_drift),
        "atlas_fallbacks": _metric_value("atlas_fallbacks", metrics, last_values, vector_drift),
        "atlas_sync_failures": _metric_value(
            "atlas_sync_failures",
            metrics,
            last_values,
            vector_drift,
        ),
        "atlas_sync_drift": _atlas_sync_drift_value(metrics, last_values, vector_drift),
        "atlas_latency": _metric_value("atlas_latency", metrics, last_values, vector_drift),
        "atlas_retrieval_hit_rate": atlas_retrieval_hit_rate,
        "retrieval_action_count": _float_value(
            metrics.get("retrieval_action_count")
            or (retrieval_monitoring.get("action_summary") or {}).get("total"),
        ),
    }


def _rules():
    """Return configured governance rules."""
    return [
        _configured_rule(DEFAULT_RULES["high_no_source_rate"]),
        _configured_rule(DEFAULT_RULES["retrieval_degradation"]),
        _configured_rule(DEFAULT_RULES["retrieval_latency"]),
        _configured_rule(DEFAULT_RULES["excessive_token_usage"]),
        _configured_rule(DEFAULT_RULES["hallucination_risk"]),
        _configured_rule(DEFAULT_RULES["sync_failures"]),
        _configured_rule(DEFAULT_RULES["atlas_errors"]),
        _configured_rule(DEFAULT_RULES["atlas_unavailable"]),
        _configured_rule(DEFAULT_RULES["atlas_fallbacks"]),
        _configured_rule(DEFAULT_RULES["atlas_sync_failures"]),
        _configured_rule(DEFAULT_RULES["atlas_sync_drift"]),
        _configured_rule(DEFAULT_RULES["atlas_latency_degradation"]),
        _configured_rule(DEFAULT_RULES["atlas_retrieval_degradation"]),
    ]


def _configured_rule(rule):
    """Return one rule with environment-configured thresholds applied."""
    prefix = f"AI_GOVERNANCE_{rule.key.upper()}"
    return GovernanceRule(
        key=rule.key,
        metric=rule.metric,
        warning=_config_float(f"{prefix}_WARNING", rule.warning),
        critical=_config_float(f"{prefix}_CRITICAL", rule.critical),
        direction=rule.direction,
        title=rule.title,
        recommended_action=rule.recommended_action,
    )


def _rule_status(value, rule):
    """Return the alert severity for one rule and metric value."""
    numeric_value = _float_value(value)
    if rule.direction == "low":
        if numeric_value <= rule.critical:
            return "critical"
        if numeric_value <= rule.warning:
            return "warning"
        return "ok"
    if numeric_value >= rule.critical:
        return "critical"
    if numeric_value >= rule.warning:
        return "warning"
    return "ok"


def _alert(rule, value, severity):
    """Return one prompt-safe alert row."""
    threshold = rule.critical if severity == "critical" else rule.warning
    return {
        "id": f"{rule.key}:{severity}",
        "rule": rule.key,
        "metric": rule.metric,
        "severity": severity,
        "title": rule.title,
        "value": _round_value(value),
        "threshold": threshold,
        "direction": rule.direction,
        "message": f"{rule.title}: {rule.metric}={_round_value(value)}",
        "recommended_action": rule.recommended_action,
        "source": "ai_observability",
    }


def _cost_spike_alerts(metrics):
    """Return alerts for unusual cost increases inside rolling cost windows."""
    costs = metrics.get("costs") or {}
    windows = metrics.get("cost_windows") or {}
    day_cost = _float_value(costs.get("day", windows.get("day")))
    week_cost = _float_value(costs.get("week", windows.get("week")))
    minimum = _config_float("AI_GOVERNANCE_COST_SPIKE_MIN_USD", 0.01)
    if day_cost < minimum or week_cost <= 0:
        return []
    daily_average = week_cost / 7
    if daily_average <= 0:
        return []
    ratio = day_cost / daily_average
    warning = _config_float("AI_GOVERNANCE_COST_SPIKE_MULTIPLIER_WARNING", 2.0)
    critical = _config_float("AI_GOVERNANCE_COST_SPIKE_MULTIPLIER_CRITICAL", 3.0)
    severity = "critical" if ratio >= critical else "warning" if ratio >= warning else "ok"
    if severity == "ok":
        return []
    return [
        {
            "id": f"unusual_cost_increase:{severity}",
            "rule": "unusual_cost_increase",
            "metric": "cost_spike_ratio",
            "severity": severity,
            "title": "Ungewoehnlicher Kostenanstieg",
            "value": round(ratio, 4),
            "threshold": critical if severity == "critical" else warning,
            "direction": "high",
            "message": f"AI-Kosten heute liegen bei {round(ratio, 2)}x des Wochenmittels.",
            "recommended_action": "Top-Workflows, Token-Nutzung und Modellrouting pruefen.",
            "source": "ai_observability",
        },
    ]


def _vector_store_alerts(vector_drift):
    """Return vector-store failure and fallback alerts."""
    if not isinstance(vector_drift, dict):
        return []
    if _atlas_context(vector_drift):
        return []
    alerts = []
    if vector_drift.get("store_error"):
        alerts.append(
            {
                "id": "vector_store_failure:critical",
                "rule": "vector_store_failure",
                "metric": "store_error",
                "severity": "critical",
                "title": "Vector Store Fehler",
                "value": 1,
                "threshold": 1,
                "direction": "high",
                "message": "Vector Store meldet einen Fehler.",
                "recommended_action": (
                    "Vector-Store-Konfiguration und Backend-Erreichbarkeit pruefen."
                ),
                "source": "vector_store_drift",
            },
        )
    if vector_drift.get("fallback_active"):
        alerts.append(
            {
                "id": "vector_store_fallback:warning",
                "rule": "vector_store_fallback",
                "metric": "fallback_active",
                "severity": "warning",
                "title": "Vector Store Fallback aktiv",
                "value": 1,
                "threshold": 1,
                "direction": "high",
                "message": "Konfigurierter Vector Store nutzt einen Fallback.",
                "recommended_action": "Externen Vector Store reparieren oder Reindex planen.",
                "source": "vector_store_drift",
            },
        )
    return alerts


def _metric_value(metric, metrics, last_values, vector_drift):
    """Return one governance metric from observability, SLO or drift payloads."""
    return _float_value(
        vector_drift.get(metric)
        if metric in vector_drift
        else last_values.get(metric)
        if metric in last_values
        else metrics.get(metric)
    )


def _atlas_unavailable_value(vector_drift):
    """Return whether Atlas is unavailable according to drift metadata."""
    if not _atlas_context(vector_drift):
        return 0.0
    if vector_drift.get("store_error"):
        return 1.0
    atlas_payload = vector_drift.get("atlas") or {}
    if (
        isinstance(atlas_payload, dict)
        and atlas_payload.get("configured")
        and not atlas_payload.get("active")
    ):
        return 1.0
    return 0.0


def _atlas_sync_drift_value(metrics, last_values, vector_drift):
    """Return whether Atlas has sync drift or reindex-required metadata."""
    if _metric_value("atlas_sync_drift", metrics, last_values, vector_drift):
        return 1.0
    drift_flags = (
        vector_drift.get("atlas_reindex_required"),
        vector_drift.get("chunk_vector_count_mismatch"),
        bool(vector_drift.get("vector_mismatches")),
    )
    if _atlas_context(vector_drift) and any(bool(flag) for flag in drift_flags):
        return 1.0
    if _metric_value("atlas_reindex_required", metrics, last_values, vector_drift):
        return 1.0
    return 0.0


def _atlas_context(vector_drift):
    """Return whether a vector-drift payload describes MongoDB Atlas."""
    if not isinstance(vector_drift, dict):
        return False
    atlas_payload = vector_drift.get("atlas")
    if isinstance(atlas_payload, dict) and (
        atlas_payload.get("configured") or atlas_payload.get("active")
    ):
        return True
    store_names = {
        str(vector_drift.get("store") or "").lower(),
        str(vector_drift.get("configured_store") or "").lower(),
    }
    return bool(store_names & {"mongodb_atlas", "mongo_atlas", "atlas"})


def _safe_vector_drift_status():
    """Return vector drift status without leaking backend internals."""
    try:
        return vector_store_drift_status()
    except Exception as exc:  # pragma: no cover - defensive governance path
        return {
            "store": "unavailable",
            "store_error": exc.__class__.__name__,
            "fallback_active": False,
        }


def _alerts_enabled():
    """Return whether governance alerts are enabled."""
    return _config_bool("AI_GOVERNANCE_ALERTS_ENABLED", True)


def _empty_payload(disabled=False):
    """Return an empty governance payload."""
    return {
        "status": "disabled" if disabled else "ok",
        "alert_count": 0,
        "critical_count": 0,
        "warning_count": 0,
        "alerts": [],
        "rules": [rule.to_dict() for rule in _rules()],
        "config": _config_summary(),
        "privacy": {
            "stores_prompt_text": False,
            "stores_answer_text": False,
            "stores_chunk_text": False,
            "source": "ai_observability_metrics_and_vector_drift_metadata",
        },
    }


def _config_summary():
    """Return prompt-safe governance configuration metadata."""
    return {
        "enabled": _alerts_enabled(),
        "cost_spike_min_usd": _config_float("AI_GOVERNANCE_COST_SPIKE_MIN_USD", 0.01),
        "cost_spike_multiplier_warning": _config_float(
            "AI_GOVERNANCE_COST_SPIKE_MULTIPLIER_WARNING",
            2.0,
        ),
        "cost_spike_multiplier_critical": _config_float(
            "AI_GOVERNANCE_COST_SPIKE_MULTIPLIER_CRITICAL",
            3.0,
        ),
    }


def _worst_status(statuses):
    """Return the worst alert status."""
    worst = "ok"
    for status in statuses:
        if SEVERITY_ORDER.get(status, 0) > SEVERITY_ORDER[worst]:
            worst = status
    return worst


def _config_float(key, default):
    """Return a float config value."""
    if not has_app_context():
        return default
    try:
        return float(current_app.config.get(key, default))
    except (TypeError, ValueError):
        return default


def _config_bool(key, default):
    """Return a boolean config value."""
    if not has_app_context():
        return default
    value = current_app.config.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _float_value(value):
    """Return a safe float value."""
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _round_value(value):
    """Return a stable rounded alert value."""
    return round(_float_value(value), 4)
