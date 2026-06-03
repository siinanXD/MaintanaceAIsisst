"""MongoDB Atlas Vector Search health and index provisioning helpers."""

from __future__ import annotations

import logging
import os
from time import perf_counter

from flask import current_app, has_app_context

from app.services.embedding_service import embedding_dimensions_for_provider
from app.services.vector_sync_status_service import ATLAS_VECTOR_STORE_NAMES

logger = logging.getLogger(__name__)

ATLAS_VECTOR_FIELD = "embedding"
DEFAULT_ATLAS_EMBEDDING_DIMENSIONS = 1536


class AtlasHealthError(Exception):
    """Raised when Atlas health or index operations fail."""


def load_atlas_settings(config=None):
    """Return sanitized Atlas settings without exposing secrets."""
    config = _config(config)
    return {
        "uri": str(config.get("MONGODB_ATLAS_URI", "") or "").strip(),
        "database": str(config.get("MONGODB_ATLAS_DATABASE", "") or "").strip(),
        "collection": str(config.get("MONGODB_ATLAS_VECTOR_COLLECTION", "") or "").strip(),
        "index_name": str(config.get("MONGODB_ATLAS_VECTOR_INDEX", "") or "").strip(),
        "timeout_ms": _positive_int(config.get("MONGODB_ATLAS_TIMEOUT_MS", 3000), 3000),
        "dimensions": atlas_embedding_dimensions(config),
        "configured_store": str(config.get("RAG_VECTOR_STORE", "") or "").strip().lower(),
    }


def atlas_embedding_dimensions(config=None):
    """Return the configured Atlas embedding dimension count."""
    config = _config(config)
    explicit = config.get("RAG_EMBEDDING_DIMENSIONS")
    if explicit not in (None, ""):
        return _positive_int(explicit, DEFAULT_ATLAS_EMBEDDING_DIMENSIONS)
    provider = str(config.get("EMBEDDING_PROVIDER", "openai") or "openai").lower()
    model = str(config.get("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small") or "")
    hash_dimensions = config.get("RAG_HASH_EMBEDDING_DIMENSIONS", 384)
    return embedding_dimensions_for_provider(provider, model, hash_dimensions)


def atlas_vector_store_configured(config=None):
    """Return whether Atlas is the configured vector store."""
    settings = load_atlas_settings(config)
    return settings["configured_store"] in ATLAS_VECTOR_STORE_NAMES


def build_atlas_client(settings):
    """Create and ping a pymongo client without logging connection details."""
    try:
        from pymongo import MongoClient
    except ImportError as exc:
        raise AtlasHealthError("pymongo_missing") from exc

    try:
        client = MongoClient(
            settings["uri"],
            serverSelectionTimeoutMS=settings["timeout_ms"],
            connectTimeoutMS=settings["timeout_ms"],
            socketTimeoutMS=settings["timeout_ms"],
        )
        client.admin.command("ping")
        return client
    except Exception as exc:
        raise AtlasHealthError("connection_failed") from exc


def list_atlas_vector_indexes(collection, index_name=""):
    """Return prompt-safe vector search index names for one collection."""
    try:
        indexes = list(collection.list_search_indexes())
    except Exception as exc:
        raise AtlasHealthError("index_list_failed") from exc
    names = []
    for index in indexes:
        name = str(index.get("name") or index.get("id") or "").strip()
        if name:
            names.append(name)
    if index_name and index_name in names:
        return names, True
    return names, bool(index_name and index_name in names)


def ensure_atlas_vector_index(settings=None, config=None):
    """Create the configured Atlas vector index when it is missing."""
    settings = settings or load_atlas_settings(config)
    missing = _missing_settings(settings)
    if missing:
        return {
            "ok": False,
            "status": "missing_config",
            "reason": f"missing_config:{','.join(missing)}",
            "index_name": settings.get("index_name", ""),
        }

    try:
        client = build_atlas_client(settings)
        collection = client[settings["database"]][settings["collection"]]
        _ensure_atlas_collection(collection)
        _, index_present = list_atlas_vector_indexes(collection, settings["index_name"])
        if index_present:
            return {
                "ok": True,
                "status": "ready",
                "index_name": settings["index_name"],
                "dimensions": settings["dimensions"],
                "created": False,
            }

        _create_atlas_vector_index(
            collection,
            settings["index_name"],
            settings["dimensions"],
        )
        return {
            "ok": True,
            "status": "created",
            "index_name": settings["index_name"],
            "dimensions": settings["dimensions"],
            "created": True,
        }
    except AtlasHealthError as exc:
        return {
            "ok": False,
            "status": "error",
            "reason": str(exc),
            "index_name": settings.get("index_name", ""),
        }
    except Exception as exc:
        logger.warning("atlas_index_setup_failed error=%s", exc.__class__.__name__)
        return {
            "ok": False,
            "status": "error",
            "reason": exc.__class__.__name__,
            "index_name": settings.get("index_name", ""),
        }


def atlas_vector_store_health(config=None):
    """Return prompt-safe Atlas vector-store health diagnostics."""
    settings = load_atlas_settings(config)
    configured = settings["configured_store"] in ATLAS_VECTOR_STORE_NAMES
    payload = {
        "configured": configured,
        "active": False,
        "connected": False,
        "index_ready": False,
        "dimensions_ok": True,
        "dimensions": settings["dimensions"],
        "index_name": settings["index_name"],
        "fallback_active": False,
        "reason": "",
    }
    if not configured:
        payload["reason"] = "atlas_not_configured"
        return payload

    missing = _missing_settings(settings)
    if missing:
        payload["reason"] = f"missing_config:{','.join(missing)}"
        payload["fallback_active"] = True
        return payload

    try:
        from app.services.vector_store_service import get_vector_store

        store = get_vector_store()
        store_name = getattr(store, "name", "")
        payload["active"] = store_name in ATLAS_VECTOR_STORE_NAMES
        payload["fallback_active"] = not payload["active"]
        if payload["fallback_active"]:
            payload["reason"] = getattr(store, "_status_error", "") or "configured_store_fallback"
    except Exception as exc:
        payload["fallback_active"] = True
        payload["reason"] = exc.__class__.__name__

    try:
        client = build_atlas_client(settings)
        payload["connected"] = True
        collection = client[settings["database"]][settings["collection"]]
        _, payload["index_ready"] = list_atlas_vector_indexes(collection, settings["index_name"])
        if not payload["index_ready"]:
            payload["reason"] = payload["reason"] or "index_missing"
    except AtlasHealthError as exc:
        payload["connected"] = False
        payload["fallback_active"] = True
        payload["reason"] = payload["reason"] or str(exc)
    except Exception as exc:
        payload["connected"] = False
        payload["fallback_active"] = True
        payload["reason"] = payload["reason"] or exc.__class__.__name__

    if payload["fallback_active"] or not payload["index_ready"]:
        payload["ok"] = False
    else:
        payload["ok"] = bool(payload["active"] and payload["connected"] and payload["index_ready"])
    return payload


def probe_atlas_vector_search(settings=None, config=None):
    """Run a lightweight Atlas vector search probe for smoke checks."""
    settings = settings or load_atlas_settings(config)
    started_at = perf_counter()
    try:
        client = build_atlas_client(settings)
        collection = client[settings["database"]][settings["collection"]]
        _, index_ready = list_atlas_vector_indexes(collection, settings["index_name"])
        if not index_ready:
            return {
                "ok": False,
                "reason": "index_missing",
                "latency_ms": round((perf_counter() - started_at) * 1000, 2),
            }
        zero_vector = [0.0] * settings["dimensions"]
        pipeline = [
            {
                "$vectorSearch": {
                    "index": settings["index_name"],
                    "path": ATLAS_VECTOR_FIELD,
                    "queryVector": zero_vector,
                    "numCandidates": 1,
                    "limit": 1,
                }
            },
            {"$limit": 1},
        ]
        list(collection.aggregate(pipeline))
        return {
            "ok": True,
            "reason": "",
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
        }
    except Exception as exc:
        return {
            "ok": False,
            "reason": exc.__class__.__name__,
            "latency_ms": round((perf_counter() - started_at) * 1000, 2),
        }


def _ensure_atlas_collection(collection):
    """Ensure the configured Atlas vector collection exists."""
    database = collection.database
    if collection.name not in database.list_collection_names():
        database.create_collection(collection.name)


def _atlas_vector_index_definition(dimensions):
    """Return the Atlas Vector Search index definition payload."""
    return {
        "fields": [
            {
                "type": "vector",
                "path": ATLAS_VECTOR_FIELD,
                "numDimensions": dimensions,
                "similarity": "cosine",
            }
        ]
    }


def _create_atlas_vector_index(collection, index_name, dimensions):
    """Create a vector search index using the pymongo API when available."""
    definition = _atlas_vector_index_definition(dimensions)
    try:
        from pymongo.operations import SearchIndexModel

        collection.create_search_index(
            SearchIndexModel(
                definition=definition,
                name=index_name,
                type="vectorSearch",
            )
        )
        return
    except ImportError:
        pass
    collection.create_search_index({"name": index_name, "definition": definition})


def _config(config=None):
    if config is not None:
        return config
    if has_app_context():
        return current_app.config
    return {
        "MONGODB_ATLAS_URI": os.getenv("MONGODB_ATLAS_URI", ""),
        "MONGODB_ATLAS_DATABASE": os.getenv("MONGODB_ATLAS_DATABASE", "maintenance_ai"),
        "MONGODB_ATLAS_VECTOR_COLLECTION": os.getenv(
            "MONGODB_ATLAS_VECTOR_COLLECTION",
            "knowledge_vectors",
        ),
        "MONGODB_ATLAS_VECTOR_INDEX": os.getenv(
            "MONGODB_ATLAS_VECTOR_INDEX",
            "knowledge_vector_index",
        ),
        "MONGODB_ATLAS_TIMEOUT_MS": os.getenv("MONGODB_ATLAS_TIMEOUT_MS", "3000"),
        "RAG_VECTOR_STORE": os.getenv("RAG_VECTOR_STORE", ""),
        "EMBEDDING_PROVIDER": os.getenv("EMBEDDING_PROVIDER", "openai"),
        "OPENAI_EMBEDDING_MODEL": os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small"),
        "RAG_HASH_EMBEDDING_DIMENSIONS": os.getenv("RAG_HASH_EMBEDDING_DIMENSIONS", "384"),
        "RAG_EMBEDDING_DIMENSIONS": os.getenv("RAG_EMBEDDING_DIMENSIONS", ""),
    }


def _missing_settings(settings):
    missing = []
    if not settings.get("uri"):
        missing.append("MONGODB_ATLAS_URI")
    if not settings.get("database"):
        missing.append("MONGODB_ATLAS_DATABASE")
    if not settings.get("collection"):
        missing.append("MONGODB_ATLAS_VECTOR_COLLECTION")
    if not settings.get("index_name"):
        missing.append("MONGODB_ATLAS_VECTOR_INDEX")
    return missing


def _positive_int(value, default):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default
