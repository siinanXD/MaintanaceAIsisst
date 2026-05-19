"""Safe explainability metadata for retrieval sources and audit review."""

from __future__ import annotations

import json

EXPLAINABILITY_FIELDS = (
    "semantic_similarity",
    "lexical_score",
    "lexical_similarity",
    "machine_match",
    "quality_status",
    "quality_influence",
    "feedback_influence",
    "feedback_score",
    "recency_influence",
    "recency_score",
    "aging_influence",
    "aging_multiplier",
    "aging_age_days",
    "aging_unconfirmed_days",
    "aging_reason",
)
NON_NUMERIC_EXPLAINABILITY_FIELDS = {"quality_status", "aging_reason"}
MAX_AUDIT_SOURCES = 8


def explainability_from_metadata(metadata, final_score=0):
    """Return safe per-source explainability metadata from vector-store scoring data."""
    metadata = metadata or {}
    score_debug = metadata.get("score_debug") or {}
    components = _mapping(metadata.get("score_components") or score_debug.get("components"))
    signals = _mapping(metadata.get("score_signals") or score_debug.get("signals"))
    quality_status = (
        metadata.get("quality_status")
        or signals.get("quality_status")
        or ""
    )
    return {
        "semantic_similarity": _rounded_float(signals.get("semantic_similarity"), 4),
        "lexical_score": _rounded_float(components.get("lexical"), 2),
        "lexical_similarity": _rounded_float(signals.get("lexical_similarity"), 4),
        "machine_match": _rounded_float(signals.get("machine_match"), 4),
        "machine_match_reasons": _string_list(signals.get("machine_match_reasons")),
        "quality_status": str(quality_status or ""),
        "quality_influence": _rounded_float(components.get("quality"), 2),
        "feedback_influence": _rounded_float(components.get("feedback"), 2),
        "feedback_score": _rounded_float(signals.get("feedback"), 4),
        "feedback_count": _int_value(signals.get("feedback_count")),
        "recency_influence": _rounded_float(components.get("recency"), 2),
        "recency_score": _rounded_float(signals.get("recency"), 4),
        "aging_influence": _rounded_float(components.get("aging"), 2),
        "aging_multiplier": _rounded_float(signals.get("aging_multiplier", 1.0), 4),
        "aging_age_days": _int_value(signals.get("aging_age_days")),
        "aging_unconfirmed_days": _int_value(signals.get("aging_unconfirmed_days")),
        "aging_reason": str(signals.get("aging_reason") or ""),
        "final_score": _rounded_float(final_score, 2),
    }


def explainability_from_source(source):
    """Return normalized explainability metadata from a public source payload."""
    if not isinstance(source, dict):
        return {}
    explainability = source.get("explainability")
    if isinstance(explainability, dict):
        return _normalize_explainability(explainability)
    return _normalize_explainability(source)


def retrieval_explainability_summary(sources):
    """Return a prompt-free retrieval explainability summary for diagnostics and audit."""
    safe_sources = [source for source in sources or [] if isinstance(source, dict)]
    explained_sources = [
        source for source in safe_sources if source.get("explainability")
    ]
    explainability_items = [
        explainability_from_source(source)
        for source in explained_sources
    ]
    return {
        "source_count": len(safe_sources),
        "explained_source_count": len(explained_sources),
        "averages": _average_explainability(explainability_items),
        "quality_status_counts": _quality_status_counts(explainability_items),
        "machine_match_count": sum(
            1 for item in explainability_items if item.get("machine_match", 0) > 0
        ),
        "feedback_influenced_count": sum(
            1 for item in explainability_items if item.get("feedback_influence", 0) != 0
        ),
        "recency_influenced_count": sum(
            1 for item in explainability_items if item.get("recency_influence", 0) > 0
        ),
        "sources": [
            _audit_source_explainability(source)
            for source in explained_sources[:MAX_AUDIT_SOURCES]
        ],
    }


def sanitize_audit_explainability(value):
    """Return prompt-free explainability metadata safe for AIAuditEvent storage."""
    if not isinstance(value, dict):
        return retrieval_explainability_summary([])
    payload = {
        "source_count": _int_value(value.get("source_count")),
        "explained_source_count": _int_value(value.get("explained_source_count")),
        "averages": _average_payload(value.get("averages")),
        "quality_status_counts": _string_int_mapping(value.get("quality_status_counts")),
        "machine_match_count": _int_value(value.get("machine_match_count")),
        "feedback_influenced_count": _int_value(value.get("feedback_influenced_count")),
        "recency_influenced_count": _int_value(value.get("recency_influenced_count")),
        "sources": [
            _sanitize_audit_source(source)
            for source in _list_value(value.get("sources"))[:MAX_AUDIT_SOURCES]
        ],
    }
    if "query_understanding" in value:
        payload["query_understanding"] = _sanitize_query_understanding(
            value.get("query_understanding"),
        )
    if "safety" in value:
        payload["safety"] = _sanitize_safety(value.get("safety"))
    if "post_generation_safety" in value:
        payload["post_generation_safety"] = _sanitize_post_generation_safety(
            value.get("post_generation_safety"),
        )
    if "conflicts" in value:
        payload["conflicts"] = _sanitize_conflicts(value.get("conflicts"))
    if "context_builder" in value:
        payload["context_builder"] = _sanitize_context_builder(value.get("context_builder"))
    if "knowledge_links" in value:
        payload["knowledge_links"] = _sanitize_knowledge_links(value.get("knowledge_links"))
    if "retrieval_duration_ms" in value:
        payload["retrieval_duration_ms"] = _int_value(value.get("retrieval_duration_ms"))
    return payload


def explainability_to_json(value):
    """Serialize sanitized audit explainability as compact JSON."""
    return json.dumps(
        sanitize_audit_explainability(value),
        ensure_ascii=True,
        sort_keys=True,
    )


def explainability_from_json(raw_value):
    """Deserialize sanitized audit explainability from JSON."""
    try:
        value = json.loads(raw_value or "{}")
    except (TypeError, json.JSONDecodeError):
        value = {}
    return sanitize_audit_explainability(value)


def _normalize_explainability(value):
    """Return stable explainability keys from a source or existing payload."""
    if not isinstance(value, dict):
        return {}
    return {
        "semantic_similarity": _rounded_float(value.get("semantic_similarity"), 4),
        "lexical_score": _rounded_float(value.get("lexical_score"), 2),
        "lexical_similarity": _rounded_float(value.get("lexical_similarity"), 4),
        "machine_match": _rounded_float(value.get("machine_match"), 4),
        "machine_match_reasons": _string_list(value.get("machine_match_reasons")),
        "quality_status": str(value.get("quality_status") or ""),
        "quality_influence": _rounded_float(value.get("quality_influence"), 2),
        "feedback_influence": _rounded_float(value.get("feedback_influence"), 2),
        "feedback_score": _rounded_float(value.get("feedback_score"), 4),
        "feedback_count": _int_value(value.get("feedback_count")),
        "recency_influence": _rounded_float(value.get("recency_influence"), 2),
        "recency_score": _rounded_float(value.get("recency_score"), 4),
        "aging_influence": _rounded_float(value.get("aging_influence"), 2),
        "aging_multiplier": _rounded_float(value.get("aging_multiplier", 1.0), 4),
        "aging_age_days": _int_value(value.get("aging_age_days")),
        "aging_unconfirmed_days": _int_value(value.get("aging_unconfirmed_days")),
        "aging_reason": str(value.get("aging_reason") or ""),
        "final_score": _rounded_float(value.get("final_score"), 2),
    }


def _average_explainability(items):
    """Return averages for numeric explainability fields."""
    if not items:
        return {
            field: 0
            for field in EXPLAINABILITY_FIELDS
            if field not in NON_NUMERIC_EXPLAINABILITY_FIELDS
        }
    averages = {}
    for field in EXPLAINABILITY_FIELDS:
        if field in NON_NUMERIC_EXPLAINABILITY_FIELDS:
            continue
        values = [_float_value(item.get(field), 0.0) for item in items]
        averages[field] = round(sum(values) / len(values), 4)
    return averages


def _quality_status_counts(items):
    """Return quality status counts for explained sources."""
    counts = {}
    for item in items:
        status = str(item.get("quality_status") or "unknown")
        counts[status] = counts.get(status, 0) + 1
    return counts


def _audit_source_explainability(source):
    """Return source IDs and explainability without text, title, prompt, or answer."""
    explainability = explainability_from_source(source)
    return {
        "type": str(source.get("type") or "")[:80],
        "id": _optional_int(source.get("id")),
        "chunk_id": _optional_int(source.get("chunk_id")),
        "score": _rounded_float(source.get("score"), 2),
        "explainability": explainability,
    }


def _sanitize_audit_source(source):
    """Return one sanitized audit source explainability item."""
    if not isinstance(source, dict):
        return {}
    return {
        "type": str(source.get("type") or "")[:80],
        "id": _optional_int(source.get("id")),
        "chunk_id": _optional_int(source.get("chunk_id")),
        "score": _rounded_float(source.get("score"), 2),
        "explainability": _normalize_explainability(source.get("explainability")),
    }


def _sanitize_query_understanding(value):
    """Return safe query-understanding metadata for audit storage."""
    if not isinstance(value, dict):
        return {}
    return {
        "query_type": str(value.get("query_type") or "")[:80],
        "confidence": _rounded_float(value.get("confidence"), 4),
        "is_safety": bool(value.get("is_safety")),
        "secondary_types": _string_list(value.get("secondary_types")),
        "signals": _string_list(value.get("signals")),
        "recommended_scopes": _string_list(value.get("recommended_scopes")),
        "retrieval_strategy": _safe_strategy(value.get("retrieval_strategy")),
        "provider": str(value.get("provider") or "")[:80],
    }


def _sanitize_safety(value):
    """Return safe safety metadata for audit storage."""
    if not isinstance(value, dict):
        return {}
    return {
        "safety_relevant": bool(value.get("safety_relevant")),
        "risk_level": str(value.get("risk_level") or "")[:80],
        "categories": _string_list(value.get("categories")),
        "warnings": _string_list(value.get("warnings")),
        "blocked_actions": _string_list(value.get("blocked_actions")),
        "signals": _string_list(value.get("signals")),
    }


def _sanitize_post_generation_safety(value):
    """Return safe final-answer safety metadata for audit storage."""
    if not isinstance(value, dict):
        return {}
    payload = _sanitize_safety(value)
    payload.update(
        {
            "action": str(value.get("action") or "")[:80],
            "modified": bool(value.get("modified")),
            "confidence_penalty": _int_value(value.get("confidence_penalty")),
        }
    )
    return payload


def _sanitize_conflicts(value):
    """Return source-conflict metadata without sensitive content."""
    if not isinstance(value, dict):
        return {}
    conflicts = []
    for conflict in _list_value(value.get("conflicts"))[:8]:
        if not isinstance(conflict, dict):
            continue
        conflicts.append(
            {
                "type": str(conflict.get("type") or "")[:80],
                "reason": str(conflict.get("reason") or "")[:220],
                "signals": _string_list(conflict.get("signals")),
                "sources": [
                    _sanitize_conflict_source(source)
                    for source in _list_value(conflict.get("sources"))[:5]
                ],
            }
        )
    return {
        "has_conflicts": bool(value.get("has_conflicts")),
        "count": _int_value(value.get("count")),
        "summary": str(value.get("summary") or "")[:220],
        "conflicts": conflicts,
    }


def _sanitize_context_builder(value):
    """Return context-builder diagnostics without context text."""
    if not isinstance(value, dict):
        return {}
    return {
        "sections": [
            {
                "key": str(section.get("key") or "")[:80],
                "title": str(section.get("title") or "")[:120],
                "priority": _int_value(section.get("priority")),
                "source_count": _int_value(section.get("source_count")),
                "chars": _int_value(section.get("chars")),
            }
            for section in _list_value(value.get("sections"))[:12]
            if isinstance(section, dict)
        ],
        "stats": _mapping(value.get("stats")),
        "explainability": _mapping(value.get("explainability")),
    }


def _sanitize_knowledge_links(value):
    """Return linked-source metadata without chunk content."""
    if not isinstance(value, dict):
        return {}
    links = []
    for link in _list_value(value.get("links"))[:12]:
        if not isinstance(link, dict):
            continue
        links.append(
            {
                "type": str(link.get("type") or "")[:80],
                "id": _optional_int(link.get("id")),
                "source_type": str(link.get("source_type") or "")[:80],
                "source_id": _optional_int(link.get("source_id")),
                "quality_status": str(link.get("quality_status") or "")[:80],
                "score": _int_value(link.get("score")),
                "reasons": _string_list(link.get("reasons")),
            }
        )
    return {
        "links": links,
        "source_document_ids": [
            _optional_int(item)
            for item in _list_value(value.get("source_document_ids"))[:12]
        ],
    }


def _sanitize_conflict_source(source):
    """Return a safe conflict source reference."""
    if not isinstance(source, dict):
        return {}
    return {
        "type": str(source.get("type") or "")[:80],
        "id": _optional_int(source.get("id")),
        "chunk_id": _optional_int(source.get("chunk_id")),
        "score": _rounded_float(source.get("score"), 2),
        "quality_status": str(source.get("quality_status") or "")[:80],
    }


def _safe_strategy(value):
    """Return safe retrieval-strategy metadata."""
    if not isinstance(value, dict):
        return {}
    return {
        "top_k": _int_value(value.get("top_k")),
        "source_types": _string_list(value.get("source_types")),
        "scope_weights": _mapping(value.get("scope_weights")),
        "prompt_rules": _string_list(value.get("prompt_rules")),
        "prefer_structured": bool(value.get("prefer_structured")),
        "prefer_confirmed": bool(value.get("prefer_confirmed")),
    }


def _average_payload(value):
    """Return sanitized average explainability fields."""
    if not isinstance(value, dict):
        return _average_explainability([])
    return {
        field: _rounded_float(value.get(field), 4)
        for field in EXPLAINABILITY_FIELDS
        if field not in NON_NUMERIC_EXPLAINABILITY_FIELDS
    }


def _string_int_mapping(value):
    """Return a string-to-int mapping."""
    if not isinstance(value, dict):
        return {}
    return {str(key)[:80]: _int_value(item) for key, item in value.items()}


def _mapping(value):
    """Return value when it is a dictionary, otherwise an empty dictionary."""
    return value if isinstance(value, dict) else {}


def _list_value(value):
    """Return value when it is a list, otherwise an empty list."""
    return value if isinstance(value, list) else []


def _string_list(value):
    """Return a bounded list of strings."""
    if not isinstance(value, list | tuple | set):
        return []
    return [str(item)[:80] for item in value if item not in (None, "")][:8]


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _int_value(value):
    """Return a safe integer value."""
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rounded_float(value, digits):
    """Return a rounded safe float value."""
    return round(_float_value(value, 0.0), digits)


def _float_value(value, default):
    """Return a safe float value."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
