"""Prompt-safe retrieval debug counters for AI/RAG diagnostics."""

from dataclasses import dataclass, field

from flask import current_app, has_app_context

COUNT_FIELDS = (
    "sql_candidates_found",
    "keyword_candidates_found",
    "vector_candidates_found",
    "permission_filtered",
    "quality_filtered",
    "score_filtered",
    "score_anchor_filtered",
    "final_visible_sources",
    "sql_keyword_fallback_candidates_found",
)
SENSITIVE_MAPPING_KEYS = {
    "answer",
    "chunk_text",
    "content",
    "message",
    "prompt",
    "query",
    "source_text",
    "text",
    "title",
    "user_question",
}


@dataclass
class RetrievalDebugCounters:
    """Store prompt-safe counters for one retrieval request."""

    sql_candidates_found: int = 0
    keyword_candidates_found: int = 0
    vector_candidates_found: int = 0
    permission_filtered: int = 0
    quality_filtered: int = 0
    score_filtered: int = 0
    score_anchor_filtered: int = 0
    final_visible_sources: int = 0
    sql_keyword_fallback_candidates_found: int = 0
    sql_keyword_fallback_used: bool = False
    sql_keyword_fallback_by_type: dict = field(default_factory=dict)
    query_classification_type: str = ""
    query_classification_sources: list[str] = field(default_factory=list)
    rag_enabled: bool = True
    vector_store: str = ""
    filters: dict = field(default_factory=dict)
    top_k: int | None = None
    source_types: dict = field(default_factory=dict)
    duration_ms: int = 0
    decision_trace: list[dict] = field(default_factory=list)

    def to_dict(self):
        """Return a JSON-safe dictionary without prompts or source text."""
        score_anchor_filtered = _safe_int(self.score_anchor_filtered or self.score_filtered)
        return {
            "sql_candidates_found": _safe_int(self.sql_candidates_found),
            "keyword_candidates_found": _safe_int(self.keyword_candidates_found),
            "vector_candidates_found": _safe_int(self.vector_candidates_found),
            "permission_filtered": _safe_int(self.permission_filtered),
            "quality_filtered": _safe_int(self.quality_filtered),
            "score_filtered": _safe_int(self.score_filtered),
            "score_anchor_filtered": score_anchor_filtered,
            "final_visible_sources": _safe_int(self.final_visible_sources),
            "sql_keyword_fallback_candidates_found": _safe_int(
                self.sql_keyword_fallback_candidates_found
            ),
            "sql_keyword_fallback_used": bool(self.sql_keyword_fallback_used),
            "sql_keyword_fallback_by_type": _safe_mapping(self.sql_keyword_fallback_by_type),
            "query_classification_type": str(self.query_classification_type or ""),
            "query_classification_sources": [
                str(source) for source in self.query_classification_sources[:12]
            ],
            "rag_enabled": bool(self.rag_enabled),
            "vector_store": str(self.vector_store or ""),
            "filters": _safe_mapping(self.filters),
            "top_k": _safe_optional_int(self.top_k),
            "source_types": _safe_mapping(self.source_types),
            "duration_ms": _safe_int(self.duration_ms),
            "candidate_counts": {
                "sql": _safe_int(self.sql_candidates_found),
                "keyword": _safe_int(self.keyword_candidates_found),
                "vector": _safe_int(self.vector_candidates_found),
                "sql_keyword_fallback": _safe_int(self.sql_keyword_fallback_candidates_found),
            },
            "filtered_by": {
                "permissions": _safe_int(self.permission_filtered),
                "quality": _safe_int(self.quality_filtered),
                "score_anchor": score_anchor_filtered,
            },
            "decision_trace": _safe_decisions(self.decision_trace),
        }


def empty_retrieval_debug(**overrides):
    """Return an empty debug counter set with optional metadata overrides."""
    counters = RetrievalDebugCounters()
    for key, value in overrides.items():
        if hasattr(counters, key):
            setattr(counters, key, value)
    return counters.to_dict()


def merge_retrieval_debug(*items, **overrides):
    """Merge prompt-safe retrieval debug dictionaries without changing behavior."""
    counters = RetrievalDebugCounters()
    for item in items:
        payload = _counter_mapping(item)
        for field_name in COUNT_FIELDS:
            setattr(
                counters,
                field_name,
                getattr(counters, field_name) + _safe_int(payload.get(field_name)),
            )
        for field_name in (
            "sql_keyword_fallback_used",
            "sql_keyword_fallback_by_type",
            "query_classification_type",
            "query_classification_sources",
            "rag_enabled",
            "vector_store",
            "filters",
            "top_k",
            "source_types",
            "decision_trace",
        ):
            value = payload.get(field_name)
            if field_name == "sql_keyword_fallback_used":
                counters.sql_keyword_fallback_used = counters.sql_keyword_fallback_used or bool(
                    value
                )
                continue
            if field_name == "sql_keyword_fallback_by_type" and isinstance(value, dict):
                counters.sql_keyword_fallback_by_type = _merge_count_maps(
                    counters.sql_keyword_fallback_by_type,
                    value,
                )
                continue
            if field_name == "query_classification_sources" and isinstance(value, list):
                counters.query_classification_sources = list(
                    dict.fromkeys([*counters.query_classification_sources, *value])
                )[:12]
                continue
            if field_name == "decision_trace" and isinstance(value, list):
                counters.decision_trace = _safe_decisions([*counters.decision_trace, *value])
                continue
            if value not in (None, "", {}):
                setattr(counters, field_name, value)
        counters.duration_ms = max(counters.duration_ms, _safe_int(payload.get("duration_ms")))

    for key, value in overrides.items():
        if hasattr(counters, key):
            setattr(counters, key, value)
    return counters.to_dict()


def retrieval_debug_decision(step, status, reason, metrics=None):
    """Return one prompt-safe retrieval decision trace entry."""
    return _safe_decision(
        {
            "step": step,
            "status": status,
            "reason": reason,
            "metrics": metrics or {},
        }
    )


def public_retrieval_debug(debug_payload):
    """Return sanitized retrieval debug data for API diagnostics."""
    return merge_retrieval_debug(debug_payload)


def is_retrieval_debug_visible(user):
    """Return whether retrieval debug data may be exposed to this request."""
    if bool(getattr(user, "is_admin", False)):
        return True
    if not has_app_context():
        return False
    return bool(
        current_app.debug
        or current_app.testing
        or str(current_app.config.get("ENV", "")).lower() == "development"
        or str(current_app.config.get("FLASK_ENV", "")).lower() == "development"
    )


def _counter_mapping(value):
    """Return a dictionary for a supported counter payload."""
    if isinstance(value, RetrievalDebugCounters):
        return value.to_dict()
    if isinstance(value, dict):
        return value
    return {}


def _safe_int(value):
    """Return a non-negative integer for debug counters."""
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _safe_optional_int(value):
    """Return an integer or None for optional debug metadata."""
    if value in (None, ""):
        return None
    return _safe_int(value)


def _safe_mapping(value):
    """Return a shallow JSON-safe mapping without sensitive text payloads."""
    if not isinstance(value, dict):
        return {}
    safe = {}
    for key, item in value.items():
        if str(key).strip().lower() in SENSITIVE_MAPPING_KEYS:
            continue
        if isinstance(item, bool):
            safe[str(key)] = item
        elif isinstance(item, int | float):
            safe[str(key)] = item
        elif item is None:
            safe[str(key)] = None
        elif isinstance(item, dict):
            safe[str(key)] = _safe_mapping(item)
        else:
            safe[str(key)] = str(item)
    return safe


def _safe_decisions(value):
    """Return bounded prompt-safe retrieval decision entries."""
    if not isinstance(value, list):
        return []
    decisions = []
    for item in value:
        decision = _safe_decision(item)
        if decision:
            decisions.append(decision)
        if len(decisions) >= 12:
            break
    return decisions


def _safe_decision(value):
    """Return one prompt-safe decision entry without source text."""
    if not isinstance(value, dict):
        return {}
    step = _bounded_text(value.get("step"), 64)
    if not step:
        return {}
    return {
        "step": step,
        "status": _bounded_text(value.get("status"), 32),
        "reason": _bounded_text(value.get("reason"), 160),
        "metrics": _safe_mapping(value.get("metrics") or {}),
    }


def _bounded_text(value, max_length):
    """Return compact bounded text for debug metadata."""
    text = " ".join(str(value or "").strip().split())
    return text[:max_length]


def _merge_count_maps(left, right):
    """Return count-like mappings merged by key."""
    merged = dict(left or {})
    for key, value in (right or {}).items():
        merged[str(key)] = _safe_int(merged.get(str(key))) + _safe_int(value)
    return merged
