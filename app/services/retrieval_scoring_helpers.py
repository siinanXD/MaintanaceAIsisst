"""Helper functions for hybrid retrieval scoring."""

# ruff: noqa: E402, F401, F403, F405

import logging
import re
from dataclasses import dataclass, field
from datetime import UTC

from flask import current_app, has_app_context

from app.domain_models.common import Priority, utc_now
from app.extensions import db
from app.models import (
    AIFeedback,
    AssistantTrainingEntry,
    Department,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    Machine,
    MachineManual,
    MaintenancePlan,
    Task,
)
from app.services.chunking_service import token_set
from app.services.knowledge_aging_service import retrieval_aging_signal
from app.services.knowledge_quality_service import retrieval_quality_gate_for_document

logger = logging.getLogger(__name__)

DEFAULT_SCORE_WEIGHTS = {
    "semantic": 70.0,
    "lexical": 60.0,
    "quality": 30.0,
    "recency": 15.0,
    "machine": 50.0,
    "feedback": 20.0,
    "usage": 15.0,
    "source_priority": 15.0,
}
DEFAULT_RECENCY_WINDOW_DAYS = 90
DEFAULT_FEEDBACK_SCAN_LIMIT = 300
DEFAULT_SEMANTIC_ONLY_MIN_SIMILARITY = 0.78
SOURCE_TYPE_PRIORITY = {
    "error_entry": 0.95,
    "machine_manual": 0.9,
    "maintenance_plan": 0.78,
    "manual_training": 0.72,
    "generated_document": 0.65,
    "task": 0.6,
    "machine": 0.55,
    "upload": 0.5,
    "shift_handover": 0.45,
    "inventory_material": 0.45,
}
RATING_VALUES = {
    "helpful": 1.0,
    "partially_helpful": 0.45,
    "not_helpful": -1.0,
}
MACHINE_LABEL_PATTERN = re.compile(
    r"\b(?:maschine|anlage|presse|linie|station|roboter|ofen)\s+[a-z0-9-]+",
)
ERROR_CONTEXT_PATTERN = re.compile(r"\b(?:fehler|error|code|stoerung|störung)\b")
ERROR_CODE_PATTERN = re.compile(r"\b[a-z]{1,4}[- ]?\d{2,5}\b")
GENERIC_MACHINE_SERIES_TOKENS = {"maschine", "anlage", "nr", "nummer"}
from app.services.retrieval_scoring_models import *


def _score_weights():
    """Return configured hybrid retrieval weights."""
    return {
        key: _positive_float(
            _config_value(f"RAG_SCORE_{key.upper()}_WEIGHT", default),
            default,
        )
        for key, default in DEFAULT_SCORE_WEIGHTS.items()
    }


def _lexical_similarity(query_tokens, candidate_tokens):
    """Return normalized lexical overlap for query and candidate tokens."""
    if not query_tokens or not candidate_tokens:
        return 0.0
    overlap = query_tokens & candidate_tokens
    query_coverage = len(overlap) / len(query_tokens)
    candidate_density = len(overlap) / max(len(candidate_tokens), 1)
    return _clamp(query_coverage * 0.85 + candidate_density * 0.15, 0.0, 1.0)


def _recency_signal(updated_at, window_days):
    """Return a freshness signal in the range 0 to 1."""
    if not updated_at:
        return 0.0
    age_days = max(0.0, (_utc_naive(utc_now()) - _utc_naive(updated_at)).total_seconds() / 86400)
    if window_days <= 0:
        return 0.0
    return _clamp(1.0 - (age_days / window_days), 0.0, 1.0)


def _usage_signal(success_count):
    """Return a bounded repeated-success usage signal."""
    return _clamp(float(success_count or 0) / 5.0, 0.0, 1.0)


def _feedback_source_key(source):
    """Return a feedback aggregation key for a stored source payload."""
    if not isinstance(source, dict):
        return None
    if str(source.get("type") or "") != "knowledge":
        return None
    document_id = _optional_int(source.get("id"))
    if document_id is None:
        return None
    chunk_id = _optional_int(source.get("chunk_id"))
    return ("knowledge", document_id, chunk_id)


def _increment_feedback_stats(stats, rating):
    """Return feedback stats incremented for one rating."""
    if rating == "helpful":
        return FeedbackStats(
            helpful=stats.helpful + 1,
            partially_helpful=stats.partially_helpful,
            not_helpful=stats.not_helpful,
        )
    if rating == "partially_helpful":
        return FeedbackStats(
            helpful=stats.helpful,
            partially_helpful=stats.partially_helpful + 1,
            not_helpful=stats.not_helpful,
        )
    return FeedbackStats(
        helpful=stats.helpful,
        partially_helpful=stats.partially_helpful,
        not_helpful=stats.not_helpful + 1,
    )


def _source_model(source_type):
    """Return the SQLAlchemy model used by a knowledge source type."""
    return {
        "generated_document": GeneratedDocument,
        "error_entry": ErrorEntry,
        "task": Task,
        "machine": Machine,
        "inventory_material": InventoryMaterial,
        "maintenance_plan": MaintenancePlan,
        "machine_manual": MachineManual,
        "manual_training": AssistantTrainingEntry,
    }.get(str(source_type or ""))


def _source_machine_objects(source):
    """Return machine objects directly linked to a structured source."""
    machines = []
    if isinstance(source, Machine):
        machines.append(source)
    for attr in ("machine", "machine_rel"):
        value = getattr(source, attr, None)
        if isinstance(value, Machine):
            machines.append(value)
    machine_id = getattr(source, "machine_id", None)
    if machine_id and not any(machine.id == machine_id for machine in machines):
        machine = db.session.get(Machine, int(machine_id))
        if machine:
            machines.append(machine)
    return machines


def _source_machine_labels(source):
    """Return normalized machine labels from one structured source."""
    labels = set()
    machine_value = getattr(source, "machine", None)
    if isinstance(machine_value, str):
        labels.add(_normalize_phrase(machine_value))
    for machine in _source_machine_objects(source):
        labels.add(_normalize_phrase(machine.name))
        labels.add(_normalize_phrase(machine.produced_item))
    return [label for label in labels if label]


def _source_departments(source):
    """Return normalized department or area names from one source."""
    departments = set()
    department = getattr(source, "department", None)
    if isinstance(department, str):
        departments.add(_normalize_phrase(department))
    elif department is not None:
        departments.add(_normalize_phrase(getattr(department, "name", "")))
    return {department for department in departments if department}


def _source_manufacturers(source):
    """Return normalized manufacturer names from one source."""
    manufacturer = _normalize_phrase(getattr(source, "manufacturer", ""))
    return {manufacturer} if manufacturer else set()


def _merge_machine_contexts(*contexts):
    """Return one machine context containing all values from given contexts."""
    return MachineContext(
        machine_names=frozenset().union(*(context.machine_names for context in contexts)),
        machine_ids=frozenset().union(*(context.machine_ids for context in contexts)),
        series=frozenset().union(*(context.series for context in contexts)),
        departments=frozenset().union(*(context.departments for context in contexts)),
        manufacturers=frozenset().union(*(context.manufacturers for context in contexts)),
        error_codes=frozenset().union(*(context.error_codes for context in contexts)),
    )


def _contains_any_machine_name(query_names, candidate_names):
    """Return whether any query machine label is contained in a candidate label."""
    for query_name in query_names:
        for candidate_name in candidate_names:
            if (
                query_name
                and candidate_name
                and (query_name in candidate_name or candidate_name in query_name)
            ):
                return True
    return False


def _machine_series_for_labels(labels):
    """Return normalized machine-series hints for machine labels."""
    series = set()
    for label in labels:
        series.update(_machine_series_for_label(label))
    return series


def _machine_series_for_label(label):
    """Return series hints inferred from one machine label."""
    tokens = _normalize_phrase(label).split()
    series = set()
    for token in tokens:
        if token.isdigit() or token in GENERIC_MACHINE_SERIES_TOKENS:
            continue
        alpha_numeric = re.match(r"([a-z]+)\d+", token)
        if alpha_numeric:
            series.add(alpha_numeric.group(1))
            continue
        series.add(token)
    return series


def _error_codes_from_text(text, broad=False):
    """Return normalized error codes from text."""
    normalized_text = str(text or "").lower()
    if not broad:
        prefixed = re.findall(
            r"(?:fehler|error|code|stoerung|störung)\s*[:#-]?\s*([a-z]{1,4}[- ]?\d{2,5})",
            normalized_text,
        )
        return {_normalize_error_code(code) for code in prefixed if code}
    return {
        _normalize_error_code(match)
        for match in ERROR_CODE_PATTERN.findall(normalized_text)
        if match
    }


def _normalize_error_code(value):
    """Return a compact uppercase error-code key."""
    return re.sub(r"[^A-Z0-9]+", "", str(value or "").upper())


def _error_code_similarity(left_codes, right_codes):
    """Return the strongest normalized similarity between two error-code sets."""
    best = 0.0
    for left_code in left_codes:
        for right_code in right_codes:
            best = max(best, _single_error_code_similarity(left_code, right_code))
    return best


def _error_alignment_payload(state, multiplier, query_codes, candidate_codes):
    """Return a compact error-code alignment scoring payload."""
    return {
        "state": state,
        "multiplier": _clamp(multiplier, 0.0, 1.0),
        "query_error_codes": frozenset(query_codes or ()),
        "candidate_error_codes": frozenset(candidate_codes or ()),
    }


def _single_error_code_similarity(left_code, right_code):
    """Return normalized similarity for two error-code strings."""
    if not left_code or not right_code:
        return 0.0
    if left_code == right_code:
        return 1.0
    left_prefix, left_number = _split_error_code(left_code)
    right_prefix, right_number = _split_error_code(right_code)
    if left_prefix and left_prefix == right_prefix:
        if left_number is not None and right_number is not None:
            if abs(left_number - right_number) <= 5:
                return 0.75
            left_digits = str(left_number)
            right_digits = str(right_number)
            if left_digits[:2] == right_digits[:2]:
                return 0.65
        return 0.5
    shared_prefix_length = len(_common_prefix(left_code, right_code))
    return 0.35 if shared_prefix_length >= 2 else 0.0


def _split_error_code(code):
    """Return alphabetic prefix and numeric suffix for an error code."""
    match = re.match(r"([A-Z]+)(\d+)", str(code or ""))
    if not match:
        return "", None
    return match.group(1), int(match.group(2))


def _common_prefix(left, right):
    """Return the common prefix for two strings."""
    index = 0
    while index < min(len(left), len(right)) and left[index] == right[index]:
        index += 1
    return left[:index]


def _task_priority_signal(source):
    """Return normalized priority for task-like source rows."""
    priority = getattr(source, "priority", None)
    if priority == Priority.URGENT:
        return 1.0
    if priority == Priority.SOON:
        return 0.75
    if priority == Priority.NORMAL:
        return 0.45
    return 0.4


def _severity_signal(severity):
    """Return normalized priority for severity-like values."""
    value = str(severity or "").strip().lower()
    if value in {"critical", "kritisch", "urgent", "hoch"}:
        return 1.0
    if value in {"high", "medium", "mittel"}:
        return 0.7
    if value in {"low", "niedrig"}:
        return 0.35
    return 0.5


def _criticality_signal(criticality):
    """Return normalized priority for criticality values."""
    return _severity_signal(criticality)


def _score_explanation(components, signals):
    """Return a short explainable score summary."""
    top_components = sorted(
        components.items(),
        key=lambda item: abs(item[1]),
        reverse=True,
    )[:4]
    component_text = ", ".join(f"{name}={value}" for name, value in top_components)
    return (
        f"{component_text}; quality={signals.get('quality_status')}; "
        f"aging={signals.get('aging_reason', 'fresh')}; "
        f"usage={signals.get('successful_usage_count', 0)}"
    )


def _cosine_similarity(left, right):
    """Return cosine similarity for two numeric vectors."""
    if not left or not right or len(left) != len(right):
        return 0.0
    numerator = sum(a * b for a, b in zip(left, right, strict=True))
    left_length = sum(a * a for a in left) ** 0.5
    right_length = sum(b * b for b in right) ** 0.5
    if left_length <= 0 or right_length <= 0:
        return 0.0
    return numerator / (left_length * right_length)


def _normalize_phrase(value):
    """Return a lowercase alphanumeric phrase for fuzzy metadata matching."""
    return " ".join(re.sub(r"[^a-z0-9-]+", " ", str(value or "").lower()).split())


def _utc_naive(value):
    """Return a timezone-free UTC datetime for safe arithmetic."""
    if value.tzinfo:
        return value.astimezone(UTC).replace(tzinfo=None)
    return value


def _config_value(name, default):
    """Return a Flask config value when available, otherwise a default."""
    if has_app_context():
        return current_app.config.get(name, default)
    return default


def _positive_float(value, default):
    """Return a non-negative float config value."""
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed >= 0 else default


def _positive_int(value, default):
    """Return a positive integer config value."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _clamp(value, minimum, maximum):
    """Return value constrained to the inclusive range."""
    return max(minimum, min(maximum, float(value)))


__all__ = [
    "_score_weights",
    "_lexical_similarity",
    "_recency_signal",
    "_usage_signal",
    "_feedback_source_key",
    "_increment_feedback_stats",
    "_source_model",
    "_source_machine_objects",
    "_source_machine_labels",
    "_source_departments",
    "_source_manufacturers",
    "_merge_machine_contexts",
    "_contains_any_machine_name",
    "_machine_series_for_labels",
    "_machine_series_for_label",
    "_error_codes_from_text",
    "_normalize_error_code",
    "_error_code_similarity",
    "_error_alignment_payload",
    "_single_error_code_similarity",
    "_split_error_code",
    "_common_prefix",
    "_task_priority_signal",
    "_severity_signal",
    "_criticality_signal",
    "_score_explanation",
    "_cosine_similarity",
    "_normalize_phrase",
    "_utc_naive",
    "_config_value",
    "_positive_float",
    "_positive_int",
    "_optional_int",
    "_clamp",
]
