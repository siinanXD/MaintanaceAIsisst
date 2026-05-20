"""Rule-based high-level query classification for AI retrieval routing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.text_normalization_service import normalize_text, tokenize_text

QUERY_TYPE_LIVE_SQL = "LIVE_SQL"
QUERY_TYPE_KNOWLEDGE_RAG = "KNOWLEDGE_RAG"
QUERY_TYPE_HYBRID = "HYBRID"
QUERY_TYPE_GENERAL = "GENERAL"

ERROR_CODE_PATTERN = re.compile(r"\b[A-Z]{1,6}[-_ ]?\d{2,6}\b", re.IGNORECASE)
TASK_ID_PATTERN = re.compile(r"\b(?:task|aufgabe)\s*#?\s*(\d+)\b", re.IGNORECASE)
MACHINE_HINT_PATTERN = re.compile(
    r"\b(?:maschine|anlage|presse|linie)\s+([a-zA-Z0-9][\w-]*)",
    re.IGNORECASE,
)
MATERIAL_HINT_PATTERN = re.compile(
    r"\b(?:material|ersatzteil|bestand|lager)\s+([a-zA-Z0-9][\w-]*)",
    re.IGNORECASE,
)
ENTITY_HINT_STOPWORDS = {
    "an",
    "der",
    "die",
    "ist",
    "kritisch",
    "mit",
    "steht",
    "stehen",
    "welche",
}

LIVE_SQL_KEYWORDS = {
    "aktuell",
    "anstehend",
    "bestand",
    "bestaende",
    "critical",
    "faellig",
    "fällig",
    "heute",
    "kritisch",
    "lager",
    "maschinenstatus",
    "offen",
    "status",
    "task",
    "tasks",
}
KNOWLEDGE_RAG_KEYWORDS = {
    "anleitung",
    "dokumentation",
    "handbuch",
    "loese",
    "loesung",
    "löse",
    "lösung",
    "notaus",
    "sicherheit",
    "spannung",
    "ueberbruecken",
    "ursache",
    "wartungswissen",
}
HYBRID_KEYWORDS = {
    "defekt",
    "error",
    "fehler",
    "fehlercode",
    "stoerung",
    "störung",
}
LIVE_SQL_SOURCES = {
    "inventory": {"bestand", "bestaende", "lager", "material", "ersatzteil"},
    "machines": {"maschine", "maschinen", "maschinenstatus", "kritisch", "status"},
    "tasks": {"task", "tasks", "aufgabe", "aufgaben", "offen", "faellig", "fällig"},
}
KNOWLEDGE_RAG_SOURCES = {
    "documents": {"dokumentation", "handbuch", "anleitung", "manual"},
    "knowledge": {"loese", "loesung", "löse", "lösung", "wartungswissen", "ursache"},
}


@dataclass(frozen=True)
class QueryClassificationResult:
    """High-level query classification used to route retrieval strategies."""

    query_type: str
    extracted_keywords: list[str] = field(default_factory=list)
    possible_entities: dict = field(default_factory=dict)
    suggested_sources: list[str] = field(default_factory=list)

    def to_dict(self):
        """Return a JSON-safe classification payload."""
        return {
            "query_type": self.query_type,
            "extracted_keywords": list(self.extracted_keywords),
            "possible_entities": _safe_entities(self.possible_entities),
            "suggested_sources": list(self.suggested_sources),
        }


class QueryClassifierService:
    """Classify AI chat questions with deterministic local rules."""

    def classify(self, message):
        """Return the high-level retrieval classification for a message."""
        normalized = normalize_text(message)
        tokens = set(tokenize_text(message))
        entities = _extract_entities(message)
        keywords = _extract_keywords(tokens, normalized)
        query_type = _query_type(tokens, normalized, entities)
        return QueryClassificationResult(
            query_type=query_type,
            extracted_keywords=keywords,
            possible_entities=entities,
            suggested_sources=_suggested_sources(query_type, tokens, entities),
        )


def classify_ai_query(message):
    """Return the default query classification for an AI chat message."""
    return QueryClassifierService().classify(message)


def _query_type(tokens, normalized, entities):
    """Return the high-level query type from rule signals."""
    has_error_code = bool(entities.get("error_codes"))
    live_score = _score(tokens, LIVE_SQL_KEYWORDS)
    knowledge_score = _score(tokens, KNOWLEDGE_RAG_KEYWORDS)
    hybrid_score = _score(tokens, HYBRID_KEYWORDS)
    if has_error_code:
        return QUERY_TYPE_HYBRID
    if hybrid_score and (live_score or knowledge_score):
        return QUERY_TYPE_HYBRID
    if _looks_like_solution_question(normalized) and not live_score:
        return QUERY_TYPE_KNOWLEDGE_RAG
    if live_score:
        return QUERY_TYPE_LIVE_SQL
    if knowledge_score:
        return QUERY_TYPE_KNOWLEDGE_RAG
    return QUERY_TYPE_GENERAL


def _extract_keywords(tokens, normalized):
    """Return matched keyword signals without exposing full prompt text."""
    keywords = set()
    for source in (LIVE_SQL_KEYWORDS, KNOWLEDGE_RAG_KEYWORDS, HYBRID_KEYWORDS):
        keywords.update(token for token in source if token in tokens or token in normalized)
    return sorted(keywords)[:12]


def _extract_entities(message):
    """Return prompt-safe technical entity hints from a query."""
    text = str(message or "")
    entities = {
        "error_codes": sorted(
            {
                match.group(0).upper().replace(" ", "")
                for match in ERROR_CODE_PATTERN.finditer(text)
            }
        ),
        "task_ids": [int(match.group(1)) for match in TASK_ID_PATTERN.finditer(text)],
        "machine_hints": _entity_hints(MACHINE_HINT_PATTERN, text),
        "material_hints": _entity_hints(MATERIAL_HINT_PATTERN, text),
    }
    return {key: value for key, value in entities.items() if value}


def _entity_hints(pattern, text):
    """Return bounded entity hints while filtering grammar filler words."""
    hints = set()
    for match in pattern.finditer(text):
        value = str(match.group(1) or "").strip()
        if not value or normalize_text(value) in ENTITY_HINT_STOPWORDS:
            continue
        hints.add(value)
    return sorted(hints)[:5]


def _suggested_sources(query_type, tokens, entities):
    """Return retrieval source hints for a query classification."""
    sources = []
    if query_type in {QUERY_TYPE_LIVE_SQL, QUERY_TYPE_HYBRID}:
        sources.extend(_source_matches(tokens, LIVE_SQL_SOURCES))
    if query_type in {QUERY_TYPE_KNOWLEDGE_RAG, QUERY_TYPE_HYBRID}:
        sources.extend(_source_matches(tokens, KNOWLEDGE_RAG_SOURCES))
    if entities.get("error_codes"):
        sources.extend(["errors", "knowledge"])
    if entities.get("task_ids"):
        sources.append("tasks")
    if entities.get("machine_hints"):
        sources.append("machines")
    if not sources and query_type == QUERY_TYPE_LIVE_SQL:
        sources.extend(["tasks", "machines", "inventory"])
    if not sources and query_type == QUERY_TYPE_KNOWLEDGE_RAG:
        sources.extend(["knowledge", "documents"])
    if not sources and query_type == QUERY_TYPE_HYBRID:
        sources.extend(["errors", "machines", "knowledge"])
    return list(dict.fromkeys(sources))


def _source_matches(tokens, source_keywords):
    """Return source names whose keyword sets match the query tokens."""
    matches = []
    for source, keywords in source_keywords.items():
        if tokens & keywords:
            matches.append(source)
    return matches


def _score(tokens, keywords):
    """Return a simple keyword overlap score."""
    return len(tokens & keywords)


def _looks_like_solution_question(normalized):
    """Return whether a query asks for repair or knowledge guidance."""
    return any(
        phrase in normalized
        for phrase in (
            "wie loese",
            "wie löse",
            "wie behebe",
            "was bedeutet",
            "was ist die loesung",
            "was ist die lösung",
        )
    )


def _safe_entities(entities):
    """Return a shallow JSON-safe entity mapping."""
    safe = {}
    for key, value in dict(entities or {}).items():
        if isinstance(value, list):
            safe[str(key)] = list(value)[:8]
        else:
            safe[str(key)] = value
    return safe
