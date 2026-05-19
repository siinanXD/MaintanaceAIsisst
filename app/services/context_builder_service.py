"""Dynamic AI context builder for retrieval results."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai_safety_service import safety_context_block
from app.services.source_conflict_service import cautious_context_block

DEFAULT_CONTEXT_MAX_CHARS = 7000


@dataclass(frozen=True)
class ContextSection:
    """One prioritized context section."""

    key: str
    title: str
    content: str
    priority: int
    source_count: int = 0

    def to_dict(self):
        """Return a JSON-safe context section summary without content."""
        return {
            "key": self.key,
            "title": self.title,
            "priority": self.priority,
            "source_count": self.source_count,
            "chars": len(self.content),
        }


def build_dynamic_context(
    message,
    retrieval,
    query_understanding,
    safety_assessment=None,
    conflicts=None,
    conversation_context=None,
    timeline_context=None,
    max_chars=DEFAULT_CONTEXT_MAX_CHARS,
):
    """Return a prioritized, bounded AI context payload."""
    sections = _candidate_sections(
        retrieval=retrieval,
        query_understanding=query_understanding,
        safety_assessment=safety_assessment,
        conflicts=conflicts,
        conversation_context=conversation_context,
        timeline_context=timeline_context,
    )
    ordered_sections = sorted(sections, key=lambda section: section.priority, reverse=True)
    selected_sections = []
    used_lines = set()
    remaining = max_chars
    for section in ordered_sections:
        content = _dedupe_lines(section.content, used_lines)
        if not content:
            continue
        bounded = content[:remaining].strip()
        if not bounded:
            break
        selected_sections.append(
            ContextSection(
                key=section.key,
                title=section.title,
                content=bounded,
                priority=section.priority,
                source_count=section.source_count,
            )
        )
        remaining -= len(bounded) + 2
        if remaining <= 200:
            break

    context = "\n\n".join(
        f"{section.title}:\n{section.content}" for section in selected_sections
    ).strip()
    return {
        "context": context,
        "sections": [section.to_dict() for section in selected_sections],
        "stats": {
            "max_chars": max_chars,
            "used_chars": len(context),
            "section_count": len(selected_sections),
            "deduplicated": True,
        },
        "explainability": {
            "strategy": "priority_bounded_context",
            "query_type": getattr(query_understanding, "query_type", "general_question"),
            "quality_preference": "confirmed_and_structured_sources_first",
        },
    }


def _candidate_sections(
    retrieval,
    query_understanding,
    safety_assessment,
    conflicts,
    conversation_context,
    timeline_context,
):
    """Return candidate context sections before ranking and truncation."""
    query_type = getattr(query_understanding, "query_type", "general_question")
    sections = []
    if safety_assessment and safety_assessment.safety_relevant:
        sections.append(
            ContextSection(
                "safety",
                "Sicherheitsregeln",
                safety_context_block(safety_assessment),
                _priority(query_type, "safety"),
            )
        )
    if conflicts and conflicts.get("has_conflicts"):
        sections.append(
            ContextSection(
                "conflicts",
                "Quellenkonflikte",
                cautious_context_block(conflicts),
                _priority(query_type, "conflicts"),
                conflicts.get("count", 0),
            )
        )
    if conversation_context is not None and getattr(conversation_context, "applied", False):
        sections.append(
            ContextSection(
                "session",
                "Session-Kontext",
                conversation_context.context_text,
                _priority(query_type, "session"),
            )
        )
    if timeline_context and timeline_context.get("context"):
        sections.append(
            ContextSection(
                "timeline",
                "Zeitlicher Verlauf",
                timeline_context["context"],
                _priority(query_type, "timeline"),
                len(timeline_context.get("sources") or []),
            )
        )
    structured_context = retrieval.get("structured_context") or ""
    if structured_context:
        sections.append(
            ContextSection(
                "structured",
                "Aktuelle strukturierte Daten",
                structured_context,
                _priority(query_type, "structured"),
                _structured_source_count(retrieval),
            )
        )
    vector_context = retrieval.get("vector_context") or ""
    if vector_context:
        sections.append(
            ContextSection(
                "knowledge",
                "Relevante Dokument-Chunks",
                vector_context,
                _priority(query_type, "knowledge"),
                len(retrieval.get("knowledge_sources") or []),
            )
        )
    links = (retrieval.get("knowledge_links") or {}).get("links") or []
    if links:
        sections.append(
            ContextSection(
                "knowledge_links",
                "Verknuepfte Wissensquellen",
                _links_context(links),
                _priority(query_type, "knowledge_links"),
                len(links),
            )
        )
    return sections


def _priority(query_type, section_key):
    """Return section priority for a query type."""
    base = {
        "safety": 100,
        "conflicts": 95,
        "session": 72,
        "structured": 70,
        "timeline": 65,
        "knowledge": 60,
        "knowledge_links": 45,
    }
    priority = base.get(section_key, 10)
    if query_type == "safety_question" and section_key == "safety":
        priority += 25
    if query_type == "trend_history_question" and section_key == "timeline":
        priority += 25
    if query_type in {"machine_question", "inventory_question", "task_question"}:
        if section_key == "structured":
            priority += 20
    if query_type in {"document_question", "knowledge_gap"} and section_key == "knowledge":
        priority += 15
    return priority


def _structured_source_count(retrieval):
    """Return the number of non-knowledge sources in a retrieval payload."""
    return sum(1 for source in retrieval.get("sources") or [] if source.get("type") != "knowledge")


def _links_context(links):
    """Return compact linked-source context."""
    lines = []
    for link in links[:8]:
        reasons = ", ".join(link.get("reasons") or [])
        lines.append(
            f"- Wissen #{link['id']} {link['title']} "
            f"({link.get('source_type') or 'unknown'}, Score {link.get('score')}, {reasons})"
        )
    return "\n".join(lines)


def _dedupe_lines(content, used_lines):
    """Return content without exact duplicate lines already used."""
    lines = []
    for line in str(content or "").splitlines():
        normalized = " ".join(line.strip().lower().split())
        if not normalized or normalized in used_lines:
            continue
        used_lines.add(normalized)
        lines.append(line)
    return "\n".join(lines).strip()
