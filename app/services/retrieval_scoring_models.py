"""Models and constants for hybrid retrieval scoring."""

# ruff: noqa: F401, F821

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


def _clamp(value, minimum, maximum):
    """Return value constrained to the inclusive range."""
    return max(minimum, min(maximum, float(value)))


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


__all__ = [name for name in globals() if not name.startswith("__")]
