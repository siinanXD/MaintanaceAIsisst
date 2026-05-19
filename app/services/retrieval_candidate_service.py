"""Unified retrieval candidate model and ranking helpers."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.services.retrieval_explainability_service import explainability_from_metadata

STRUCTURED_SCORE_CAP = 100.0
KNOWLEDGE_SCORE_CAP = 180.0


@dataclass(frozen=True)
class StructuredCandidateScore:
    """Score information for one structured retrieval candidate."""

    raw_score: float
    explanation: str
    allowed: bool


@dataclass(frozen=True)
class RetrievalCandidate:
    """Comparable retrieval candidate for structured records and RAG chunks."""

    source_type: str
    source_id: int | None
    title: str
    content: str
    module: str
    url: str
    raw_score: float
    normalized_score: float
    quality_status: str = ""
    permission_scope: str = ""
    explanation: str = ""
    metadata: dict = field(default_factory=dict)

    def to_public_source(self, include_score_debug=False):
        """Return a source payload compatible with existing API clients."""
        source = {
            "type": self.source_type,
            "id": self.source_id,
            "title": self.title,
            "module": self.module,
            "url": self.url,
            "reason": self.explanation,
            "score": int(round(max(self.raw_score, 0))),
            "raw_score": round(max(self.raw_score, 0), 2),
            "normalized_score": round(max(self.normalized_score, 0), 2),
        }
        _copy_optional(source, self.metadata, "chunk_id")
        _copy_optional(source, self.metadata, "machine_match")
        _copy_optional(source, self.metadata, "machine_match_reasons")
        _copy_optional(source, self.metadata, "explainability")
        if self.quality_status:
            source["quality_status"] = self.quality_status
        if include_score_debug:
            _copy_optional(source, self.metadata, "score_debug")
        return source

    def context_block(self):
        """Return the compact context block used for structured prompt context."""
        return (
            f"Quelle: {self.module} #{self.source_id} - {self.title}\n"
            f"Grund: {self.explanation}\n"
            f"{self.content}"
        )


def structured_candidate_score(
    query_tokens,
    candidate_tokens,
    permission_scope,
    requested_scopes,
    index,
):
    """Return calibrated score metadata for one structured app-data candidate."""
    requested_scope_set = set(requested_scopes or set())
    overlap = set(query_tokens or set()) & set(candidate_tokens or set())
    requested_bonus = 15 if permission_scope in requested_scope_set else 0
    raw_score = len(overlap) * 20 + requested_bonus
    allowed = raw_score > 0 or permission_scope in requested_scope_set
    reason = (
        f"{len(overlap)} gemeinsame Begriffe" if overlap else "Aktueller sichtbarer Kontext"
    )
    return StructuredCandidateScore(
        raw_score=max(raw_score, 5) - (index * 0.01),
        explanation=reason,
        allowed=allowed,
    )


def normalize_retrieval_score(raw_score, source_kind):
    """Return a comparable 0-100 retrieval score for one source kind."""
    cap = KNOWLEDGE_SCORE_CAP if source_kind == "knowledge" else STRUCTURED_SCORE_CAP
    try:
        numeric_score = float(raw_score or 0)
    except (TypeError, ValueError):
        numeric_score = 0.0
    if cap <= 0:
        return max(numeric_score, 0.0)
    return round(max(0.0, min(100.0, (numeric_score / cap) * 100.0)), 2)


def rank_candidates(candidates, limit=None):
    """Return retrieval candidates ordered by normalized comparable score."""
    ranked = sorted(
        list(candidates or []),
        key=lambda candidate: (
            candidate.normalized_score,
            candidate.raw_score,
            candidate.source_type,
            candidate.title,
        ),
        reverse=True,
    )
    if limit is None:
        return ranked
    return ranked[: _positive_int(limit, len(ranked))]


def vector_result_candidate(result, include_score_debug=False):
    """Return a unified retrieval candidate for one vector-store result."""
    metadata = dict(getattr(result, "metadata", {}) or {})
    raw_score = float(getattr(result, "score", 0.0) or 0.0)
    explainability = explainability_from_metadata(metadata, raw_score)
    score_signals = metadata.get("score_signals") or {}
    quality_status = (
        explainability.get("quality_status")
        or metadata.get("quality_status")
        or score_signals.get("quality_status")
        or ""
    )
    candidate_metadata = {
        "chunk_id": metadata.get("chunk_id"),
        "knowledge_source_type": metadata.get("source_type"),
        "source_record_id": metadata.get("source_id"),
        "document_type": metadata.get("document_type"),
        "department": metadata.get("department"),
        "machine_match": explainability.get("machine_match", 0),
        "machine_match_reasons": explainability.get("machine_match_reasons", []),
        "explainability": explainability,
    }
    if include_score_debug and metadata.get("score_debug"):
        candidate_metadata["score_debug"] = metadata["score_debug"]
    return RetrievalCandidate(
        source_type=metadata.get("type") or "knowledge",
        source_id=_optional_int(metadata.get("id")),
        title=metadata.get("title") or "Wissensquelle",
        content=getattr(result, "text", "") or "",
        module=metadata.get("module") or "knowledge",
        url=metadata.get("url") or "/admin/ai",
        raw_score=raw_score,
        normalized_score=normalize_retrieval_score(raw_score, "knowledge"),
        quality_status=str(quality_status or ""),
        permission_scope=str(metadata.get("source_type") or "knowledge"),
        explanation=f"{int(raw_score)} RAG-Trefferpunkte",
        metadata=candidate_metadata,
    )


def public_sources_from_candidates(candidates, include_score_debug=False):
    """Return public source payloads from unified retrieval candidates."""
    return [
        candidate.to_public_source(include_score_debug=include_score_debug)
        for candidate in candidates or []
    ]


def _copy_optional(target, source, key):
    """Copy one optional metadata value when it is present."""
    value = source.get(key)
    if value not in (None, ""):
        target[key] = value


def _positive_int(value, default):
    """Return a positive integer or a fallback default."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _optional_int(value):
    """Return an integer value when parsing succeeds."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
