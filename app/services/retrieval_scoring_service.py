"""Hybrid scoring for RAG knowledge retrieval."""

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


@dataclass(frozen=True)
class MachineContext:
    """Normalized machine-related retrieval context."""

    machine_names: frozenset = field(default_factory=frozenset)
    machine_ids: frozenset = field(default_factory=frozenset)
    series: frozenset = field(default_factory=frozenset)
    departments: frozenset = field(default_factory=frozenset)
    manufacturers: frozenset = field(default_factory=frozenset)
    error_codes: frozenset = field(default_factory=frozenset)

    def has_context(self):
        """Return whether any machine-aware signal is available."""
        return any(
            (
                self.machine_names,
                self.machine_ids,
                self.series,
                self.departments,
                self.manufacturers,
                self.error_codes,
            )
        )

    def to_debug_dict(self):
        """Return a compact JSON-safe representation for score debugging."""
        return {
            "machine_names": sorted(self.machine_names),
            "machine_ids": sorted(self.machine_ids),
            "series": sorted(self.series),
            "departments": sorted(self.departments),
            "manufacturers": sorted(self.manufacturers),
            "error_codes": sorted(self.error_codes),
        }


@dataclass(frozen=True)
class FeedbackStats:
    """Aggregated user feedback for one retrieval source."""

    helpful: int = 0
    partially_helpful: int = 0
    not_helpful: int = 0

    @property
    def total(self):
        """Return the total feedback count."""
        return self.helpful + self.partially_helpful + self.not_helpful

    @property
    def success_count(self):
        """Return feedback count that indicates useful retrieval."""
        return self.helpful + self.partially_helpful

    def merged(self, other):
        """Return combined feedback statistics."""
        return FeedbackStats(
            helpful=self.helpful + other.helpful,
            partially_helpful=self.partially_helpful + other.partially_helpful,
            not_helpful=self.not_helpful + other.not_helpful,
        )

    def net_signal(self):
        """Return a normalized feedback signal in the range -1 to 1."""
        if not self.total:
            return 0.0
        value = (
            self.helpful * RATING_VALUES["helpful"]
            + self.partially_helpful * RATING_VALUES["partially_helpful"]
            + self.not_helpful * RATING_VALUES["not_helpful"]
        ) / self.total
        return _clamp(value, -1.0, 1.0)


@dataclass(frozen=True)
class HybridScore:
    """Transparent final score and component breakdown for one retrieval result."""

    final_score: float
    allowed: bool
    components: dict = field(default_factory=dict)
    signals: dict = field(default_factory=dict)
    explanation: str = ""

    def metadata(self):
        """Return a JSON-safe metadata payload for score debugging."""
        return {
            "final_score": round(self.final_score, 2),
            "allowed": self.allowed,
            "components": dict(self.components),
            "signals": dict(self.signals),
            "explanation": self.explanation,
        }


class HybridRetrievalScorer:
    """Calculate explainable retrieval scores for knowledge documents."""

    def __init__(self, query_text, query_vector=None, embedding_provider=None):
        """Initialize a scorer for one retrieval query."""
        self.query_text = str(query_text or "")
        self.query_tokens = token_set(self.query_text)
        self.query_vector = query_vector
        self.embedding_provider = embedding_provider
        self.weights = _score_weights()
        self.recency_window_days = _positive_float(
            _config_value("RAG_RECENCY_WINDOW_DAYS", DEFAULT_RECENCY_WINDOW_DAYS),
            DEFAULT_RECENCY_WINDOW_DAYS,
        )
        self.semantic_only_min_similarity = _positive_float(
            _config_value(
                "RAG_SEMANTIC_ONLY_MIN_SIMILARITY",
                DEFAULT_SEMANTIC_ONLY_MIN_SIMILARITY,
            ),
            DEFAULT_SEMANTIC_ONLY_MIN_SIMILARITY,
        )
        self.debug_enabled = bool(_config_value("RAG_SCORE_DEBUG", False))
        self._feedback_cache = None
        self._source_cache = {}
        self._query_machine_context_cache = None
        self._known_departments_cache = None
        self._known_machines_cache = None
        self._known_manufacturers_cache = None

    def score_chunk(self, chunk, document):
        """Return the hybrid score for a persisted knowledge chunk."""
        text = getattr(chunk, "text", "") or ""
        semantic_similarity = self._semantic_similarity(text)
        token_text = getattr(chunk, "token_text", "") or text
        return self.score_text_result(
            text=text,
            document=document,
            chunk_id=getattr(chunk, "id", None),
            semantic_similarity=semantic_similarity,
            token_text=token_text,
        )

    def score_text_result(
        self,
        text,
        document,
        chunk_id=None,
        semantic_similarity=0.0,
        token_text="",
    ):
        """Return the hybrid score for a text result and knowledge document."""
        quality_gate = retrieval_quality_gate_for_document(document)
        if not quality_gate.allowed:
            return HybridScore(
                final_score=0.0,
                allowed=False,
                components={},
                signals={
                    "quality_status": quality_gate.status,
                    "quality_gate": quality_gate.reason,
                    "quality_multiplier": quality_gate.score_multiplier,
                },
                explanation=quality_gate.reason,
            )

        candidate_text = self._candidate_text(text, document)
        lexical_similarity = _lexical_similarity(
            self.query_tokens,
            token_set(token_text or candidate_text),
        )
        recency_signal = _recency_signal(
            getattr(document, "updated_at", None),
            self.recency_window_days,
        )
        machine_signal, machine_reasons, machine_context = self._machine_match_signal(
            candidate_text,
            document,
        )
        error_code_alignment = self._error_code_alignment(machine_context)
        feedback_stats = self._feedback_stats_for(document, chunk_id)
        feedback_signal = feedback_stats.net_signal()
        usage_signal = _usage_signal(feedback_stats.success_count)
        source_priority_signal = self._source_priority_signal(document)
        aging_state = retrieval_aging_signal(document)
        semantic_similarity = _clamp(semantic_similarity, 0.0, 1.0)
        if not self._has_relevance_anchor(
            lexical_similarity,
            machine_signal,
            feedback_stats,
            semantic_similarity,
        ):
            return HybridScore(
                final_score=0.0,
                allowed=False,
                components={},
                signals={
                    "semantic_similarity": round(semantic_similarity, 4),
                    "lexical_similarity": round(lexical_similarity, 4),
                    "machine_match": round(machine_signal, 4),
                    "machine_match_reasons": machine_reasons,
                    "machine_context": machine_context.to_debug_dict(),
                    "feedback_count": feedback_stats.total,
                    "quality_status": quality_gate.status,
                    "quality_gate": quality_gate.reason,
                    "quality_multiplier": quality_gate.score_multiplier,
                },
                explanation="insufficient_relevance_anchor",
            )

        components = {
            "semantic": round(
                semantic_similarity * self.weights["semantic"],
                2,
            ),
            "lexical": round(lexical_similarity * self.weights["lexical"], 2),
            "machine": round(machine_signal * self.weights["machine"], 2),
            "recency": round(recency_signal * self.weights["recency"], 2),
            "feedback": round(feedback_signal * self.weights["feedback"], 2),
            "usage": round(usage_signal * self.weights["usage"], 2),
            "source_priority": round(
                source_priority_signal * self.weights["source_priority"],
                2,
            ),
            "quality": round(quality_gate.score_multiplier * self.weights["quality"], 2),
        }
        relevance_score = sum(
            components[key]
            for key in (
                "semantic",
                "lexical",
                "machine",
                "recency",
                "feedback",
                "usage",
                "source_priority",
            )
        )
        quality_adjusted_score = max(
            0.0,
            round(relevance_score * quality_gate.score_multiplier + components["quality"], 2),
        )
        aging_penalty = round(
            quality_adjusted_score * max(0.0, 1.0 - aging_state.retrieval_multiplier),
            2,
        )
        components["aging"] = -aging_penalty if aging_penalty else 0.0
        aged_score = max(
            0.0,
            round(quality_adjusted_score * aging_state.retrieval_multiplier, 2),
        )
        error_mismatch_penalty = round(
            aged_score * max(0.0, 1.0 - error_code_alignment["multiplier"]),
            2,
        )
        components["error_code_alignment"] = (
            -error_mismatch_penalty if error_mismatch_penalty else 0.0
        )
        final_score = max(0.0, round(aged_score * error_code_alignment["multiplier"], 2))
        signals = {
            "semantic_similarity": round(semantic_similarity, 4),
            "lexical_similarity": round(lexical_similarity, 4),
            "machine_match": round(machine_signal, 4),
            "machine_match_reasons": machine_reasons,
            "machine_context": machine_context.to_debug_dict(),
            "recency": round(recency_signal, 4),
            "feedback": round(feedback_signal, 4),
            "successful_usage_count": feedback_stats.success_count,
            "feedback_count": feedback_stats.total,
            "source_priority": round(source_priority_signal, 4),
            "quality_status": quality_gate.status,
            "quality_gate": quality_gate.reason,
            "quality_multiplier": quality_gate.score_multiplier,
            "aging_multiplier": round(aging_state.retrieval_multiplier, 4),
            "aging_reason": aging_state.reason,
            "aging_age_days": aging_state.age_days,
            "aging_unconfirmed_days": aging_state.unconfirmed_days,
            "aging_stable": aging_state.stable,
            "error_code_alignment": error_code_alignment["state"],
            "query_error_codes": sorted(error_code_alignment["query_error_codes"]),
            "candidate_error_codes": sorted(error_code_alignment["candidate_error_codes"]),
        }
        score = HybridScore(
            final_score=final_score,
            allowed=True,
            components=components,
            signals=signals,
            explanation=_score_explanation(components, signals),
        )
        self._log_score(document, chunk_id, score)
        return score

    def _has_relevance_anchor(
        self,
        lexical_similarity,
        machine_signal,
        feedback_stats,
        semantic_similarity,
    ):
        """Return whether a candidate has enough relevance evidence to score."""
        if lexical_similarity > 0 or machine_signal > 0 or feedback_stats.success_count > 0:
            return True
        return semantic_similarity >= self.semantic_only_min_similarity

    def _semantic_similarity(self, text):
        """Return semantic similarity for local embedding-based retrieval."""
        if not self.query_vector or not self.embedding_provider:
            return 0.0
        return max(
            0.0,
            _cosine_similarity(self.query_vector, self.embedding_provider.embed_text(text)),
        )

    def _candidate_text(self, text, document):
        """Return searchable text assembled from chunk and source metadata."""
        return " ".join(
            part
            for part in (
                text,
                getattr(document, "title", ""),
                getattr(document, "department", ""),
                self._source_context_text(document),
            )
            if part
        )

    def _machine_match_signal(self, candidate_text, document):
        """Return how strongly a candidate matches machine context in the query."""
        query_context = self._query_machine_context()
        candidate_context = self._candidate_machine_context(candidate_text, document)
        if not query_context.has_context():
            return 0.0, [], candidate_context

        score = 0.0
        reasons = []
        if (
            query_context.machine_ids & candidate_context.machine_ids
            or query_context.machine_names & candidate_context.machine_names
            or _contains_any_machine_name(
                query_context.machine_names,
                candidate_context.machine_names,
            )
        ):
            score += 1.0
            reasons.append("same_machine")
        if query_context.series & candidate_context.series:
            score += 0.55
            reasons.append("same_machine_series")
        if query_context.departments & candidate_context.departments:
            score += 0.25
            reasons.append("same_area")
        if query_context.manufacturers & candidate_context.manufacturers:
            score += 0.35
            reasons.append("same_manufacturer")

        error_similarity = _error_code_similarity(
            query_context.error_codes,
            candidate_context.error_codes,
        )
        if error_similarity > 0:
            score += error_similarity * 0.55
            reasons.append(
                "same_error_code" if error_similarity >= 1.0 else "similar_error_code"
            )
        maximum_score = 1.0 if "same_machine" in reasons else 0.85
        return _clamp(score, 0.0, maximum_score), reasons, candidate_context

    def _query_machine_context(self):
        """Return normalized machine context extracted from the query."""
        if self._query_machine_context_cache is not None:
            return self._query_machine_context_cache
        self._query_machine_context_cache = self._machine_context_from_text(
            self.query_text,
            include_known_machine_ids=True,
            require_error_context=True,
        )
        return self._query_machine_context_cache

    def _candidate_machine_context(self, candidate_text, document):
        """Return normalized machine context for a retrieval candidate."""
        source = self._source_record(document)
        text = " ".join(
            part
            for part in (
                candidate_text,
                getattr(document, "title", ""),
                getattr(document, "department", ""),
                self._source_machine_text(document),
            )
            if part
        )
        text_context = self._machine_context_from_text(
            text,
            include_known_machine_ids=True,
            require_error_context=False,
        )
        source_context = self._machine_context_from_source(source, document)
        return _merge_machine_contexts(text_context, source_context)

    def _machine_context_from_text(
        self,
        text,
        include_known_machine_ids=False,
        require_error_context=False,
    ):
        """Return machine context inferred from free text and known app data."""
        normalized_text = _normalize_phrase(text)
        labels = {
            _normalize_phrase(match)
            for match in MACHINE_LABEL_PATTERN.findall(normalized_text)
        }
        machine_ids = set()
        if include_known_machine_ids and has_app_context():
            for machine in self._known_machines():
                machine_name = _normalize_phrase(machine.name)
                if machine_name and machine_name in normalized_text:
                    labels.add(machine_name)
                    machine_ids.add(machine.id)
        departments = {
            department
            for department in self._known_departments()
            if department and department in normalized_text
        }
        manufacturers = {
            manufacturer
            for manufacturer in self._known_manufacturers()
            if manufacturer and manufacturer in normalized_text
        }
        error_codes = _error_codes_from_text(
            normalized_text,
            broad=not require_error_context or bool(ERROR_CONTEXT_PATTERN.search(normalized_text)),
        )
        return MachineContext(
            machine_names=frozenset(label for label in labels if label),
            machine_ids=frozenset(machine_ids),
            series=frozenset(_machine_series_for_labels(labels)),
            departments=frozenset(departments),
            manufacturers=frozenset(manufacturers),
            error_codes=frozenset(error_codes),
        )

    def _machine_context_from_source(self, source, document):
        """Return machine context from a structured source row."""
        if not source:
            return MachineContext(
                departments=frozenset(
                    {_normalize_phrase(getattr(document, "department", ""))}
                    - {""}
                )
            )

        machine_objects = [machine for machine in _source_machine_objects(source) if machine]
        labels = set(_source_machine_labels(source))
        labels.update(_normalize_phrase(machine.name) for machine in machine_objects)
        machine_ids = {
            machine.id for machine in machine_objects if getattr(machine, "id", None)
        }
        departments = set(_source_departments(source))
        departments.add(_normalize_phrase(getattr(document, "department", "")))
        manufacturers = set(_source_manufacturers(source))
        for machine in machine_objects:
            manufacturers.update(
                _normalize_phrase(material.manufacturer)
                for material in getattr(machine, "materials", [])
                if getattr(material, "manufacturer", "")
            )
        error_codes = {
            _normalize_error_code(getattr(source, "error_code", "")),
            *_error_codes_from_text(self._source_context_text_from_source(source), broad=True),
        }
        return MachineContext(
            machine_names=frozenset(label for label in labels if label),
            machine_ids=frozenset(machine_ids),
            series=frozenset(_machine_series_for_labels(labels)),
            departments=frozenset(item for item in departments if item),
            manufacturers=frozenset(item for item in manufacturers if item),
            error_codes=frozenset(item for item in error_codes if item),
        )

    def _feedback_stats_for(self, document, chunk_id):
        """Return aggregated feedback stats for one document and optional chunk."""
        if not document or not getattr(document, "id", None):
            return FeedbackStats()
        stats_by_key = self._feedback_stats_by_key()
        document_key = ("knowledge", int(document.id), None)
        chunk_key = (
            "knowledge",
            int(document.id),
            int(chunk_id) if chunk_id not in (None, "") else None,
        )
        document_stats = stats_by_key.get(document_key, FeedbackStats())
        if chunk_key == document_key:
            return document_stats
        return document_stats.merged(stats_by_key.get(chunk_key, FeedbackStats()))

    def _feedback_stats_by_key(self):
        """Return cached feedback stats grouped by retrieval source key."""
        if self._feedback_cache is not None:
            return self._feedback_cache
        stats = {}
        if has_app_context():
            limit = _positive_int(
                _config_value("RAG_FEEDBACK_SCAN_LIMIT", DEFAULT_FEEDBACK_SCAN_LIMIT),
                DEFAULT_FEEDBACK_SCAN_LIMIT,
            )
            feedback_items = (
                AIFeedback.query.order_by(AIFeedback.created_at.desc()).limit(limit).all()
            )
            for feedback in feedback_items:
                rating = str(feedback.rating or "").strip()
                if rating not in RATING_VALUES:
                    continue
                for source in feedback.sources():
                    key = _feedback_source_key(source)
                    if key is None:
                        continue
                    current = stats.get(key, FeedbackStats())
                    stats[key] = _increment_feedback_stats(current, rating)
        self._feedback_cache = stats
        return self._feedback_cache

    def _source_priority_signal(self, document):
        """Return normalized source-priority signal for a knowledge document."""
        if not document:
            return 0.0
        source_type = str(getattr(document, "source_type", "") or "")
        base_priority = SOURCE_TYPE_PRIORITY.get(source_type, 0.4)
        source = self._source_record(document)
        if source_type == "manual_training" and source:
            return max(base_priority, _clamp((source.priority or 0) / 100, 0.0, 1.0))
        if source_type == "task" and source:
            return max(base_priority, _task_priority_signal(source))
        if source_type == "maintenance_plan" and source:
            return max(base_priority, _task_priority_signal(source))
        if source_type == "error_entry" and source:
            return max(base_priority, _severity_signal(source.severity))
        if source_type == "machine" and source:
            return max(base_priority, _criticality_signal(source.criticality))
        if source_type == "inventory_material" and source:
            return max(base_priority, _criticality_signal(source.criticality))
        if source_type == "generated_document" and source:
            return max(base_priority, _clamp((source.quality_score or 0) / 100, 0.0, 1.0))
        return base_priority

    def _source_record(self, document):
        """Return the structured source row for a knowledge document when available."""
        source_type = str(getattr(document, "source_type", "") or "")
        source_id = getattr(document, "source_id", None)
        if not source_id:
            return None
        key = (source_type, int(source_id))
        if key in self._source_cache:
            return self._source_cache[key]
        model = _source_model(source_type)
        source = None
        if model is not None:
            source = db.session.get(model, int(source_id))
        self._source_cache[key] = source
        return source

    def _source_context_text(self, document):
        """Return compact source metadata text for scoring features."""
        source = self._source_record(document)
        if not source:
            return ""
        return self._source_context_text_from_source(source)

    def _source_context_text_from_source(self, source):
        """Return compact text from source metadata for scoring features."""
        parts = []
        for attr in (
            "title",
            "machine",
            "error_code",
            "description",
            "possible_causes",
            "solution",
            "produced_item",
            "name",
            "manufacturer",
            "summary",
        ):
            value = getattr(source, attr, "")
            if value:
                parts.append(str(value))
        return " ".join(parts)

    def _source_machine_text(self, document):
        """Return machine-specific metadata for a knowledge source."""
        source = self._source_record(document)
        if not source:
            return ""
        return " ".join(_source_machine_labels(source))

    def _error_code_alignment(self, candidate_context):
        """Return an exactness signal that penalizes conflicting error-code hits."""
        query_codes = self._query_machine_context().error_codes
        candidate_codes = candidate_context.error_codes
        if not query_codes:
            return _error_alignment_payload("not_applicable", 1.0, query_codes, candidate_codes)
        if not candidate_codes:
            return _error_alignment_payload(
                "candidate_without_error_code",
                0.92,
                query_codes,
                candidate_codes,
            )
        best_similarity = _error_code_similarity(query_codes, candidate_codes)
        if best_similarity >= 1.0:
            return _error_alignment_payload("exact_error_code", 1.0, query_codes, candidate_codes)
        if best_similarity >= 0.65:
            return _error_alignment_payload(
                "similar_error_code",
                0.86,
                query_codes,
                candidate_codes,
            )
        return _error_alignment_payload(
            "conflicting_error_code",
            0.42,
            query_codes,
            candidate_codes,
        )

    def _known_departments(self):
        """Return normalized known department names."""
        if self._known_departments_cache is not None:
            return self._known_departments_cache
        if not has_app_context():
            self._known_departments_cache = set()
            return self._known_departments_cache
        self._known_departments_cache = {
            _normalize_phrase(department.name)
            for department in Department.query.order_by(Department.name.asc()).limit(100).all()
        }
        return self._known_departments_cache

    def _known_machines(self):
        """Return known machine rows used for context inference."""
        if self._known_machines_cache is not None:
            return self._known_machines_cache
        if not has_app_context():
            self._known_machines_cache = []
            return self._known_machines_cache
        self._known_machines_cache = Machine.query.order_by(Machine.name.asc()).limit(200).all()
        return self._known_machines_cache

    def _known_manufacturers(self):
        """Return normalized known inventory manufacturers."""
        if self._known_manufacturers_cache is not None:
            return self._known_manufacturers_cache
        if not has_app_context():
            self._known_manufacturers_cache = set()
            return self._known_manufacturers_cache
        materials = (
            InventoryMaterial.query.order_by(InventoryMaterial.manufacturer.asc()).limit(300).all()
        )
        self._known_manufacturers_cache = {
            _normalize_phrase(material.manufacturer)
            for material in materials
            if material.manufacturer
        }
        return self._known_manufacturers_cache

    def _log_score(self, document, chunk_id, score):
        """Emit debug logging for one scored retrieval candidate."""
        if not self.debug_enabled:
            return
        logger.debug(
            "retrieval_hybrid_score document_id=%s chunk_id=%s final=%s components=%s signals=%s",
            getattr(document, "id", None),
            chunk_id,
            score.final_score,
            score.components,
            score.signals,
        )


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
            if query_name and candidate_name and (
                query_name in candidate_name or candidate_name in query_name
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
