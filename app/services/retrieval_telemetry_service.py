"""Prompt-safe retrieval telemetry and quality analytics."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta
from math import ceil

from flask import current_app, has_app_context

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import AIAuditEvent, AIFeedback, KnowledgeChunk, KnowledgeDocument, KnowledgeGap
from app.services.ai_confidence_service import LOW_CONFIDENCE_THRESHOLD
from app.services.vector_sync_status_service import vector_store_drift_status

DEFAULT_WINDOW_DAYS = 30
DEFAULT_LIMIT = 10
DEFAULT_LOW_CONFIDENCE_SCORE = LOW_CONFIDENCE_THRESHOLD
DEFAULT_LOW_SOURCE_SCORE = 20.0
MAX_LIMIT = 50
POSITIVE_RATINGS = {"helpful"}
PARTIAL_RATINGS = {"partially_helpful"}
NEGATIVE_RATINGS = {"not_helpful"}
SLO_THRESHOLDS = {
    "retrieval_p95_ms": {"warning": 1200, "critical": 3000},
    "no_source_rate": {"warning": 0.2, "critical": 0.4},
    "low_confidence_rate": {"warning": 0.2, "critical": 0.4},
    "permission_filtered_candidate_count": {"warning": 3, "critical": 10},
    "negative_feedback_rate": {"warning": 0.15, "critical": 0.3},
    "safety_risk_count": {"warning": 1, "critical": 5},
    "fallback_rate": {"warning": 0.25, "critical": 0.5},
    "vector_sync_failure_count": {"warning": 1, "critical": 3},
    "stale_index_count": {"warning": 1, "critical": 5},
}


@dataclass
class SourceTelemetry:
    """Aggregate retrieval usage and feedback for one source reference."""

    source_type: str
    source_id: int | None
    chunk_id: int | None
    title: str = ""
    audit_uses: int = 0
    helpful_feedback: int = 0
    partially_helpful_feedback: int = 0
    not_helpful_feedback: int = 0
    low_score_uses: int = 0
    score_total: float = 0.0
    score_count: int = 0
    workflows: Counter = field(default_factory=Counter)
    quality_statuses: Counter = field(default_factory=Counter)

    @property
    def feedback_count(self):
        """Return total feedback count linked to this source."""
        return (
            self.helpful_feedback
            + self.partially_helpful_feedback
            + self.not_helpful_feedback
        )

    @property
    def average_score(self):
        """Return average retrieval score for this source."""
        if not self.score_count:
            return None
        return round(self.score_total / self.score_count, 2)

    @property
    def negative_rate(self):
        """Return negative feedback rate for this source."""
        if not self.feedback_count:
            return 0
        return round(self.not_helpful_feedback / self.feedback_count, 2)

    def add_score(self, score, low_score_threshold):
        """Add one retrieval score sample to this source."""
        numeric_score = _optional_float(score)
        if numeric_score is None:
            return
        self.score_total += numeric_score
        self.score_count += 1
        if numeric_score <= low_score_threshold:
            self.low_score_uses += 1

    def add_feedback(self, rating):
        """Add one feedback rating to this source."""
        if rating in POSITIVE_RATINGS:
            self.helpful_feedback += 1
        elif rating in PARTIAL_RATINGS:
            self.partially_helpful_feedback += 1
        elif rating in NEGATIVE_RATINGS:
            self.not_helpful_feedback += 1

    def to_dict(self):
        """Return a prompt-safe telemetry payload for this source."""
        return {
            "type": self.source_type,
            "id": self.source_id,
            "chunk_id": self.chunk_id,
            "title": _source_title(self),
            "audit_uses": self.audit_uses,
            "feedback_count": self.feedback_count,
            "helpful_feedback": self.helpful_feedback,
            "partially_helpful_feedback": self.partially_helpful_feedback,
            "not_helpful_feedback": self.not_helpful_feedback,
            "negative_rate": self.negative_rate,
            "low_score_uses": self.low_score_uses,
            "average_score": self.average_score,
            "top_workflows": _counter_payload(self.workflows),
            "quality_status_counts": dict(self.quality_statuses),
        }


def retrieval_quality_analytics(days=None, limit=None):
    """Return aggregated retrieval quality telemetry without storing raw content."""
    window_days = _window_days(days)
    item_limit = _limit(limit)
    since = utc_now() - timedelta(days=window_days)
    previous_since = since - timedelta(days=window_days)
    events = _audit_events_since(since)
    previous_events = _audit_events_between(previous_since, since)
    feedback_entries = _feedback_since(since)
    previous_feedback_entries = _feedback_between(previous_since, since)
    source_stats = _source_telemetry(events, feedback_entries)
    used_chunk_ids = _used_chunk_ids(source_stats)
    return {
        "window_days": window_days,
        "events": _event_overview(events),
        "retrieval_slo": retrieval_slo_metrics(
            events=events,
            feedback_entries=feedback_entries,
            previous_events=previous_events,
            previous_feedback_entries=previous_feedback_entries,
            window_days=window_days,
        ),
        "source_usage": _source_usage_summary(source_stats, item_limit),
        "poor_sources": _poor_source_summary(source_stats, item_limit),
        "unsuccessful_questions": _unsuccessful_question_summary(events),
        "knowledge_gaps": _knowledge_gap_summary(since, item_limit),
        "negative_feedback": _negative_feedback_summary(feedback_entries, item_limit),
        "unused_chunks": _unused_chunk_summary(used_chunk_ids, item_limit),
        "privacy": {
            "stores_prompt_text": False,
            "stores_answer_text": False,
            "stores_chunk_text": False,
            "source": "aggregated_audit_feedback_gap_metadata",
        },
    }


def retrieval_slo_metrics(
    events=None,
    feedback_entries=None,
    previous_events=None,
    previous_feedback_entries=None,
    window_days=None,
):
    """Return prompt-safe retrieval SLO metrics, trends, and warning status."""
    current_events = list(events or [])
    current_feedback = list(feedback_entries or [])
    previous_event_list = list(previous_events or [])
    previous_feedback = list(previous_feedback_entries or [])
    drift_status = vector_store_drift_status()
    current_values = _slo_metric_values(
        current_events,
        current_feedback,
        drift_status=drift_status,
    )
    previous_values = _slo_metric_values(
        previous_event_list,
        previous_feedback,
        drift_status={},
    )
    warnings = _slo_warnings(current_values)
    return {
        "window_days": _window_days(window_days),
        "status": _worst_status([warning["status"] for warning in warnings]),
        "last_values": current_values,
        "previous_values": previous_values,
        "trends": _slo_trends(current_values, previous_values),
        "warnings": warnings,
        "thresholds": SLO_THRESHOLDS,
        "privacy": {
            "stores_prompt_text": False,
            "stores_answer_text": False,
            "stores_chunk_text": False,
            "source": "ai_audit_metadata_feedback_and_vector_drift",
        },
    }


def _audit_events_since(since):
    """Return audit events in the telemetry window."""
    return (
        AIAuditEvent.query.filter(AIAuditEvent.created_at >= since)
        .order_by(AIAuditEvent.created_at.desc(), AIAuditEvent.id.desc())
        .all()
    )


def _audit_events_between(start_at, end_at):
    """Return audit events inside a closed-open time range."""
    return (
        AIAuditEvent.query.filter(
            AIAuditEvent.created_at >= start_at,
            AIAuditEvent.created_at < end_at,
        )
        .order_by(AIAuditEvent.created_at.desc(), AIAuditEvent.id.desc())
        .all()
    )


def _feedback_since(since):
    """Return feedback entries in the telemetry window."""
    return (
        AIFeedback.query.filter(AIFeedback.created_at >= since)
        .order_by(AIFeedback.created_at.desc(), AIFeedback.id.desc())
        .all()
    )


def _feedback_between(start_at, end_at):
    """Return feedback entries inside a closed-open time range."""
    return (
        AIFeedback.query.filter(
            AIFeedback.created_at >= start_at,
            AIFeedback.created_at < end_at,
        )
        .order_by(AIFeedback.created_at.desc(), AIFeedback.id.desc())
        .all()
    )


def _slo_metric_values(events, feedback_entries, drift_status=None):
    """Return central retrieval SLO values for one event window."""
    event_count = len(events)
    feedback_count = len(feedback_entries)
    negative_feedback_count = sum(
        1 for feedback in feedback_entries if feedback.rating in NEGATIVE_RATINGS
    )
    drift = drift_status if isinstance(drift_status, dict) else {}
    return {
        "event_count": event_count,
        "retrieval_p95_ms": _percentile(
            [_retrieval_duration_ms(event) for event in events],
            0.95,
        ),
        "no_source_rate": _rate(
            sum(1 for event in events if int(event.source_count or 0) == 0),
            event_count,
        ),
        "low_confidence_rate": _rate(
            sum(1 for event in events if _is_low_confidence_event(event)),
            event_count,
        ),
        "permission_filtered_candidate_count": sum(
            _permission_filtered_candidate_count(event) for event in events
        ),
        "negative_feedback_rate": _rate(negative_feedback_count, feedback_count),
        "safety_risk_count": sum(1 for event in events if _event_has_safety_risk(event)),
        "fallback_rate": _rate(
            sum(1 for event in events if bool(event.fallback_used)),
            event_count,
        ),
        "vector_sync_failure_count": int(drift.get("vector_sync_failure_count") or 0),
        "stale_index_count": int(drift.get("stale_document_count") or 0),
    }


def _retrieval_duration_ms(event):
    """Return retrieval duration metadata for one audit event."""
    explainability = event.retrieval_explainability()
    if not isinstance(explainability, dict):
        return None
    return _optional_int(explainability.get("retrieval_duration_ms"))


def _is_low_confidence_event(event):
    """Return whether an audit event falls below the low-confidence SLO threshold."""
    if event.confidence_score is None:
        return False
    return int(event.confidence_score) <= _low_confidence_score()


def _permission_filtered_candidate_count(event):
    """Return a safe proxy for scopes filtered by permissions."""
    requested = set(_json_list(event.requested_scopes))
    allowed = set(_json_list(event.allowed_scopes))
    blocked_scope_count = len(requested - allowed)
    if str(event.status or "") == "permission_denied" and not blocked_scope_count:
        return 1
    return blocked_scope_count


def _event_has_safety_risk(event):
    """Return whether audit metadata contains a safety-relevant risk signal."""
    explainability = event.retrieval_explainability()
    if not isinstance(explainability, dict):
        return False
    safety = explainability.get("safety")
    post_safety = explainability.get("post_generation_safety")
    return _safety_relevant(safety) or _safety_relevant(post_safety)


def _safety_relevant(value):
    """Return whether a serialized safety payload is safety relevant."""
    return isinstance(value, dict) and bool(value.get("safety_relevant"))


def _percentile(values, percentile):
    """Return a nearest-rank percentile from optional numeric values."""
    numeric_values = sorted(value for value in values if value is not None)
    if not numeric_values:
        return 0
    index = max(0, min(len(numeric_values) - 1, ceil(len(numeric_values) * percentile) - 1))
    return int(round(numeric_values[index]))


def _slo_warnings(values):
    """Return warning rows for SLO values that cross configured thresholds."""
    warnings = []
    for metric, thresholds in SLO_THRESHOLDS.items():
        value = values.get(metric, 0)
        status = _threshold_status(value, thresholds)
        if status == "ok":
            continue
        warnings.append(
            {
                "metric": metric,
                "value": value,
                "status": status,
                "threshold": thresholds[status],
            }
        )
    return warnings


def _threshold_status(value, thresholds):
    """Return ok, warning, or critical for one SLO value."""
    if value >= thresholds["critical"]:
        return "critical"
    if value >= thresholds["warning"]:
        return "warning"
    return "ok"


def _slo_trends(current_values, previous_values):
    """Return simple trends for every central retrieval SLO metric."""
    trends = {}
    for metric in SLO_THRESHOLDS:
        current = current_values.get(metric, 0)
        previous = previous_values.get(metric, 0)
        delta = round(current - previous, 4)
        trends[metric] = {
            "current": current,
            "previous": previous,
            "delta": delta,
            "direction": _trend_direction(delta),
            "status": _trend_status(delta),
        }
    return trends


def _trend_direction(delta):
    """Return up, down, or flat for a numeric trend delta."""
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


def _trend_status(delta):
    """Return whether a higher SLO value is operationally better or worse."""
    if delta > 0:
        return "worse"
    if delta < 0:
        return "better"
    return "stable"


def _worst_status(statuses):
    """Return the worst status from a list of warning severities."""
    order = {"ok": 0, "warning": 1, "critical": 2}
    worst = "ok"
    for status in statuses:
        if order.get(status, 0) > order[worst]:
            worst = status
    return worst


def _rate(numerator, denominator):
    """Return a rounded ratio or zero for an empty denominator."""
    return round(numerator / denominator, 4) if denominator else 0.0


def _source_telemetry(events, feedback_entries):
    """Return source telemetry keyed by type, document id and chunk id."""
    source_stats = {}
    low_score_threshold = _low_source_score()
    for event in events:
        for source in _audit_sources(event):
            stat = _source_stat(source_stats, source)
            if not stat:
                continue
            stat.audit_uses += 1
            stat.workflows[str(event.workflow or "unknown")] += 1
            stat.add_score(_source_score(source), low_score_threshold)
            quality_status = _source_quality_status(source)
            if quality_status:
                stat.quality_statuses[quality_status] += 1
    for feedback in feedback_entries:
        rating = str(feedback.rating or "").strip()
        for source in feedback.sources():
            stat = _source_stat(source_stats, source)
            if not stat:
                continue
            stat.add_feedback(rating)
            stat.add_score(_source_score(source), low_score_threshold)
    return source_stats


def _audit_sources(event):
    """Return sanitized retrieval sources from one audit event."""
    explainability = event.retrieval_explainability()
    sources = explainability.get("sources") if isinstance(explainability, dict) else []
    return sources if isinstance(sources, list) else []


def _source_stat(source_stats, source):
    """Return or create telemetry stats for one source payload."""
    key = _source_key(source)
    if not key:
        return None
    if key not in source_stats:
        source_stats[key] = SourceTelemetry(
            source_type=key[0],
            source_id=key[1],
            chunk_id=key[2],
            title=_bounded_string(source.get("title"), 220),
        )
    elif not source_stats[key].title and source.get("title"):
        source_stats[key].title = _bounded_string(source.get("title"), 220)
    return source_stats[key]


def _source_key(source):
    """Return a stable source aggregation key."""
    if not isinstance(source, dict):
        return None
    source_type = _bounded_string(source.get("type") or "knowledge", 80)
    source_id = _optional_int(source.get("id"))
    chunk_id = _optional_int(source.get("chunk_id"))
    if source_id is None and chunk_id is None:
        return None
    return source_type, source_id, chunk_id


def _source_score(source):
    """Return the most specific score available on a source payload."""
    if not isinstance(source, dict):
        return None
    explainability = source.get("explainability")
    if isinstance(explainability, dict) and explainability.get("final_score") is not None:
        return explainability.get("final_score")
    return source.get("score")


def _source_quality_status(source):
    """Return source quality status from explainability or direct metadata."""
    if not isinstance(source, dict):
        return ""
    explainability = source.get("explainability")
    if isinstance(explainability, dict) and explainability.get("quality_status"):
        return _bounded_string(explainability.get("quality_status"), 80)
    return _bounded_string(source.get("quality_status"), 80)


def _source_usage_summary(source_stats, limit):
    """Return frequently used source telemetry."""
    sources = sorted(
        source_stats.values(),
        key=lambda stat: (
            stat.audit_uses,
            stat.feedback_count,
            stat.score_count,
        ),
        reverse=True,
    )
    return {
        "used_source_count": sum(1 for stat in sources if stat.audit_uses > 0),
        "referenced_source_count": len(sources),
        "top_sources": [stat.to_dict() for stat in sources[:limit] if stat.audit_uses > 0],
    }


def _poor_source_summary(source_stats, limit):
    """Return source telemetry that suggests poor retrieval quality."""
    poor_sources = [
        stat
        for stat in source_stats.values()
        if stat.not_helpful_feedback > 0 or stat.low_score_uses > 0
    ]
    poor_sources.sort(
        key=lambda stat: (
            stat.not_helpful_feedback,
            stat.negative_rate,
            stat.low_score_uses,
            stat.audit_uses,
        ),
        reverse=True,
    )
    return [stat.to_dict() for stat in poor_sources[:limit]]


def _unsuccessful_question_summary(events):
    """Return prompt-free signals for retrieval misses and weak answers."""
    low_confidence_threshold = _low_confidence_score()
    no_source_events = [event for event in events if int(event.source_count or 0) == 0]
    low_confidence_events = [
        event
        for event in events
        if event.confidence_score is not None
        and int(event.confidence_score) <= low_confidence_threshold
    ]
    error_events = [event for event in events if _is_error_event(event)]
    return {
        "no_source_events": len(no_source_events),
        "low_confidence_events": len(low_confidence_events),
        "error_events": len(error_events),
        "low_confidence_threshold": low_confidence_threshold,
        "by_workflow": dict(Counter(str(event.workflow or "") for event in no_source_events)),
        "by_status": dict(Counter(str(event.status or "") for event in no_source_events)),
        "by_error_category": dict(
            Counter(event.error_category for event in error_events if event.error_category)
        ),
        "latest": [_event_reference(event) for event in no_source_events[:10]],
    }


def _knowledge_gap_summary(since, limit):
    """Return frequently recurring knowledge gaps without exposing question text."""
    window_gaps = (
        KnowledgeGap.query.filter(KnowledgeGap.last_seen_at >= since)
        .order_by(
            KnowledgeGap.occurrence_count.desc(),
            KnowledgeGap.last_seen_at.desc(),
            KnowledgeGap.id.desc(),
        )
        .all()
    )
    open_total = KnowledgeGap.query.filter(KnowledgeGap.status == "open").count()
    return {
        "open_total": open_total,
        "window_total": len(window_gaps),
        "top_gaps": [_gap_payload(gap) for gap in window_gaps[:limit]],
    }


def _negative_feedback_summary(feedback_entries, limit):
    """Return answer-level negative feedback metadata without prompts or answers."""
    negative_feedback = [
        feedback for feedback in feedback_entries if feedback.rating in NEGATIVE_RATINGS
    ]
    return {
        "total": len(negative_feedback),
        "with_sources": sum(1 for item in negative_feedback if item.source_count > 0),
        "without_sources": sum(1 for item in negative_feedback if item.source_count == 0),
        "by_response_type": dict(
            Counter(str(item.response_type or "") for item in negative_feedback),
        ),
        "latest": [
            _feedback_reference(feedback)
            for feedback in negative_feedback[:limit]
        ],
    }


def _unused_chunk_summary(used_chunk_ids, limit):
    """Return indexed chunks with no telemetry reference in the selected window."""
    chunks = (
        KnowledgeChunk.query.join(KnowledgeDocument)
        .filter(KnowledgeDocument.status == "indexed")
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeChunk.id.asc())
        .all()
    )
    unused_chunks = [chunk for chunk in chunks if chunk.id not in used_chunk_ids]
    return {
        "total": len(unused_chunks),
        "referenced_chunk_count": len(used_chunk_ids),
        "sample": [_chunk_payload(chunk) for chunk in unused_chunks[:limit]],
    }


def _used_chunk_ids(source_stats):
    """Return chunk ids referenced by retrieval or feedback telemetry."""
    return {
        stat.chunk_id
        for stat in source_stats.values()
        if stat.source_type == "knowledge" and stat.chunk_id is not None
    }


def _event_overview(events):
    """Return aggregate retrieval event coverage."""
    with_sources = sum(1 for event in events if int(event.source_count or 0) > 0)
    total_sources = sum(int(event.source_count or 0) for event in events)
    return {
        "total": len(events),
        "with_sources": with_sources,
        "without_sources": len(events) - with_sources,
        "source_count": total_sources,
        "average_sources": round(total_sources / len(events), 2) if events else 0,
    }


def _event_reference(event):
    """Return metadata-only event reference for admin drill-down."""
    return {
        "id": event.id,
        "workflow": event.workflow,
        "status": event.status,
        "source_count": event.source_count,
        "confidence_score": event.confidence_score,
        "confidence_level": event.confidence_level,
        "error_category": event.error_category,
        "created_at": event.created_at.isoformat(),
    }


def _feedback_reference(feedback):
    """Return metadata-only feedback reference for admin drill-down."""
    return {
        "id": feedback.id,
        "chat_message_id": feedback.chat_message_id,
        "audit_event_id": feedback.audit_event_id,
        "response_type": feedback.response_type,
        "source_count": feedback.source_count,
        "review_status": feedback.review_status,
        "created_at": feedback.created_at.isoformat(),
    }


def _gap_payload(gap):
    """Return a content-safe knowledge-gap analytics payload."""
    return {
        "id": gap.id,
        "question_hash": gap.question_hash,
        "status": gap.status,
        "occurrence_count": gap.occurrence_count,
        "machine": gap.machine,
        "department": gap.department,
        "audit_event_id": gap.audit_event_id,
        "last_seen_at": gap.last_seen_at.isoformat(),
    }


def _chunk_payload(chunk):
    """Return a content-safe unused chunk payload."""
    document = chunk.document
    return {
        "chunk_id": chunk.id,
        "document_id": chunk.document_id,
        "chunk_index": chunk.chunk_index,
        "document_title": _bounded_string(getattr(document, "title", ""), 220),
        "source_type": getattr(document, "source_type", ""),
        "quality_status": getattr(document, "quality_status", ""),
        "document_status": getattr(document, "status", ""),
        "updated_at": document.updated_at.isoformat() if document and document.updated_at else None,
    }


def _source_title(stat):
    """Return a source title from telemetry or current knowledge metadata."""
    if stat.title:
        return stat.title
    if stat.source_type != "knowledge" or stat.source_id is None:
        return ""
    document = db_get_knowledge_document(stat.source_id)
    return _bounded_string(getattr(document, "title", ""), 220)


def db_get_knowledge_document(document_id):
    """Return a knowledge document by id without raising for missing rows."""
    try:
        return db.session.get(KnowledgeDocument, int(document_id))
    except (TypeError, ValueError):
        return None


def _is_error_event(event):
    """Return whether an audit event represents an unsuccessful AI execution."""
    status = str(event.status or "").lower()
    return bool(event.error_category) or "error" in status or "failed" in status


def _counter_payload(counter, limit=5):
    """Return a sorted counter payload."""
    return [{"key": key, "count": count} for key, count in counter.most_common(limit)]


def _window_days(value):
    """Return a bounded telemetry window in days."""
    default = _config_int("RETRIEVAL_TELEMETRY_WINDOW_DAYS", DEFAULT_WINDOW_DAYS)
    return _bounded_int(value, default=default, minimum=1, maximum=365)


def _limit(value):
    """Return a bounded result limit."""
    default = _config_int("RETRIEVAL_TELEMETRY_LIMIT", DEFAULT_LIMIT)
    return _bounded_int(value, default=default, minimum=1, maximum=MAX_LIMIT)


def _low_confidence_score():
    """Return the low-confidence threshold used for unsuccessful question telemetry."""
    return _bounded_int(
        _config_int(
            "RETRIEVAL_TELEMETRY_LOW_CONFIDENCE_SCORE",
            DEFAULT_LOW_CONFIDENCE_SCORE,
        ),
        default=DEFAULT_LOW_CONFIDENCE_SCORE,
        minimum=0,
        maximum=100,
    )


def _low_source_score():
    """Return the low-source-score threshold used for poor source telemetry."""
    return _config_float("RETRIEVAL_TELEMETRY_LOW_SOURCE_SCORE", DEFAULT_LOW_SOURCE_SCORE)


def _config_int(name, default):
    """Return an integer config value."""
    value = current_app.config.get(name, default) if has_app_context() else default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _config_float(name, default):
    """Return a float config value."""
    value = current_app.config.get(name, default) if has_app_context() else default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _bounded_int(value, default, minimum, maximum):
    """Return an integer clamped to a closed range."""
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, parsed))


def _json_list(value):
    """Return a JSON-list database value as a list of strings."""
    try:
        parsed = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    if not isinstance(parsed, list):
        return []
    return [str(item) for item in parsed if item not in (None, "")]


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _optional_float(value):
    """Return an optional float value."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _bounded_string(value, max_length):
    """Return a stripped string bounded for public analytics payloads."""
    return str(value or "").strip()[:max_length]
