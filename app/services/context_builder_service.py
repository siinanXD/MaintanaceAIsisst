"""Dynamic AI context builder for retrieval results."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.ai_safety_service import safety_context_block
from app.services.source_conflict_service import cautious_context_block

DEFAULT_CONTEXT_MAX_CHARS = 7000
MIN_BOUNDARY_TRUNCATION_CHARS = 80
MIN_REMAINING_CHARS = 200
SOURCE_SEPARATOR = "\n\n"
SENTENCE_BOUNDARY_PATTERN = re.compile(r"[.!?](?:[\"')\]]*)\s+")
LIST_LINE_PATTERN = re.compile(r"^\s*(?:[-*]|\d+[.)]|schritt\s+\d+[:.)-])\s+", re.I)
QUALITY_PRIORITY = {
    "admin_approved": 35,
    "technician_confirmed": 35,
    "ai_suggested": 10,
    "outdated": -15,
    "low_quality": -35,
    "duplicate": -40,
    "draft": -25,
    "rejected": -100,
}


@dataclass(frozen=True)
class ContextSection:
    """One prioritized context section."""

    key: str
    title: str
    content: str
    priority: int
    source_count: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        """Return a JSON-safe context section summary without content."""
        return {
            "key": self.key,
            "title": self.title,
            "priority": self.priority,
            "source_count": self.source_count,
            "chars": len(self.content),
            "truncated": bool(self.metadata.get("truncated")),
            "removed_source_count": int(self.metadata.get("removed_source_count", 0)),
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
    truncation_events = []
    removed_sources = []
    source_prioritization = []
    remaining = max_chars
    for section in ordered_sections:
        bounded, metadata = _bounded_section(section, used_lines, remaining)
        if metadata.get("source_prioritization"):
            source_prioritization.extend(metadata["source_prioritization"])
        if metadata.get("truncated_sources"):
            truncation_events.extend(metadata["truncated_sources"])
        if metadata.get("removed_sources"):
            removed_sources.extend(metadata["removed_sources"])
        if not bounded:
            if metadata.get("removed_sources"):
                continue
            break
        if metadata.get("truncated"):
            truncation_events.append(
                {
                    "section": section.key,
                    "reason": "section_budget_boundary_truncated",
                    "original_chars": len(section.content),
                    "used_chars": len(bounded),
                }
            )
        selected_sections.append(
            ContextSection(
                key=section.key,
                title=section.title,
                content=bounded,
                priority=section.priority,
                source_count=section.source_count,
                metadata=metadata,
            )
        )
        remaining -= len(bounded) + 2
        if remaining <= MIN_REMAINING_CHARS:
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
            "boundary_aware": True,
            "truncated_source_count": len(truncation_events),
            "removed_source_count": len(removed_sources),
        },
        "explainability": {
            "strategy": "priority_boundary_source_aware_context",
            "query_type": getattr(query_understanding, "query_type", "general_question"),
            "quality_preference": "confirmed_and_structured_sources_first",
            "truncated_sources": truncation_events[:12],
            "removed_sources": removed_sources[:12],
            "source_prioritization": source_prioritization[:12],
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
        knowledge_content, knowledge_metadata = _prioritized_knowledge_context(
            vector_context,
            retrieval.get("knowledge_sources") or [],
        )
        sections.append(
            ContextSection(
                "knowledge",
                "Relevante Dokument-Chunks",
                knowledge_content,
                _priority(query_type, "knowledge"),
                len(retrieval.get("knowledge_sources") or []),
                knowledge_metadata,
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


def _bounded_section(section, used_lines, remaining):
    """Return a section content bounded by source and sentence boundaries."""
    if remaining <= 0:
        return "", {"truncated": True}
    if section.metadata.get("source_blocks"):
        return _bounded_source_section(section, used_lines, remaining)
    content = _dedupe_lines(section.content, used_lines)
    bounded, truncated = _truncate_content_to_boundary(content, remaining)
    return bounded, {"truncated": truncated}


def _bounded_source_section(section, used_lines, remaining):
    """Return bounded content for a source-aware knowledge section."""
    selected_blocks = []
    truncated_sources = []
    removed_sources = []
    source_blocks = list(section.metadata.get("source_blocks") or [])
    for block in source_blocks:
        content = _dedupe_lines(block["content"], used_lines)
        if not content:
            removed_sources.append(_source_event(block, "duplicate_or_empty_after_dedupe"))
            continue
        separator_chars = len(SOURCE_SEPARATOR) if selected_blocks else 0
        available = remaining - sum(len(item) for item in selected_blocks) - separator_chars
        if available <= 0:
            removed_sources.append(_source_event(block, "context_budget_exhausted"))
            continue
        if len(content) <= available:
            selected_blocks.append(content)
            continue
        if available >= MIN_BOUNDARY_TRUNCATION_CHARS and not selected_blocks:
            bounded, truncated = _truncate_content_to_boundary(content, available)
            if bounded:
                selected_blocks.append(bounded)
                if truncated:
                    truncated_sources.append(_source_event(block, "boundary_truncated"))
                continue
        removed_sources.append(_source_event(block, "source_dropped_for_budget"))
    content = SOURCE_SEPARATOR.join(selected_blocks).strip()
    metadata = {
        "truncated": bool(truncated_sources or removed_sources),
        "removed_source_count": len(removed_sources),
        "truncated_sources": truncated_sources,
        "removed_sources": removed_sources,
        "source_prioritization": section.metadata.get("source_prioritization", []),
    }
    return content, metadata


def _truncate_content_to_boundary(content, max_chars):
    """Return content truncated on sentence, line, step or word boundaries."""
    text = str(content or "").strip()
    if not text or max_chars <= 0:
        return "", bool(text)
    if len(text) <= max_chars:
        return text, False
    if _looks_like_step_text(text):
        line_bounded = _truncate_lines_to_budget(text, max_chars)
        if line_bounded:
            return line_bounded, True
    candidate = text[:max_chars].rstrip()
    boundary_index = _best_sentence_boundary(candidate, max_chars)
    if boundary_index > 0:
        return candidate[:boundary_index].rstrip(), True
    return _truncate_word_boundary(candidate), True


def _truncate_lines_to_budget(text, max_chars):
    """Return complete list or step lines that fit into the budget."""
    lines = text.splitlines()
    if len(lines) <= 1 and not _looks_like_step_text(text):
        return ""
    selected = []
    used = 0
    for line in lines:
        stripped = line.rstrip()
        if not stripped:
            line_cost = 1
        else:
            line_cost = len(stripped)
        separator = 1 if selected else 0
        if used + separator + line_cost > max_chars:
            break
        selected.append(stripped)
        used += separator + line_cost
    while selected and not selected[-1].strip():
        selected.pop()
    return "\n".join(selected).strip()


def _best_sentence_boundary(candidate, max_chars):
    """Return the best sentence boundary index inside a candidate text."""
    minimum = min(max(40, int(max_chars * 0.45)), max_chars)
    if len(candidate) >= minimum and candidate[-1:] in {".", "!", "?"}:
        return len(candidate)
    positions = [
        match.end()
        for match in SENTENCE_BOUNDARY_PATTERN.finditer(candidate)
        if match.end() >= minimum
    ]
    for marker in ("\n\n", "\n- ", "\n* "):
        index = candidate.rfind(marker)
        if index >= minimum:
            positions.append(index)
    return max(positions) if positions else -1


def _truncate_word_boundary(candidate):
    """Return content cut at a word boundary instead of inside a token."""
    for index in range(len(candidate) - 1, -1, -1):
        if candidate[index].isspace():
            return candidate[:index].rstrip()
    return ""


def _looks_like_step_text(text):
    """Return whether text appears to contain maintenance steps or list items."""
    return any(LIST_LINE_PATTERN.match(line) for line in str(text or "").splitlines())


def _prioritized_knowledge_context(vector_context, knowledge_sources):
    """Return knowledge context sorted and deduplicated by source quality."""
    blocks = _split_source_blocks(vector_context)
    if not blocks:
        return vector_context, {}
    source_blocks = []
    seen = set()
    for index, block in enumerate(blocks):
        source = knowledge_sources[index] if index < len(knowledge_sources) else {}
        source_key = _source_key(source, block)
        if source_key in seen:
            continue
        seen.add(source_key)
        priority, reasons = _source_priority(source, fallback_index=index)
        source_blocks.append(
            {
                "content": block,
                "source": source,
                "priority": priority,
                "priority_reasons": reasons,
                "original_index": index,
            }
        )
    source_blocks.sort(
        key=lambda item: (item["priority"], -item["original_index"]),
        reverse=True,
    )
    return SOURCE_SEPARATOR.join(block["content"] for block in source_blocks), {
        "source_blocks": source_blocks,
        "source_prioritization": [
            _source_event(block, "prioritized_by_score_quality_and_order")
            for block in source_blocks
        ],
        "removed_source_count": max(0, len(blocks) - len(source_blocks)),
    }


def _split_source_blocks(content):
    """Return source blocks split on blank-line boundaries."""
    return [
        block.strip()
        for block in re.split(r"\n\s*\n", str(content or "").strip())
        if block.strip()
    ]


def _source_key(source, block):
    """Return a stable key used to remove duplicate source blocks."""
    if isinstance(source, dict):
        key = (source.get("type"), source.get("id"), source.get("chunk_id"))
        if any(value not in (None, "") for value in key):
            return key
    first_line = str(block or "").splitlines()[0] if block else ""
    return ("block", " ".join(first_line.lower().split()))


def _source_priority(source, fallback_index):
    """Return a source priority score and explainable reasons."""
    if not isinstance(source, dict):
        return -fallback_index, ["original_order"]
    score = _numeric(source.get("score"))
    quality_status = str(source.get("quality_status") or "").strip()
    quality_bonus = QUALITY_PRIORITY.get(quality_status, 0)
    machine_bonus = _numeric(source.get("machine_match")) * 10
    priority = score + quality_bonus + machine_bonus - (fallback_index * 0.01)
    reasons = [f"score:{round(score, 2)}"]
    if quality_status:
        reasons.append(f"quality:{quality_status}")
    if machine_bonus:
        reasons.append("machine_match")
    return priority, reasons


def _source_event(block, reason):
    """Return prompt-safe context-builder source diagnostics."""
    source = block.get("source") if isinstance(block, dict) else {}
    source = source if isinstance(source, dict) else {}
    return {
        "type": str(source.get("type") or "")[:80],
        "id": _optional_int(source.get("id")),
        "chunk_id": _optional_int(source.get("chunk_id")),
        "score": round(_numeric(source.get("score")), 2),
        "quality_status": str(source.get("quality_status") or "")[:80],
        "reason": reason,
        "priority_reasons": list(block.get("priority_reasons") or [])[:6]
        if isinstance(block, dict)
        else [],
    }


def _numeric(value):
    """Return a safe float value."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _optional_int(value):
    """Return an optional integer value."""
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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
