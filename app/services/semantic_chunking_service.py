"""Semantic structure-aware chunking for maintenance knowledge sources."""

import re
from dataclasses import dataclass, field

from app.services.text_normalization_service import tokenize_text

MAX_SECTION_TITLE_CHARS = 140
MAX_PROTECTED_BLOCK_OVERSIZE_FACTOR = 1.35
SEMANTIC_CHUNK_SCHEMA_VERSION = "semantic_structure_v1"

HEADING_NUMBER_PATTERN = re.compile(r"^\d+(?:\.\d+)*[.)]?\s+\S+")
LIST_ITEM_PATTERN = re.compile(
    r"^\s*(?:[-*]|\u2022|\d+[.)]|schritt\s+\d+[:.)-])\s+",
    re.IGNORECASE,
)
ERROR_CODE_PATTERN = re.compile(
    r"\b(?:fehler(?:code)?|error|stoerung|st\u00f6rung|code)\s*[:#-]?\s*"
    r"(?:[A-Z]{1,8}[-_])?[A-Z]{1,4}[-_]?\d{2,5}(?:[-_][A-Z0-9]{1,8})?\b",
    re.IGNORECASE,
)
ERROR_DETAIL_PATTERN = re.compile(
    r"^\s*(?:ursache|causes?|grund|abhilfe|loesung|l\u00f6sung|massnahme|ma\u00dfnahme)"
    r"\s*[:#-]",
    re.IGNORECASE,
)
PROCEDURE_KEYWORDS = (
    "schritt",
    "vorgehen",
    "ablauf",
    "procedure",
    "anleitung",
    "durchfuehrung",
    "durchf\u00fchrung",
)
MAINTENANCE_KEYWORDS = (
    "wartung",
    "inspektion",
    "pruefen",
    "pr\u00fcfen",
    "reinigen",
    "tauschen",
    "schmieren",
    "kalibrieren",
    "instandhaltung",
)


@dataclass(frozen=True)
class SemanticSection:
    """One heading-derived section in a semantic source hierarchy."""

    index: int
    level: int
    title: str
    path: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class SemanticBlock:
    """One source block before final semantic chunk packing."""

    text: str
    offset: int
    kind: str
    semantic_type: str
    section: SemanticSection


def semantic_chunk_text(text, metadata=None, config=None):
    """Split text into semantic chunks with stable hierarchy metadata."""
    normalized_text = _normalize_source_text(text)
    if not normalized_text:
        return []
    blocks = _semantic_blocks(normalized_text)
    if not blocks:
        return []
    max_chars = _config_int(config, "max_chars", 1200)
    target_chars = min(
        _config_int(config, "semantic_target_chars", max_chars),
        max_chars,
    )
    max_chunks = _config_int(config, "max_chunks", 80)
    chunks = _pack_semantic_blocks(
        blocks=blocks,
        metadata=metadata,
        max_chars=max_chars,
        target_chars=target_chars,
        max_chunks=max_chunks,
    )
    return _reindex_chunk_dicts(chunks)


def _semantic_blocks(text):
    """Return semantic blocks grouped by headings, tables, procedures, and errors."""
    blocks = []
    section_stack = []
    section_counter = 0
    current_lines = []
    current_offset = 0
    current_kind = ""
    current_section = _root_section()
    pending_heading = None

    for line, offset in _line_offsets(text):
        stripped = line.strip()
        if not stripped:
            _append_block(blocks, current_lines, current_offset, current_kind, current_section)
            current_lines = []
            current_kind = ""
            continue
        if _is_heading_line(stripped):
            _append_block(blocks, current_lines, current_offset, current_kind, current_section)
            current_lines = []
            current_kind = ""
            level = _heading_level(stripped)
            section_counter += 1
            section_stack = _updated_section_stack(section_stack, level, _clean_heading(stripped))
            current_section = SemanticSection(
                index=section_counter,
                level=level,
                title=section_stack[-1][1],
                path=tuple(title for _level, title in section_stack),
            )
            pending_heading = (line, offset)
            continue

        kind = _line_kind(stripped)
        if pending_heading:
            current_lines = [pending_heading[0]]
            current_offset = pending_heading[1]
            current_kind = kind
            pending_heading = None
        if not current_lines:
            current_lines = [line]
            current_offset = offset
            current_kind = kind
            continue
        if _starts_new_block(current_kind, kind):
            _append_block(blocks, current_lines, current_offset, current_kind, current_section)
            current_lines = [line]
            current_offset = offset
            current_kind = kind
            continue
        current_lines.append(line)

    if pending_heading:
        current_lines = [pending_heading[0]]
        current_offset = pending_heading[1]
        current_kind = "heading"
    _append_block(blocks, current_lines, current_offset, current_kind, current_section)
    return blocks


def _pack_semantic_blocks(blocks, metadata, max_chars, target_chars, max_chunks):
    """Pack semantic blocks without crossing strong maintenance boundaries."""
    chunks = []
    current_blocks = []
    for block in blocks:
        if len(chunks) >= max_chunks:
            break
        for part in _split_oversized_block(block, max_chars):
            if len(chunks) >= max_chunks:
                break
            if (
                current_blocks
                and _is_standalone_block(part)
                and _should_keep_standalone(
                    current_blocks,
                    part,
                    max_chars,
                    target_chars,
                )
            ):
                if current_blocks:
                    _append_chunk(chunks, current_blocks, metadata)
                    current_blocks = []
                _append_chunk(chunks, [part], metadata)
                continue
            if current_blocks and _should_flush_chunk(
                current_blocks,
                part,
                max_chars,
                target_chars,
            ):
                _append_chunk(chunks, current_blocks, metadata)
                current_blocks = []
            current_blocks.append(part)
    if current_blocks and len(chunks) < max_chunks:
        _append_chunk(chunks, current_blocks, metadata)
    return chunks


def _append_chunk(chunks, blocks, metadata):
    """Append one semantic chunk with hierarchy and block metadata."""
    text = _blocks_text(blocks)
    if not text:
        return
    first_block = blocks[0]
    block_kinds = sorted({block.kind for block in blocks if block.kind})
    hierarchy = list(first_block.section.path)
    chunk_metadata = dict(metadata or {})
    chunk_index = len(chunks)
    chunk_metadata.update(
        {
            "chunk_index": chunk_index,
            "chunk_order": chunk_index,
            "chunking_mode": "hybrid_semantic",
            "chunk_schema_version": SEMANTIC_CHUNK_SCHEMA_VERSION,
            "semantic_strategy": "structure_aware_v1",
            "semantic_group": chunk_index,
            "semantic_chunk_type": _chunk_semantic_type(blocks),
            "semantic_boundary": _chunk_boundary(blocks),
            "source_offset": int(first_block.offset),
            "chunk_block_count": len(blocks),
            "chunk_block_kinds": ",".join(block_kinds),
            "section_level": first_block.section.level,
            "chunk_hierarchy": hierarchy,
            "hierarchy_path": " > ".join(hierarchy),
            "parent_section_title": hierarchy[-2] if len(hierarchy) > 1 else "",
        }
    )
    if first_block.section.index:
        chunk_metadata["source_section"] = f"section-{first_block.section.index}"
    if first_block.section.title:
        chunk_metadata["section_title"] = first_block.section.title
    chunk_metadata.update(_chunk_quality_metadata(text))
    chunks.append({"text": text, "chunk_index": chunk_index, "metadata": chunk_metadata})


def _append_block(blocks, lines, offset, kind, section):
    """Append one non-empty semantic source block."""
    text = "\n".join(line for line in lines if line is not None).strip()
    if not text:
        return
    block_kind = kind or "paragraph"
    blocks.append(
        SemanticBlock(
            text=text,
            offset=offset,
            kind=block_kind,
            semantic_type=_semantic_type(block_kind, text, section),
            section=section,
        )
    )


def _semantic_type(kind, text, section):
    """Return the maintenance-specific semantic type for a block."""
    combined = f"{section.title} {text}".lower()
    if kind == "table":
        return "table"
    if kind in {"error_code", "error_detail"}:
        return "error_catalog_entry"
    if kind == "list" and any(keyword in combined for keyword in PROCEDURE_KEYWORDS):
        return "procedure"
    if any(keyword in combined for keyword in MAINTENANCE_KEYWORDS):
        return "maintenance_instruction"
    if kind == "heading":
        return "section"
    return "section"


def _chunk_semantic_type(blocks):
    """Return the strongest semantic type represented by chunk blocks."""
    priorities = (
        "error_catalog_entry",
        "procedure",
        "maintenance_instruction",
        "table",
        "section",
    )
    types = {block.semantic_type for block in blocks}
    return next((value for value in priorities if value in types), "section")


def _chunk_boundary(blocks):
    """Return the boundary reason represented by one chunk."""
    if len(blocks) == 1 and blocks[0].semantic_type in {
        "error_catalog_entry",
        "procedure",
        "maintenance_instruction",
        "table",
    }:
        return blocks[0].semantic_type
    if len({block.section.index for block in blocks}) == 1:
        return "section"
    return "mixed"


def _is_standalone_block(block):
    """Return whether a block should remain its own semantic chunk."""
    return block.semantic_type in {
        "error_catalog_entry",
        "procedure",
        "maintenance_instruction",
        "table",
    }


def _should_keep_standalone(current_blocks, next_block, max_chars, target_chars):
    """Return whether a protected block should force a chunk boundary."""
    if not current_blocks:
        return True
    current_text = _blocks_text(current_blocks)
    if current_blocks[-1].section.index != next_block.section.index:
        return True
    if len(current_text) + 2 + len(next_block.text) > max_chars:
        return True
    return len(current_text) >= target_chars


def _should_flush_chunk(current_blocks, next_block, max_chars, target_chars):
    """Return whether adding a block would cross a semantic boundary."""
    current_text = _blocks_text(current_blocks)
    if current_blocks[-1].section.index != next_block.section.index:
        return True
    if len(current_text) + 2 + len(next_block.text) > max_chars:
        return True
    return len(current_text) >= target_chars


def _split_oversized_block(block, max_chars):
    """Split oversized blocks while preserving protected maintenance context."""
    if len(block.text) <= max_chars:
        return [block]
    protected_limit = int(max_chars * MAX_PROTECTED_BLOCK_OVERSIZE_FACTOR)
    if (
        block.semantic_type in {"error_catalog_entry", "procedure"}
        and len(block.text) <= protected_limit
    ):
        return [block]
    if block.kind == "table":
        return _split_table_block(block, max_chars)
    if block.kind == "list":
        return _split_line_block(block, max_chars)
    return _split_text_block(block, max_chars)


def _split_table_block(block, max_chars):
    """Split a large table while repeating header lines."""
    lines = [line for line in block.text.splitlines() if line.strip()]
    if len(lines) <= 2:
        return _split_text_block(block, max_chars)
    header_lines = _table_header_lines(lines)
    body_lines = lines[len(header_lines) :]
    parts = []
    current_lines = []
    current_offset = block.offset + sum(len(line) + 1 for line in header_lines)
    line_offset = current_offset
    for line in body_lines:
        candidate = "\n".join([*header_lines, *current_lines, line]).strip()
        if current_lines and len(candidate) > max_chars:
            parts.append(_block_part(block, [*header_lines, *current_lines], current_offset))
            current_lines = [line]
            current_offset = line_offset
        else:
            current_lines.append(line)
        line_offset += len(line) + 1
    if current_lines:
        parts.append(_block_part(block, [*header_lines, *current_lines], current_offset))
    return parts or _split_text_block(block, max_chars)


def _split_line_block(block, max_chars):
    """Split a large line-oriented block at line boundaries."""
    lines = block.text.splitlines()
    parts = []
    current_lines = []
    current_offset = block.offset
    line_offset = block.offset
    for line in lines:
        candidate = "\n".join([*current_lines, line]).strip()
        if current_lines and len(candidate) > max_chars:
            parts.append(_block_part(block, current_lines, current_offset))
            current_lines = [line]
            current_offset = line_offset
        else:
            current_lines.append(line)
        line_offset += len(line) + 1
    if current_lines:
        parts.append(_block_part(block, current_lines, current_offset))
    return parts


def _split_text_block(block, max_chars):
    """Split oversized plain text at sentence or whitespace boundaries."""
    parts = []
    start = 0
    while start < len(block.text):
        end = _choose_chunk_end(block.text, start, max_chars)
        parts.append(
            SemanticBlock(
                text=block.text[start:end].strip(),
                offset=block.offset + start,
                kind=block.kind,
                semantic_type=block.semantic_type,
                section=block.section,
            )
        )
        if end >= len(block.text):
            break
        start = max(end, start + 1)
    return [part for part in parts if part.text]


def _block_part(block, lines, offset):
    """Return a block part that keeps the original semantic metadata."""
    return SemanticBlock(
        text="\n".join(lines).strip(),
        offset=offset,
        kind=block.kind,
        semantic_type=block.semantic_type,
        section=block.section,
    )


def _line_kind(stripped_line):
    """Return the structural kind for one source line."""
    if _is_table_line(stripped_line):
        return "table"
    if ERROR_CODE_PATTERN.search(stripped_line):
        return "error_code"
    if ERROR_DETAIL_PATTERN.match(stripped_line):
        return "error_detail"
    if LIST_ITEM_PATTERN.match(stripped_line):
        return "list"
    return "paragraph"


def _starts_new_block(current_kind, next_kind):
    """Return whether a new source block should start between two lines."""
    if not current_kind:
        return False
    if current_kind == "table" or next_kind == "table":
        return current_kind != next_kind
    if current_kind in {"error_code", "error_detail"}:
        return next_kind == "error_code"
    if next_kind in {"error_code", "error_detail"}:
        return current_kind not in {"error_code", "error_detail"}
    if current_kind == "list":
        return next_kind not in {"list", "paragraph"}
    return next_kind == "list"


def _is_heading_line(stripped_line):
    """Return whether a line should start a new semantic section."""
    line = stripped_line.strip()
    if not line or LIST_ITEM_PATTERN.match(line):
        return False
    if line.startswith("#"):
        return True
    if len(line) > MAX_SECTION_TITLE_CHARS:
        return False
    if HEADING_NUMBER_PATTERN.match(line) and not line.endswith("."):
        return True
    if line.endswith(":") and len(line.split()) <= 10:
        return True
    letters = [char for char in line if char.isalpha()]
    if len(letters) >= 4 and line.upper() == line:
        return True
    return line.lower().rstrip(":") in {
        "wartung",
        "wartungsschritte",
        "wartungsanweisung",
        "inspektion",
        "fehlerbild",
        "ursache",
        "abhilfe",
        "loesung",
        "l\u00f6sung",
        "sicherheit",
        "ersatzteile",
        "verfahren",
    }


def _heading_level(stripped_line):
    """Return a stable heading level for hierarchy metadata."""
    line = stripped_line.strip()
    if line.startswith("#"):
        return min(len(line) - len(line.lstrip("#")), 6)
    match = re.match(r"^(\d+(?:\.\d+)*)[.)]?\s+", line)
    if match:
        return min(match.group(1).count(".") + 1, 6)
    return 1


def _updated_section_stack(section_stack, level, title):
    """Return the section stack after entering a heading."""
    stack = [(existing_level, existing_title) for existing_level, existing_title in section_stack]
    while stack and stack[-1][0] >= level:
        stack.pop()
    stack.append((level, title))
    return stack


def _clean_heading(stripped_line):
    """Return a compact heading title."""
    title = re.sub(r"^#+", "", stripped_line).strip()
    return title.rstrip(":")[:MAX_SECTION_TITLE_CHARS]


def _is_table_line(stripped_line):
    """Return whether a line looks like a table row."""
    line = stripped_line.strip()
    if line.count("|") >= 2:
        return True
    if "\t" in line and len([part for part in line.split("\t") if part.strip()]) >= 2:
        return True
    return line.count(";") >= 2 and len(line) <= 240


def _table_header_lines(lines):
    """Return header lines that should repeat across split table chunks."""
    if len(lines) >= 3 and not _is_table_line(lines[0]) and _is_table_line(lines[1]):
        if _looks_like_table_separator(lines[2]):
            return lines[:3]
        return lines[:2]
    if len(lines) >= 2 and _looks_like_table_separator(lines[1]):
        return lines[:2]
    return lines[:1]


def _looks_like_table_separator(line):
    """Return whether a line is a Markdown table separator."""
    normalized = str(line or "").replace("|", "").replace("-", "").replace(":", "").strip()
    return normalized == ""


def _choose_chunk_end(text, start, max_chars):
    """Return a chunk end that prefers semantic text boundaries."""
    hard_end = min(len(text), start + max_chars)
    if hard_end >= len(text):
        return len(text)
    window = text[start:hard_end]
    for boundary in ("\n\n", ". ", "! ", "? ", "; ", ": "):
        index = window.rfind(boundary)
        if index >= int(max_chars * 0.55):
            return start + index + len(boundary)
    space_index = window.rfind(" ")
    if space_index >= int(max_chars * 0.55):
        return start + space_index
    return hard_end


def _normalize_source_text(value):
    """Return source text with stable line boundaries."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = [re.sub(r"[ \t]+$", "", line) for line in text.split("\n")]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    compact_lines = []
    blank_count = 0
    for line in lines:
        if line.strip():
            blank_count = 0
            compact_lines.append(line)
            continue
        blank_count += 1
        if blank_count <= 2:
            compact_lines.append("")
    return "\n".join(compact_lines).strip()


def _line_offsets(text):
    """Yield text lines with their source offsets."""
    offset = 0
    for line in str(text or "").split("\n"):
        yield line, offset
        offset += len(line) + 1


def _blocks_text(blocks):
    """Return block texts joined with paragraph spacing."""
    return "\n\n".join(block.text.strip() for block in blocks if block.text.strip()).strip()


def _chunk_quality_metadata(text):
    """Return prompt-safe chunk size metrics."""
    chunk_text_value = str(text or "")
    non_empty_lines = [line for line in chunk_text_value.splitlines() if line.strip()]
    return {
        "chunk_char_count": len(chunk_text_value),
        "chunk_line_count": len(non_empty_lines),
        "chunk_token_count": len(tokenize_text(chunk_text_value)),
    }


def _root_section():
    """Return the synthetic root section for text before the first heading."""
    return SemanticSection(index=0, level=0, title="", path=())


def _config_int(config, name, default):
    """Return an integer attribute from a chunking config object."""
    try:
        value = int(getattr(config, name, default))
    except (TypeError, ValueError):
        return default
    return value if value > 0 else default


def _reindex_chunk_dicts(chunks):
    """Return chunks with consecutive order metadata."""
    reindexed = []
    for index, chunk in enumerate(chunks):
        metadata = dict(chunk.get("metadata") or {})
        metadata["chunk_index"] = index
        metadata["chunk_order"] = index
        metadata["semantic_group"] = index
        reindexed.append(
            {
                "text": str(chunk.get("text") or ""),
                "chunk_index": index,
                "metadata": metadata,
            }
        )
    return reindexed
