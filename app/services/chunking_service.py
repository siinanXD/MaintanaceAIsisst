"""Text chunking helpers for the maintenance RAG pipeline."""

import logging
import math
import re
from dataclasses import dataclass, field

from flask import current_app, has_app_context

from app.services.text_normalization_service import (
    normalize_text as normalize_retrieval_text,
)
from app.services.text_normalization_service import tokenize_text

DEFAULT_CHUNK_SIZE = 1200
DEFAULT_CHUNK_OVERLAP = 220
DEFAULT_MAX_CHUNKS = 80
DEFAULT_CHUNKING_MODE = "hybrid_semantic"
DEFAULT_SEMANTIC_BREAKPOINT_THRESHOLD = 0.35
DEFAULT_SEMANTIC_MIN_CHUNK_CHARS = 600
DEFAULT_SEMANTIC_TARGET_CHUNK_CHARS = 1200
DEFAULT_SEMANTIC_MAX_CHUNK_CHARS = 1800
MIN_CHUNK_SIZE = 200
MIN_CHUNK_OVERLAP = 0
MAX_SECTION_TITLE_CHARS = 140
MAX_PROTECTED_BLOCK_OVERSIZE_FACTOR = 1.35
SUPPORTED_CHUNKING_MODES = {"structured", "hybrid_semantic"}
logger = logging.getLogger(__name__)
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


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for deterministic text chunking."""

    max_chars: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_CHUNK_OVERLAP
    max_chunks: int = DEFAULT_MAX_CHUNKS
    mode: str = DEFAULT_CHUNKING_MODE
    semantic_breakpoint_threshold: float = DEFAULT_SEMANTIC_BREAKPOINT_THRESHOLD
    semantic_min_chars: int = DEFAULT_SEMANTIC_MIN_CHUNK_CHARS
    semantic_target_chars: int = DEFAULT_SEMANTIC_TARGET_CHUNK_CHARS
    semantic_max_chars: int = DEFAULT_SEMANTIC_MAX_CHUNK_CHARS


@dataclass(frozen=True)
class TextChunk:
    """One normalized text chunk with optional retrieval metadata."""

    text: str
    chunk_index: int
    metadata: dict = field(default_factory=dict)

    def to_dict(self):
        """Return the chunk as a JSON-serializable dictionary."""
        return {
            "text": self.text,
            "chunk_index": self.chunk_index,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class StructuredBlock:
    """One structure-aware source block before final chunk packing."""

    text: str
    offset: int
    section_index: int = 0
    section_title: str = ""
    kind: str = "paragraph"


def configured_chunking(default=None):
    """Return chunking configuration from Flask config or safe defaults."""
    fallback = default or ChunkingConfig()
    if not has_app_context():
        return fallback
    return ChunkingConfig(
        max_chars=current_app.config.get("RAG_CHUNK_SIZE", fallback.max_chars),
        overlap=current_app.config.get("RAG_CHUNK_OVERLAP", fallback.overlap),
        max_chunks=current_app.config.get("RAG_MAX_CHUNKS", fallback.max_chunks),
        mode=current_app.config.get("RAG_CHUNKING_MODE", fallback.mode),
        semantic_breakpoint_threshold=current_app.config.get(
            "RAG_SEMANTIC_BREAKPOINT_THRESHOLD",
            fallback.semantic_breakpoint_threshold,
        ),
        semantic_min_chars=current_app.config.get(
            "RAG_SEMANTIC_MIN_CHUNK_CHARS",
            fallback.semantic_min_chars,
        ),
        semantic_target_chars=current_app.config.get(
            "RAG_SEMANTIC_TARGET_CHUNK_CHARS",
            fallback.semantic_target_chars,
        ),
        semantic_max_chars=current_app.config.get(
            "RAG_SEMANTIC_MAX_CHUNK_CHARS",
            fallback.semantic_max_chars,
        ),
    )


def validate_chunking_config(config):
    """Return a validated chunking config or raise ValueError."""
    try:
        max_chars = int(config.max_chars)
        overlap = int(config.overlap)
        max_chunks = int(config.max_chunks)
        semantic_threshold = float(config.semantic_breakpoint_threshold)
        semantic_min_chars = int(config.semantic_min_chars)
        semantic_target_chars = int(config.semantic_target_chars)
        semantic_max_chars = int(config.semantic_max_chars)
    except (TypeError, ValueError) as exc:
        raise ValueError("Chunking values must be numeric") from exc

    mode = str(config.mode or DEFAULT_CHUNKING_MODE).strip().lower()
    if max_chars < MIN_CHUNK_SIZE:
        raise ValueError(f"Chunk size must be at least {MIN_CHUNK_SIZE} characters")
    if overlap < MIN_CHUNK_OVERLAP:
        raise ValueError("Chunk overlap must not be negative")
    if overlap >= max_chars:
        raise ValueError("Chunk overlap must be smaller than chunk size")
    if max_chunks < 1:
        raise ValueError("Chunk limit must be at least 1")
    if mode not in SUPPORTED_CHUNKING_MODES:
        raise ValueError(f"Chunking mode must be one of {sorted(SUPPORTED_CHUNKING_MODES)}")
    if not 0 <= semantic_threshold <= 1:
        raise ValueError("Semantic breakpoint threshold must be between 0 and 1")
    if semantic_min_chars < 100:
        raise ValueError("Semantic minimum chunk size must be at least 100 characters")
    if semantic_target_chars < semantic_min_chars:
        raise ValueError("Semantic target chunk size must not be smaller than minimum size")
    if semantic_max_chars < semantic_target_chars:
        raise ValueError("Semantic maximum chunk size must not be smaller than target size")
    return ChunkingConfig(
        max_chars=max_chars,
        overlap=overlap,
        max_chunks=max_chunks,
        mode=mode,
        semantic_breakpoint_threshold=semantic_threshold,
        semantic_min_chars=semantic_min_chars,
        semantic_target_chars=semantic_target_chars,
        semantic_max_chars=semantic_max_chars,
    )


def normalize_text(value):
    """Return whitespace-normalized text suitable for chunking."""
    return normalize_retrieval_text(value, lowercase=False, fold_german=False)


def token_set(value):
    """Return normalized retrieval tokens for local matching."""
    return set(tokenize_text(value))


def chunk_text(text, metadata=None, config=None):
    """Split text into overlapping chunks with stable metadata."""
    structured_text = _normalize_structured_source_text(text)
    if not structured_text:
        return []

    chunking_config = validate_chunking_config(configured_chunking(config))
    blocks = _structured_blocks(structured_text)
    if chunking_config.mode == "hybrid_semantic" and len(blocks) > 1:
        try:
            return _pack_semantic_blocks(blocks, metadata, chunking_config)
        except Exception:
            logger.exception("semantic_chunking_fallback mode=structured")
    if _has_structural_signal(blocks):
        return _pack_structured_blocks(blocks, metadata, chunking_config)
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []
    return _character_chunks(normalized_text, metadata, chunking_config)


def _character_chunks(text, metadata, chunking_config):
    """Return legacy overlapping character chunks for unstructured text."""
    chunks = []
    start = 0
    while start < len(text) and len(chunks) < chunking_config.max_chunks:
        end = _choose_chunk_end(text, start, chunking_config.max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(
                TextChunk(
                    text=chunk,
                    chunk_index=len(chunks),
                    metadata=_chunk_metadata(
                        metadata,
                        len(chunks),
                        source_offset=start,
                    ),
                )
            )
        if end >= len(text):
            break
        start = _next_chunk_start(text, end, chunking_config.overlap)
    return [chunk.to_dict() for chunk in chunks]


def _normalize_structured_source_text(value):
    """Return text with stable line boundaries for section-aware parsing."""
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


def _structured_blocks(text):
    """Return source blocks grouped by headings, lists, tables, and error-code areas."""
    blocks = []
    current_lines = []
    current_offset = 0
    current_kind = ""
    section_index = 0
    section_title = ""
    pending_heading = None

    for line, offset in _line_offsets(text):
        stripped = line.strip()
        if not stripped:
            _append_block(
                blocks,
                current_lines,
                current_offset,
                section_index,
                section_title,
                current_kind,
            )
            current_lines = []
            current_kind = ""
            continue
        if _is_heading_line(stripped):
            _append_block(
                blocks,
                current_lines,
                current_offset,
                section_index,
                section_title,
                current_kind,
            )
            current_lines = []
            current_kind = ""
            section_index += 1
            section_title = _clean_heading(stripped)
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
            _append_block(
                blocks,
                current_lines,
                current_offset,
                section_index,
                section_title,
                current_kind,
            )
            current_lines = [line]
            current_offset = offset
            current_kind = kind
            continue
        current_lines.append(line)

    if pending_heading:
        current_lines = [pending_heading[0]]
        current_offset = pending_heading[1]
        current_kind = "heading"
    _append_block(
        blocks,
        current_lines,
        current_offset,
        section_index,
        section_title,
        current_kind,
    )
    return blocks


def _line_offsets(text):
    """Yield source lines with their starting character offset."""
    offset = 0
    for line in str(text or "").split("\n"):
        yield line, offset
        offset += len(line) + 1


def _append_block(blocks, lines, offset, section_index, section_title, kind):
    """Append a non-empty structured block."""
    text = "\n".join(line for line in lines if line is not None).strip()
    if not text:
        return
    blocks.append(
        StructuredBlock(
            text=text,
            offset=offset,
            section_index=section_index,
            section_title=section_title,
            kind=kind or "paragraph",
        )
    )


def _has_structural_signal(blocks):
    """Return whether blocks carry document structure worth preserving."""
    structural_kinds = {"table", "list", "error_code", "error_detail", "heading"}
    return any(block.section_title or block.kind in structural_kinds for block in blocks)


def _is_heading_line(stripped_line):
    """Return whether a line looks like a document heading."""
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
    heading_words = (
        "wartung",
        "wartungsschritte",
        "inspektion",
        "fehlerbild",
        "ursache",
        "abhilfe",
        "loesung",
        "l\u00f6sung",
        "sicherheit",
        "ersatzteile",
    )
    return line.lower() in heading_words


def _clean_heading(stripped_line):
    """Return a compact section title without markdown heading markers."""
    title = stripped_line.strip().lstrip("#").strip()
    return title.rstrip(":")[:MAX_SECTION_TITLE_CHARS]


def _line_kind(stripped_line):
    """Return the structural kind for one source line."""
    if _is_table_line(stripped_line):
        return "table"
    if LIST_ITEM_PATTERN.match(stripped_line):
        return "list"
    if ERROR_CODE_PATTERN.search(stripped_line):
        return "error_code"
    if ERROR_DETAIL_PATTERN.match(stripped_line):
        return "error_detail"
    return "paragraph"


def _is_table_line(stripped_line):
    """Return whether a line looks like a table row."""
    line = stripped_line.strip()
    if line.count("|") >= 2:
        return True
    if "\t" in line and len([part for part in line.split("\t") if part.strip()]) >= 2:
        return True
    return line.count(";") >= 2 and len(line) <= 240


def _starts_new_block(current_kind, next_kind):
    """Return whether a new source block should start between two lines."""
    if not current_kind:
        return False
    if current_kind == "table" or next_kind == "table":
        return current_kind != next_kind
    if current_kind in {"list", "error_code", "error_detail"}:
        return False
    return next_kind in {"list", "error_code", "error_detail"}


def _pack_structured_blocks(blocks, metadata, chunking_config):
    """Pack structured blocks into chunks without crossing section boundaries."""
    chunks = []
    current_blocks = []
    for block in blocks:
        if len(chunks) >= chunking_config.max_chunks:
            break
        for part in _split_oversized_block(block, chunking_config.max_chars):
            if len(chunks) >= chunking_config.max_chunks:
                break
            if current_blocks and _should_flush_structured_chunk(
                current_blocks,
                part,
                chunking_config.max_chars,
            ):
                _append_structured_chunk(chunks, current_blocks, metadata)
                current_blocks = []
            current_blocks.append(part)
    if current_blocks and len(chunks) < chunking_config.max_chunks:
        _append_structured_chunk(chunks, current_blocks, metadata)
    return _merge_leading_metadata_preface(
        [chunk.to_dict() for chunk in chunks],
        chunking_config.max_chars,
    )


def _pack_semantic_blocks(blocks, metadata, chunking_config):
    """Pack source blocks using structure guards plus semantic breakpoints."""
    parts = _semantic_candidate_blocks(blocks, chunking_config)
    if not parts:
        return []
    distances = _semantic_distances(parts)
    chunks = []
    current_blocks = []
    current_break_distance = 0.0
    max_chars = min(chunking_config.semantic_max_chars, chunking_config.max_chars)
    for index, block in enumerate(parts):
        if len(chunks) >= chunking_config.max_chunks:
            break
        if current_blocks and _should_flush_semantic_chunk(
            current_blocks,
            block,
            distances[index - 1] if index else 0.0,
            chunking_config,
            max_chars,
        ):
            _append_structured_chunk(
                chunks,
                current_blocks,
                metadata,
                extra_metadata={
                    "chunking_mode": "hybrid_semantic",
                    "semantic_group": len(chunks),
                    "semantic_break_distance": round(current_break_distance, 4),
                },
            )
            current_blocks = []
            current_break_distance = 0.0
        current_blocks.append(block)
        if index < len(distances):
            current_break_distance = max(current_break_distance, distances[index])
    if current_blocks and len(chunks) < chunking_config.max_chunks:
        _append_structured_chunk(
            chunks,
            current_blocks,
            metadata,
            extra_metadata={
                "chunking_mode": "hybrid_semantic",
                "semantic_group": len(chunks),
                "semantic_break_distance": round(current_break_distance, 4),
            },
        )
    return _merge_leading_metadata_preface(
        [chunk.to_dict() for chunk in chunks],
        max_chars,
    )


def _semantic_candidate_blocks(blocks, chunking_config):
    """Return block parts small enough for semantic packing."""
    parts = []
    max_chars = min(chunking_config.semantic_max_chars, chunking_config.max_chars)
    for block in blocks:
        parts.extend(_split_oversized_block(block, max_chars))
    return [part for part in parts if part.text.strip()]


def _semantic_distances(blocks):
    """Return cosine distances between neighboring source blocks."""
    if len(blocks) <= 1:
        return []
    embeddings = _embed_block_texts([block.text for block in blocks])
    return [
        _cosine_distance(embeddings[index], embeddings[index + 1])
        for index in range(len(embeddings) - 1)
    ]


def _embed_block_texts(texts):
    """Return embeddings for semantic chunking using the configured provider."""
    from app.services.embedding_service import get_embedding_provider

    return get_embedding_provider().embed_texts(texts)


def _cosine_distance(left_vector, right_vector):
    """Return bounded cosine distance for two embedding vectors."""
    left = [float(value) for value in (left_vector or [])]
    right = [float(value) for value in (right_vector or [])]
    if not left or not right or len(left) != len(right):
        return 1.0
    dot_product = sum(left[index] * right[index] for index in range(len(left)))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm <= 0 or right_norm <= 0:
        return 1.0
    similarity = dot_product / (left_norm * right_norm)
    return max(0.0, min(1.0, 1.0 - similarity))


def _should_flush_semantic_chunk(
    current_blocks,
    next_block,
    semantic_distance,
    chunking_config,
    max_chars,
):
    """Return whether semantic packing should start a new chunk."""
    current_text = _blocks_text(current_blocks)
    candidate_length = len(current_text) + 2 + len(next_block.text)
    if candidate_length > max_chars:
        return True
    current_length = len(current_text)
    if current_length < chunking_config.semantic_min_chars:
        return False
    if current_blocks[-1].section_index != next_block.section_index:
        return True
    if current_length >= chunking_config.semantic_target_chars:
        return semantic_distance >= chunking_config.semantic_breakpoint_threshold
    return False


def _merge_leading_metadata_preface(chunks, max_chars):
    """Merge a leading source-metadata preface with the first real content chunk."""
    if len(chunks) < 2:
        return chunks
    first_text = str(chunks[0].get("text") or "")
    if not _is_metadata_preface(first_text):
        return chunks
    combined_text = f"{first_text.strip()}\n\n{str(chunks[1].get('text') or '').strip()}"
    if len(combined_text) > max_chars:
        return chunks
    merged_metadata = dict(chunks[0].get("metadata") or {})
    for key in ("source_section", "section_title"):
        if not merged_metadata.get(key):
            value = (chunks[1].get("metadata") or {}).get(key)
            if value:
                merged_metadata[key] = value
    merged_chunks = [
        {
            "text": combined_text.strip(),
            "chunk_index": 0,
            "metadata": merged_metadata,
        },
        *chunks[2:],
    ]
    return _reindex_chunk_dicts(merged_chunks)


def _is_metadata_preface(text):
    """Return whether text contains only source metadata labels."""
    allowed_labels = {
        "titel",
        "datei",
        "maschine",
        "abteilung",
        "analyse",
        "zusammenfassung",
        "dokument",
        "quelle",
    }
    lines = [line.strip() for line in str(text or "").splitlines() if line.strip()]
    if not lines:
        return False
    for line in lines:
        normalized = line.lower()
        if normalized.startswith(("maschinenhandbuch #", "wissensquelle #")):
            continue
        if ":" not in normalized:
            return False
        label = normalized.split(":", 1)[0].strip()
        if label not in allowed_labels:
            return False
    return True


def _reindex_chunk_dicts(chunks):
    """Return chunk dictionaries with consecutive public chunk order metadata."""
    reindexed = []
    for index, chunk in enumerate(chunks):
        metadata = dict(chunk.get("metadata") or {})
        metadata["chunk_index"] = index
        metadata["chunk_order"] = index
        reindexed.append(
            {
                "text": str(chunk.get("text") or ""),
                "chunk_index": index,
                "metadata": metadata,
            }
        )
    return reindexed


def _should_flush_structured_chunk(current_blocks, next_block, max_chars):
    """Return whether adding the next block would harm section or size boundaries."""
    current_text = _blocks_text(current_blocks)
    if current_blocks[-1].section_index != next_block.section_index:
        return True
    return len(current_text) + 2 + len(next_block.text) > max_chars


def _append_structured_chunk(chunks, blocks, metadata, extra_metadata=None):
    """Append one packed structured chunk with section metadata."""
    text = _blocks_text(blocks)
    first_block = blocks[0]
    chunks.append(
        TextChunk(
            text=text,
            chunk_index=len(chunks),
            metadata=_chunk_metadata(
                metadata,
                len(chunks),
                section_title=first_block.section_title,
                source_section=_source_section(first_block),
                source_offset=first_block.offset,
                extra_metadata=extra_metadata,
            ),
        )
    )


def _blocks_text(blocks):
    """Return block texts joined with paragraph spacing."""
    return "\n\n".join(block.text.strip() for block in blocks if block.text.strip()).strip()


def _source_section(block):
    """Return a stable section identifier for chunk metadata."""
    if not block.section_index:
        return ""
    return f"section-{block.section_index}"


def _split_oversized_block(block, max_chars):
    """Split very large blocks at line or sentence boundaries as a fallback."""
    if len(block.text) <= max_chars:
        return [block]
    if _is_protected_maintenance_block(block, max_chars):
        return [block]
    if block.kind == "table":
        return _split_table_block(block, max_chars)
    lines = block.text.splitlines()
    if len(lines) <= 1:
        return _split_long_block_text(block, max_chars)

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


def _is_protected_maintenance_block(block, max_chars):
    """Return whether a slightly oversized maintenance block should stay intact."""
    if block.kind not in {"error_code", "error_detail", "list"}:
        return False
    protected_limit = int(max_chars * MAX_PROTECTED_BLOCK_OVERSIZE_FACTOR)
    if len(block.text) > protected_limit:
        return False
    if block.kind in {"error_code", "error_detail"}:
        return True
    return "schritt" in block.text.lower() or LIST_ITEM_PATTERN.search(block.text)


def _split_table_block(block, max_chars):
    """Split an oversized table block while preserving the header row in each part."""
    lines = [line for line in block.text.splitlines() if line.strip()]
    if len(lines) <= 2:
        return _split_long_block_text(block, max_chars)

    header_lines = _table_header_lines(lines)
    body_lines = lines[len(header_lines) :]
    parts = []
    current_lines = []
    current_offset = block.offset + sum(len(line) + 1 for line in header_lines)
    line_offset = current_offset
    for line in body_lines:
        candidate_lines = [*header_lines, *current_lines, line]
        candidate = "\n".join(candidate_lines).strip()
        if current_lines and len(candidate) > max_chars:
            parts.append(_block_part(block, [*header_lines, *current_lines], current_offset))
            current_lines = [line]
            current_offset = line_offset
        else:
            current_lines.append(line)
        line_offset += len(line) + 1
    if current_lines:
        parts.append(_block_part(block, [*header_lines, *current_lines], current_offset))
    return parts or _split_long_block_text(block, max_chars)


def _table_header_lines(lines):
    """Return table header lines that should repeat across split table chunks."""
    if len(lines) >= 3 and not _is_table_line(lines[0]) and _is_table_line(lines[1]):
        if _looks_like_table_separator(lines[2]):
            return lines[:3]
        return lines[:2]
    if len(lines) >= 2 and _looks_like_table_separator(lines[1]):
        return lines[:2]
    return lines[:1]


def _looks_like_table_separator(line):
    """Return whether a row looks like a Markdown table separator."""
    normalized = str(line or "").replace("|", "").replace("-", "").replace(":", "").strip()
    return normalized == ""


def _split_long_block_text(block, max_chars):
    """Split a single oversized block by legacy character boundaries."""
    parts = []
    start = 0
    while start < len(block.text):
        end = _choose_chunk_end(block.text, start, max_chars)
        parts.append(
            StructuredBlock(
                text=block.text[start:end].strip(),
                offset=block.offset + start,
                section_index=block.section_index,
                section_title=block.section_title,
                kind=block.kind,
            )
        )
        if end >= len(block.text):
            break
        start = _next_chunk_start(block.text, end, 0)
    return [part for part in parts if part.text]


def _block_part(block, lines, offset):
    """Return a structured block part with the original section metadata."""
    return StructuredBlock(
        text="\n".join(lines).strip(),
        offset=offset,
        section_index=block.section_index,
        section_title=block.section_title,
        kind=block.kind,
    )


def _choose_chunk_end(text, start, max_chars):
    """Return a chunk end index that prefers paragraph or sentence boundaries."""
    hard_end = min(len(text), start + max_chars)
    if hard_end >= len(text):
        return len(text)

    window = text[start:hard_end]
    boundary = _last_boundary_index(window, ("\n\n", ". ", "! ", "? ", "; ", ": "))
    minimum_end = int(max_chars * 0.55)
    if boundary >= minimum_end:
        return start + boundary
    space_index = window.rfind(" ")
    if space_index >= minimum_end:
        return start + space_index
    return hard_end


def _last_boundary_index(text, boundaries):
    """Return the best local boundary index within a chunk window."""
    positions = []
    for boundary in boundaries:
        index = text.rfind(boundary)
        if index >= 0:
            positions.append(index + len(boundary))
    return max(positions) if positions else -1


def _next_chunk_start(text, end, overlap):
    """Return the next chunk start index while preserving useful overlap."""
    start = max(0, end - overlap)
    while start < end and start < len(text) and text[start].isspace():
        start += 1
    return start


def _chunk_metadata(
    metadata,
    chunk_index,
    section_title="",
    source_section="",
    source_offset=None,
    extra_metadata=None,
):
    """Return metadata for one chunk with a stable chunk index."""
    payload = dict(metadata or {})
    payload["chunk_index"] = chunk_index
    payload["chunk_order"] = chunk_index
    if source_offset is not None:
        payload["source_offset"] = int(source_offset)
    if source_section:
        payload["source_section"] = source_section
    if section_title:
        payload["section_title"] = section_title
    payload.update(extra_metadata or {})
    return payload
