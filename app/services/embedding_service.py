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
EMBEDDING_PROVIDER_CATALOG = (
    {
        "provider": "hashing",
        "status": "supported",
        "mode": "local_hashing",
        "requires_credential": False,
        "requires_base_url": False,
        "effective_fallback": "hashing",
    },
    {
        "provider": "openai",
        "status": "supported",
        "mode": "external",
        "requires_credential": True,
        "requires_base_url": False,
        "effective_fallback": "hashing",
    },
    {
        "provider": "openai_compatible",
        "status": "supported",
        "mode": "openai_compatible",
        "requires_credential": True,
        "requires_base_url": True,
        "effective_fallback": "hashing",
    },
    {
        "provider": "gemini",
        "status": "planned",
        "mode": "unsupported",
        "requires_credential": True,
        "requires_base_url": False,
        "effective_fallback": "hashing",
    },
)


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

    def __init__(self, api_key, model, provider_name="openai"):
        """Initialize the OpenAI embedding provider."""
        if not api_key:
            raise EmbeddingServiceError("OPENAI_API_KEY is required for OpenAI embeddings")
        if not model:
            raise EmbeddingServiceError("OPENAI_EMBEDDING_MODEL is required")
        self.name = provider_name
        self.client = OpenAI(
            api_key=api_key,
            **openai_client_options(allow_base_url=self.name == "openai_compatible"),
        )
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
        api_key = _config_text_value("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning("embedding_fallback provider=openai reason=api_key_missing")
            return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=_config_text_value(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
        )
    if provider_name == "openai_compatible":
        api_key = _config_text_value("OPENAI_API_KEY", "")
        if not api_key:
            logger.warning(
                "embedding_fallback provider=openai_compatible reason=api_key_missing"
            )
            return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))
        if not _config_value("AI_BASE_URL", ""):
            logger.warning(
                "embedding_fallback provider=openai_compatible reason=base_url_missing"
            )
            return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))
        return OpenAIEmbeddingProvider(
            api_key=api_key,
            model=_config_text_value(
                "OPENAI_EMBEDDING_MODEL",
                "text-embedding-3-small",
            ),
            provider_name="openai_compatible",
        )
    logger.warning("embedding_fallback provider=%s reason=unsupported_provider", provider_name)
    return HashingEmbeddingProvider(_config_value("RAG_HASH_EMBEDDING_DIMENSIONS", 384))


def embedding_provider_status(config=None):
    """Return redacted embedding provider readiness without external API calls."""
    config = config or (current_app.config if has_app_context() else {})
    provider_name = str(config.get("EMBEDDING_PROVIDER", "hashing") or "hashing").lower()
    api_key_configured = bool(str(config.get("OPENAI_API_KEY") or "").strip())
    base_url_configured = bool(str(config.get("AI_BASE_URL") or "").strip())
    model = str(config.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small") or "").strip()
    dimensions = _status_dimensions(config.get("RAG_HASH_EMBEDDING_DIMENSIONS", 384))
    if provider_name in {"hash", "hashing", "local", "mock"}:
        return {
            "provider": provider_name,
            "ready": True,
            "mode": "local_hashing",
            "reason": "",
            "effective_provider": "hashing",
            "configuration_action": "none",
            "recommended_action": "Keine Embedding-Konfiguration erforderlich.",
            "dimensions": dimensions,
        }
    if provider_name == "openai":
        ready = bool(api_key_configured and model)
        reason = "" if ready else _embedding_config_reason(api_key_configured, model)
        return {
            "provider": "openai",
            "ready": ready,
            "mode": "external",
            "reason": reason,
            "effective_provider": "openai" if ready else "hashing",
            "configuration_action": _embedding_configuration_action(reason),
            "recommended_action": _embedding_recommended_action(reason),
            "api_key_configured": api_key_configured,
            "model_configured": bool(model),
        }
    if provider_name == "openai_compatible":
        ready = bool(api_key_configured and model and base_url_configured)
        reason = _embedding_config_reason(api_key_configured, model)
        if not reason and not base_url_configured:
            reason = "base_url_missing"
        return {
            "provider": "openai_compatible",
            "ready": ready,
            "mode": "openai_compatible",
            "reason": reason,
            "effective_provider": "openai_compatible" if ready else "hashing",
            "configuration_action": _embedding_configuration_action(reason),
            "recommended_action": _embedding_recommended_action(reason),
            "api_key_configured": api_key_configured,
            "base_url_configured": base_url_configured,
            "model_configured": bool(model),
        }
    return {
        "provider": provider_name,
        "ready": False,
        "mode": "unsupported",
        "reason": "unsupported_provider",
        "effective_provider": "hashing",
        "configuration_action": "select_supported_embedding_provider",
        "recommended_action": (
            "EMBEDDING_PROVIDER auf hashing, openai oder openai_compatible setzen."
        ),
    }


def embedding_provider_catalog():
    """Return redacted embedding-provider capabilities for admin status payloads."""
    return [dict(item) for item in EMBEDDING_PROVIDER_CATALOG]


def _config_value(name, default):
    """Return a Flask config value when available, otherwise a default."""
    if has_app_context():
        return current_app.config.get(name, default)
    return default


def _config_text_value(name, default):
    """Return a stripped Flask config text value when available."""
    return str(_config_value(name, default) or "").strip()


def _embedding_config_reason(api_key_configured, model):
    """Return the first missing embedding provider configuration reason."""
    if not api_key_configured:
        return "api_key_missing"
    if not model:
        return "embedding_model_missing"
    return ""


def _embedding_configuration_action(reason):
    """Return a stable admin action key for one embedding readiness reason."""
    actions = {
        "": "none",
        "api_key_missing": "set_openai_api_key",
        "embedding_model_missing": "set_openai_embedding_model",
        "base_url_missing": "set_ai_base_url",
        "unsupported_provider": "select_supported_embedding_provider",
    }
    return actions.get(str(reason or ""), "review_embedding_provider_configuration")


def _embedding_recommended_action(reason):
    """Return a concise admin-facing embedding remediation hint."""
    actions = {
        "": "Embedding-Provider ist einsatzbereit.",
        "api_key_missing": "OPENAI_API_KEY setzen oder EMBEDDING_PROVIDER=hashing verwenden.",
        "embedding_model_missing": "OPENAI_EMBEDDING_MODEL setzen.",
        "base_url_missing": "AI_BASE_URL fuer den OpenAI-kompatiblen Endpoint setzen.",
        "unsupported_provider": (
            "EMBEDDING_PROVIDER auf hashing, openai oder openai_compatible setzen."
        ),
    }
    return actions.get(str(reason or ""), "Embedding-Provider-Konfiguration pruefen.")


def _status_dimensions(value):
    """Return safe dimensions for status payloads without raising."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return DEFAULT_HASH_DIMENSIONS


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
