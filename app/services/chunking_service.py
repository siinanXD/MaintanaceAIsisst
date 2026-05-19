"""Text chunking helpers for the maintenance RAG pipeline."""

from dataclasses import dataclass, field

from flask import current_app, has_app_context

from app.services.text_normalization_service import (
    normalize_text as normalize_retrieval_text,
)
from app.services.text_normalization_service import tokenize_text

DEFAULT_CHUNK_SIZE = 1400
DEFAULT_CHUNK_OVERLAP = 160
DEFAULT_MAX_CHUNKS = 80
MIN_CHUNK_SIZE = 200
MIN_CHUNK_OVERLAP = 0


@dataclass(frozen=True)
class ChunkingConfig:
    """Configuration for deterministic text chunking."""

    max_chars: int = DEFAULT_CHUNK_SIZE
    overlap: int = DEFAULT_CHUNK_OVERLAP
    max_chunks: int = DEFAULT_MAX_CHUNKS


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


def configured_chunking(default=None):
    """Return chunking configuration from Flask config or safe defaults."""
    fallback = default or ChunkingConfig()
    if not has_app_context():
        return fallback
    return ChunkingConfig(
        max_chars=current_app.config.get("RAG_CHUNK_SIZE", fallback.max_chars),
        overlap=current_app.config.get("RAG_CHUNK_OVERLAP", fallback.overlap),
        max_chunks=current_app.config.get("RAG_MAX_CHUNKS", fallback.max_chunks),
    )


def validate_chunking_config(config):
    """Return a validated chunking config or raise ValueError."""
    try:
        max_chars = int(config.max_chars)
        overlap = int(config.overlap)
        max_chunks = int(config.max_chunks)
    except (TypeError, ValueError) as exc:
        raise ValueError("Chunking values must be integers") from exc

    if max_chars < MIN_CHUNK_SIZE:
        raise ValueError(f"Chunk size must be at least {MIN_CHUNK_SIZE} characters")
    if overlap < MIN_CHUNK_OVERLAP:
        raise ValueError("Chunk overlap must not be negative")
    if overlap >= max_chars:
        raise ValueError("Chunk overlap must be smaller than chunk size")
    if max_chunks < 1:
        raise ValueError("Chunk limit must be at least 1")
    return ChunkingConfig(max_chars=max_chars, overlap=overlap, max_chunks=max_chunks)


def normalize_text(value):
    """Return whitespace-normalized text suitable for chunking."""
    return normalize_retrieval_text(value, lowercase=False, fold_german=False)


def token_set(value):
    """Return normalized retrieval tokens for local matching."""
    return set(tokenize_text(value))


def chunk_text(text, metadata=None, config=None):
    """Split text into overlapping chunks with stable metadata."""
    normalized_text = normalize_text(text)
    if not normalized_text:
        return []

    chunking_config = validate_chunking_config(configured_chunking(config))
    chunks = []
    start = 0
    while start < len(normalized_text) and len(chunks) < chunking_config.max_chunks:
        end = _choose_chunk_end(normalized_text, start, chunking_config.max_chars)
        chunk = normalized_text[start:end].strip()
        if chunk:
            chunks.append(
                TextChunk(
                    text=chunk,
                    chunk_index=len(chunks),
                    metadata=_chunk_metadata(metadata, len(chunks)),
                )
            )
        if end >= len(normalized_text):
            break
        start = _next_chunk_start(normalized_text, end, chunking_config.overlap)
    return [chunk.to_dict() for chunk in chunks]


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


def _chunk_metadata(metadata, chunk_index):
    """Return metadata for one chunk with a stable chunk index."""
    payload = dict(metadata or {})
    payload["chunk_index"] = chunk_index
    return payload
