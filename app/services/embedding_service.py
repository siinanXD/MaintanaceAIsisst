"""Embedding provider abstractions for the maintenance RAG pipeline."""

import hashlib
import logging
import math
from abc import ABC, abstractmethod

from flask import current_app, has_app_context
from openai import OpenAI, OpenAIError

from app.services.ai_routing import openai_client_options
from app.services.chunking_service import token_set

logger = logging.getLogger(__name__)

DEFAULT_HASH_DIMENSIONS = 384


class EmbeddingServiceError(Exception):
    """Raised when an embedding provider cannot return usable vectors."""


class BaseEmbeddingProvider(ABC):
    """Define the provider contract for text embeddings."""

    name = "base"

    @abstractmethod
    def embed_texts(self, texts):
        """Return one embedding vector for each input text."""

    def embed_text(self, text):
        """Return one embedding vector for a single input text."""
        return self.embed_texts([text])[0]


class HashingEmbeddingProvider(BaseEmbeddingProvider):
    """Create deterministic local embeddings without external services."""

    name = "hashing"

    def __init__(self, dimensions=DEFAULT_HASH_DIMENSIONS):
        """Initialize the local hashing embedding provider."""
        self.dimensions = _validated_dimensions(dimensions)

    def embed_texts(self, texts):
        """Return deterministic normalized vectors for input texts."""
        if texts is None:
            raise EmbeddingServiceError("texts must not be None")
        return [self._embed_text(str(text or "")) for text in texts]

    def _embed_text(self, text):
        """Return a normalized hashing vector for one text."""
        vector = [0.0] * self.dimensions
        tokens = token_set(text)
        if not tokens:
            return vector

        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            raw_value = int.from_bytes(digest, byteorder="big", signed=False)
            index = raw_value % self.dimensions
            sign = 1.0 if (raw_value >> 1) % 2 == 0 else -1.0
            vector[index] += sign
        return _normalize_vector(vector)


class OpenAIEmbeddingProvider(BaseEmbeddingProvider):
    """Create embeddings with OpenAI's embeddings API."""

    name = "openai"

    def __init__(self, api_key, model):
        """Initialize the OpenAI embedding provider."""
        if not api_key:
            raise EmbeddingServiceError("OPENAI_API_KEY is required for OpenAI embeddings")
        if not model:
            raise EmbeddingServiceError("OPENAI_EMBEDDING_MODEL is required")
        self.client = OpenAI(api_key=api_key, **openai_client_options())
        self.model = model

    def embed_texts(self, texts):
        """Return OpenAI embedding vectors for input texts."""
        if texts is None:
            raise EmbeddingServiceError("texts must not be None")
        safe_texts = [str(text or "") for text in texts]
        if not safe_texts:
            return []
        try:
            response = self.client.embeddings.create(
                model=self.model,
                input=safe_texts,
            )
        except OpenAIError as exc:
            logger.exception("embedding_call_failed provider=openai model=%s", self.model)
            raise EmbeddingServiceError("Embedding provider failed") from exc
        return [item.embedding for item in response.data]


def get_embedding_provider():
    """Return the configured embedding provider with a local fallback."""
    provider_name = _config_value("EMBEDDING_PROVIDER", "hashing").lower()
    if provider_name in {"hash", "hashing", "local", "mock"}:
        return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))
    if provider_name == "openai":
        api_key = _config_value("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("embedding_fallback provider=openai reason=api_key_missing")
            return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=_config_value("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        )
    logger.warning("embedding_fallback provider=%s reason=unsupported_provider", provider_name)
    return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))


def _config_value(name, default):
    """Return a Flask config value when available, otherwise a default."""
    if has_app_context():
        return current_app.config.get(name, default)
    return default


def _validated_dimensions(value):
    """Return a safe embedding dimension count."""
    try:
        dimensions = int(value)
    except (TypeError, ValueError) as exc:
        raise EmbeddingServiceError("Embedding dimensions must be an integer") from exc
    if dimensions < 16:
        raise EmbeddingServiceError("Embedding dimensions must be at least 16")
    return dimensions


def _normalize_vector(vector):
    """Return a unit-length vector while preserving all-zero vectors."""
    magnitude = math.sqrt(sum(value * value for value in vector))
    if magnitude <= 0:
        return vector
    return [value / magnitude for value in vector]
