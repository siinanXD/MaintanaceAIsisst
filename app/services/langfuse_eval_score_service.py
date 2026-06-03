"""Langfuse evaluation scores for automatic quality signals and user feedback."""

from __future__ import annotations

import logging

from app.services.langfuse_service import (
    attach_langfuse_eval_io,
    langfuse_eval_capture_io_enabled,
    langfuse_eval_enabled,
    langfuse_is_ready,
    submit_langfuse_scores,
)

logger = logging.getLogger(__name__)

USER_FEEDBACK_NUMERIC = {
    "helpful": 1.0,
    "not_helpful": 0.0,
    "partially_helpful": 0.5,
}
MAX_FEEDBACK_COMMENT_CHARS = 200


def submit_automatic_eval_scores(diagnostics, result):
    """Push rule-based evaluation scores to Langfuse for one AI answer."""
    if not langfuse_eval_enabled():
        return 0

    trace_id = _trace_id_from_diagnostics(diagnostics)
    if not trace_id:
        return 0

    safe_diagnostics = diagnostics if isinstance(diagnostics, dict) else {}
    safe_result = result if isinstance(result, dict) else {}
    answer_quality = safe_result.get("answer_quality") or {}
    if not isinstance(answer_quality, dict):
        answer_quality = {}

    scores = _dedupe_scores(
        _hallucination_scores(safe_diagnostics, answer_quality)
        + _retrieval_quality_scores(safe_diagnostics, safe_result)
        + _baseline_quality_scores(safe_diagnostics, answer_quality, safe_result)
    )

    submitted = submit_langfuse_scores(
        trace_id,
        scores,
        observation_id=_observation_id_from_diagnostics(safe_diagnostics),
    )
    if submitted and langfuse_eval_capture_io_enabled():
        attach_langfuse_eval_io(
            trace_id=trace_id,
            diagnostics=safe_diagnostics,
            result=safe_result,
            observation_id=_observation_id_from_diagnostics(safe_diagnostics),
        )
    return submitted


def submit_user_feedback_score(chat_message, feedback_entry):
    """Attach user feedback ratings as Langfuse scores on the linked trace."""
    if not langfuse_is_ready() or chat_message is None or feedback_entry is None:
        return False

    trace_id = _trace_id_from_diagnostics(chat_message.diagnostics())
    if not trace_id:
        return False

    rating = str(getattr(feedback_entry, "rating", "") or "").strip()
    numeric_value = USER_FEEDBACK_NUMERIC.get(rating)
    if numeric_value is None:
        return False

    comment = _safe_feedback_comment(getattr(feedback_entry, "comment", ""))
    scores = [
        {
            "name": "user-feedback",
            "value": float(numeric_value),
            "data_type": "NUMERIC",
            "comment": comment,
        },
        {
            "name": "user-feedback-rating",
            "value": rating,
            "data_type": "CATEGORICAL",
            "comment": comment,
        },
    ]
    return submit_langfuse_scores(trace_id, scores) > 0


def _hallucination_scores(diagnostics, answer_quality):
    """Return hallucination-related Langfuse scores."""
    scores = [
        _boolean_score(
            "hallucination-risk",
            bool(diagnostics.get("hallucination_warning")),
        ),
        _boolean_score("empty-retrieval", bool(diagnostics.get("empty_retrieval"))),
        _boolean_score("no-answer", bool(answer_quality.get("no_answer"))),
    ]
    return scores


def _retrieval_quality_scores(diagnostics, result):
    """Return retrieval-quality Langfuse scores without chunk text."""
    explainability = diagnostics.get("retrieval_explainability") or {}
    if not isinstance(explainability, dict):
        explainability = {}

    averages = explainability.get("averages") or {}
    if not isinstance(averages, dict):
        averages = {}

    source_count = _optional_int(
        explainability.get("source_count"),
        default=len(result.get("sources") or []),
    )
    scores = [
        _numeric_score("retrieval-source-count", float(source_count)),
        _numeric_score(
            "retrieval-explained-count",
            float(_optional_int(explainability.get("explained_source_count"))),
        ),
        _numeric_score("retrieval-avg-final-score", _optional_float(averages.get("final_score"))),
        _numeric_score(
            "retrieval-avg-semantic-similarity",
            _optional_float(averages.get("semantic_similarity")),
        ),
        _numeric_score(
            "retrieval-duration-ms",
            float(_optional_int(diagnostics.get("retrieval_duration_ms"))),
        ),
        _numeric_score(
            "retrieval-machine-match-count",
            float(_optional_int(explainability.get("machine_match_count"))),
        ),
        _boolean_score("retrieval-used", bool(diagnostics.get("retrieval_used"))),
    ]

    source_conflicts = diagnostics.get("source_conflicts") or {}
    if isinstance(source_conflicts, dict):
        scores.append(
            _boolean_score(
                "source-conflict",
                bool(source_conflicts.get("has_conflicts")),
            )
        )
    return scores


def _baseline_quality_scores(diagnostics, answer_quality, result):
    """Return compact baseline quality scores shared across workflows."""
    scores = []

    status = str(answer_quality.get("status") or "").strip()
    if status:
        scores.append(
            {
                "name": "answer-quality",
                "value": status,
                "data_type": "CATEGORICAL",
            }
        )

    confidence = result.get("confidence") or diagnostics.get("confidence") or {}
    if not isinstance(confidence, dict):
        confidence = {}
    confidence_score = _optional_int(
        confidence.get("score") or diagnostics.get("confidence_score"),
        default=None,
    )
    if confidence_score is not None:
        scores.append(
            _numeric_score("confidence", round(confidence_score / 100.0, 4)),
        )
    return scores


def _dedupe_scores(scores):
    """Return scores deduplicated by name while preserving the last value."""
    deduped = {}
    for score in scores:
        if isinstance(score, dict) and score.get("name"):
            deduped[score["name"]] = score
    return list(deduped.values())


def _boolean_score(name, value):
    """Return one boolean Langfuse score payload."""
    return {
        "name": name,
        "value": 1.0 if value else 0.0,
        "data_type": "BOOLEAN",
    }


def _numeric_score(name, value):
    """Return one numeric Langfuse score payload."""
    return {
        "name": name,
        "value": float(value or 0.0),
        "data_type": "NUMERIC",
    }


def _trace_id_from_diagnostics(diagnostics):
    """Return a Langfuse trace id from diagnostics when present."""
    if not isinstance(diagnostics, dict):
        return ""
    return str(diagnostics.get("langfuse_trace_id") or "").strip()


def _observation_id_from_diagnostics(diagnostics):
    """Return an optional Langfuse observation id from diagnostics."""
    if not isinstance(diagnostics, dict):
        return ""
    return str(diagnostics.get("langfuse_observation_id") or "").strip()


def _safe_feedback_comment(comment):
    """Return a short feedback comment without prompt or answer bodies."""
    text = " ".join(str(comment or "").strip().split())
    return text[:MAX_FEEDBACK_COMMENT_CHARS]


def _optional_int(value, default=0):
    """Return an integer value or a default."""
    if value in (None, ""):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value):
    """Return a float value or zero."""
    if value in (None, ""):
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
