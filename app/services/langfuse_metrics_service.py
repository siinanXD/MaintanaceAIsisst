"""Langfuse Metrics API client for admin cost dashboards."""

from __future__ import annotations

import base64
import json
import logging
from datetime import UTC, datetime, timedelta
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from flask import current_app

from app.services.langfuse_service import langfuse_host, langfuse_status

logger = logging.getLogger(__name__)

DEFAULT_LANGFUSE_METRICS_TIMEOUT_SECONDS = 3.0


def langfuse_metrics_summary(days=7, row_limit=20, config=None, http_get=None):
    """Return aggregated Langfuse usage and cost metrics for the admin dashboard."""
    config = config or current_app.config
    status = langfuse_status(config)
    window_days = _bounded_int(days, default=7, minimum=1, maximum=90)
    limit = _bounded_int(row_limit, default=20, minimum=1, maximum=100)
    base_payload = _base_metrics_payload(status, window_days, config)
    if not status["enabled"]:
        return _unavailable_payload(base_payload, "disabled", "Langfuse ist deaktiviert.")
    if not status["configured"]:
        return _unavailable_payload(
            base_payload,
            "unconfigured",
            "Langfuse API-Keys fehlen.",
        )

    http_get = http_get or _http_get_json
    try:
        aggregate = _metrics_query(
            config,
            _aggregate_query(window_days),
            http_get=http_get,
        )
        models = _metrics_query(
            config,
            _dimension_query(window_days, "providedModelName", "totalCost_sum", limit),
            http_get=http_get,
        )
        workflows = _metrics_query(
            config,
            _dimension_query(window_days, "traceName", "totalCost_sum", limit),
            http_get=http_get,
        )
    except LangfuseMetricsError as exc:
        logger.warning("langfuse_metrics_unavailable reason=%s", exc.reason)
        return _unavailable_payload(base_payload, exc.reason, exc.message)

    first_row = _first_row(aggregate)
    payload = {
        **base_payload,
        "available": True,
        "status": "ok",
        "message": "Langfuse Metrics geladen.",
        "observation_count": _int_metric(first_row.get("count_count")),
        "total_tokens": _int_metric(first_row.get("totalTokens_sum")),
        "total_cost_usd": _money_metric(first_row.get("totalCost_sum")),
        "average_latency_ms": round(_float_metric(first_row.get("latency_avg"))),
        "models": _dimension_rows(models, "providedModelName", "model"),
        "workflows": _dimension_rows(workflows, "traceName", "workflow"),
    }
    payload["cost_per_1k_tokens"] = _cost_per_1k_tokens(
        payload["total_cost_usd"],
        payload["total_tokens"],
    )
    return payload


class LangfuseMetricsError(Exception):
    """Raised when Langfuse metrics cannot be loaded safely."""

    def __init__(self, reason, message):
        """Create an error with a stable reason and user-facing message."""
        super().__init__(message)
        self.reason = reason
        self.message = message


def _base_metrics_payload(status, window_days, config):
    """Return the common Langfuse metrics payload shape."""
    return {
        "enabled": bool(status.get("enabled")),
        "configured": bool(status.get("configured")),
        "tracing_ready": bool(status.get("ready")),
        "installed": bool(status.get("installed")),
        "available": False,
        "status": "unavailable",
        "message": "",
        "host": langfuse_host(config),
        "window_days": window_days,
        "observation_count": 0,
        "total_tokens": 0,
        "total_cost_usd": 0.0,
        "average_latency_ms": 0,
        "cost_per_1k_tokens": 0,
        "models": [],
        "workflows": [],
    }


def _unavailable_payload(payload, status, message):
    """Return a complete unavailable metrics payload."""
    result = dict(payload)
    result["available"] = False
    result["status"] = status
    result["message"] = message
    return result


def _metrics_query(config, query, http_get):
    """Execute one Langfuse Metrics API v2 query."""
    host = langfuse_host(config).rstrip("/")
    url = f"{host}/api/public/v2/metrics?{urlencode({'query': json.dumps(query)})}"
    timeout = _metrics_timeout(config)
    try:
        return http_get(url, _auth_header(config), timeout)
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise LangfuseMetricsError(
                "authentication_failed",
                "Langfuse Metrics API lehnt die konfigurierten Keys ab.",
            ) from exc
        if exc.code == 404:
            raise LangfuseMetricsError(
                "metrics_api_unavailable",
                "Langfuse Metrics API v2 ist fuer diesen Host nicht verfuegbar.",
            ) from exc
        raise LangfuseMetricsError(
            "http_error",
            f"Langfuse Metrics API antwortet mit Status {exc.code}.",
        ) from exc
    except TimeoutError as exc:
        raise LangfuseMetricsError(
            "timeout",
            "Langfuse Metrics API antwortet nicht rechtzeitig.",
        ) from exc
    except URLError as exc:
        raise LangfuseMetricsError(
            "connection_error",
            "Langfuse Metrics API ist nicht erreichbar.",
        ) from exc
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise LangfuseMetricsError(
            "invalid_response",
            "Langfuse Metrics API liefert keine gueltige JSON-Antwort.",
        ) from exc


def _http_get_json(url, authorization_header, timeout):
    """Return JSON from a GET request using Langfuse Basic Auth."""
    request = Request(
        url,
        headers={
            "Authorization": authorization_header,
            "Accept": "application/json",
        },
        method="GET",
    )
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _auth_header(config):
    """Return a Basic Auth header for Langfuse public and secret keys."""
    public_key = str(config.get("LANGFUSE_PUBLIC_KEY") or "")
    secret_key = str(config.get("LANGFUSE_SECRET_KEY") or "")
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode("ascii")
    return f"Basic {token}"


def _aggregate_query(days):
    """Return a Metrics API query for total cost, tokens, count, and latency."""
    return {
        "view": "observations",
        "metrics": [
            {"measure": "count", "aggregation": "count"},
            {"measure": "totalTokens", "aggregation": "sum"},
            {"measure": "totalCost", "aggregation": "sum"},
            {"measure": "latency", "aggregation": "avg"},
        ],
        "dimensions": [],
        "filters": [],
        "fromTimestamp": _from_timestamp(days),
        "toTimestamp": _to_timestamp(),
        "rowLimit": 1,
    }


def _dimension_query(days, dimension, order_field, row_limit):
    """Return a Metrics API query grouped by one dimension."""
    return {
        "view": "observations",
        "metrics": [
            {"measure": "count", "aggregation": "count"},
            {"measure": "totalTokens", "aggregation": "sum"},
            {"measure": "totalCost", "aggregation": "sum"},
            {"measure": "latency", "aggregation": "avg"},
        ],
        "dimensions": [{"field": dimension}],
        "filters": [],
        "fromTimestamp": _from_timestamp(days),
        "toTimestamp": _to_timestamp(),
        "orderBy": [{"field": order_field, "direction": "desc"}],
        "rowLimit": row_limit,
    }


def _from_timestamp(days):
    """Return an ISO UTC start timestamp for a rolling day window."""
    return _iso_timestamp(datetime.now(UTC) - timedelta(days=days))


def _to_timestamp():
    """Return the current ISO UTC timestamp."""
    return _iso_timestamp(datetime.now(UTC))


def _iso_timestamp(value):
    """Return a compact ISO timestamp accepted by Langfuse."""
    return value.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _metrics_timeout(config):
    """Return the Langfuse metrics request timeout in seconds."""
    try:
        return float(
            config.get(
                "LANGFUSE_METRICS_TIMEOUT_SECONDS",
                DEFAULT_LANGFUSE_METRICS_TIMEOUT_SECONDS,
            )
        )
    except (TypeError, ValueError):
        return DEFAULT_LANGFUSE_METRICS_TIMEOUT_SECONDS


def _first_row(payload):
    """Return the first data row from a Langfuse response."""
    rows = payload.get("data") if isinstance(payload, dict) else []
    if isinstance(rows, list) and rows:
        return rows[0] if isinstance(rows[0], dict) else {}
    return {}


def _dimension_rows(payload, source_key, target_key):
    """Return normalized dimension rows from a Langfuse metrics response."""
    rows = payload.get("data") if isinstance(payload, dict) else []
    if not isinstance(rows, list):
        return []
    normalized_rows = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        label = str(row.get(source_key) or "").strip()
        if not label:
            label = "unbekannt"
        total_tokens = _int_metric(row.get("totalTokens_sum"))
        total_cost_usd = _money_metric(row.get("totalCost_sum"))
        normalized_rows.append(
            {
                target_key: label,
                "observation_count": _int_metric(row.get("count_count")),
                "total_tokens": total_tokens,
                "total_cost_usd": total_cost_usd,
                "average_latency_ms": round(_float_metric(row.get("latency_avg"))),
                "cost_per_1k_tokens": _cost_per_1k_tokens(total_cost_usd, total_tokens),
            }
        )
    return normalized_rows


def _bounded_int(value, default, minimum, maximum):
    """Return an integer constrained to an inclusive range."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return min(max(parsed, minimum), maximum)


def _int_metric(value):
    """Return a safe integer metric value."""
    return int(round(_float_metric(value)))


def _money_metric(value):
    """Return a rounded USD metric value."""
    return round(_float_metric(value), 6)


def _float_metric(value):
    """Return a safe float metric value."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _cost_per_1k_tokens(cost_usd, total_tokens):
    """Return cost per thousand tokens for Langfuse metrics."""
    return round((cost_usd / total_tokens) * 1000, 6) if total_tokens else 0
