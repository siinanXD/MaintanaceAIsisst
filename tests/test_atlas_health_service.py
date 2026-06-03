"""Tests for MongoDB Atlas health and index provisioning."""

import sys
from types import ModuleType

from app.services.atlas_health_service import (
    atlas_vector_store_health,
    ensure_atlas_vector_index,
    load_atlas_settings,
    probe_atlas_vector_search,
)


def test_load_atlas_settings_reads_configured_values(app):
    """Verify Atlas settings load configured database and index names."""
    with app.app_context():
        _configure_atlas(app)
        settings = load_atlas_settings()

    assert settings["database"] == "maintenance_ai"
    assert settings["collection"] == "knowledge_vectors"
    assert settings["index_name"] == "knowledge_vector_index"
    assert settings["dimensions"] == 1536


def test_atlas_health_never_exposes_connection_uri(app, monkeypatch):
    """Verify Atlas health diagnostics do not expose secret URIs."""
    _install_fake_pymongo(monkeypatch, indexes=[{"name": "knowledge_vector_index"}])
    _configure_atlas(app)

    with app.app_context():
        health = atlas_vector_store_health()

    health_text = str(health)
    assert "mongodb+srv://" not in health_text
    assert "password" not in health_text


def test_ensure_atlas_vector_index_creates_missing_index(app, monkeypatch):
    """Verify missing Atlas indexes are created idempotently."""
    fake_collection = _install_fake_pymongo(monkeypatch, indexes=[])
    _configure_atlas(app)

    with app.app_context():
        result = ensure_atlas_vector_index()

    assert result["ok"] is True
    assert result["status"] == "created"
    assert fake_collection.created_indexes[0]["name"] == "knowledge_vector_index"


def test_ensure_atlas_vector_index_reports_ready_index(app, monkeypatch):
    """Verify existing Atlas indexes are not recreated."""
    fake_collection = _install_fake_pymongo(
        monkeypatch,
        indexes=[{"name": "knowledge_vector_index"}],
    )
    _configure_atlas(app)

    with app.app_context():
        result = ensure_atlas_vector_index()

    assert result["ok"] is True
    assert result["status"] == "ready"
    assert fake_collection.created_indexes == []


def test_atlas_vector_store_health_marks_missing_index(app, monkeypatch):
    """Verify missing Atlas indexes degrade health diagnostics."""
    _install_fake_pymongo(monkeypatch, indexes=[])
    _configure_atlas(app)

    with app.app_context():
        health = atlas_vector_store_health()

    assert health["configured"] is True
    assert health["connected"] is True
    assert health["index_ready"] is False
    assert health["ok"] is False


def test_probe_atlas_vector_search_runs_vector_stage(app, monkeypatch):
    """Verify the smoke probe executes a lightweight vector search."""
    fake_collection = _install_fake_pymongo(
        monkeypatch,
        indexes=[{"name": "knowledge_vector_index"}],
    )
    _configure_atlas(app)

    with app.app_context():
        result = probe_atlas_vector_search()

    assert result["ok"] is True
    assert fake_collection.pipelines
    assert "$vectorSearch" in fake_collection.pipelines[0][0]


def _configure_atlas(app, uri="mongodb+srv://user:password@example.mongodb.net"):
    """Configure Atlas settings for tests without using a real network."""
    app.config["RAG_VECTOR_STORE"] = "mongodb_atlas"
    app.config["MONGODB_ATLAS_URI"] = uri
    app.config["MONGODB_ATLAS_DATABASE"] = "maintenance_ai"
    app.config["MONGODB_ATLAS_VECTOR_COLLECTION"] = "knowledge_vectors"
    app.config["MONGODB_ATLAS_VECTOR_INDEX"] = "knowledge_vector_index"
    app.config["MONGODB_ATLAS_TIMEOUT_MS"] = 100
    app.config["EMBEDDING_PROVIDER"] = "openai"
    app.config["OPENAI_EMBEDDING_MODEL"] = "text-embedding-3-small"
    app.config["RAG_EMBEDDING_DIMENSIONS"] = 1536


def _install_fake_pymongo(monkeypatch, indexes=None):
    """Install a fake pymongo module and return its collection double."""
    fake_collection = _FakeAtlasCollection(indexes=indexes or [])

    class FakeDatabase:
        """Minimal fake MongoDB database."""

        def __getitem__(self, _collection_name):
            return fake_collection

    class FakeAdmin:
        """Minimal fake MongoDB admin database."""

        def command(self, _command_name):
            return {"ok": 1}

    class FakeClient:
        """Minimal fake MongoClient."""

        admin = FakeAdmin()

        def __init__(self, *_args, **_kwargs):
            """Initialize the fake client."""

        def __getitem__(self, _database_name):
            return FakeDatabase()

    pymongo_module = ModuleType("pymongo")
    pymongo_module.MongoClient = FakeClient
    monkeypatch.setitem(sys.modules, "pymongo", pymongo_module)
    return fake_collection


class _FakeAtlasCollection:
    """In-memory collection double for Atlas health tests."""

    def __init__(self, indexes=None, name="knowledge_vectors"):
        self.name = name
        self.indexes = list(indexes or [])
        self.created_indexes = []
        self.pipelines = []
        self.database = _FakeAtlasDatabase([self])

    def list_search_indexes(self):
        return list(self.indexes)

    def create_search_index(self, definition):
        payload = _normalize_search_index_payload(definition)
        self.created_indexes.append(payload)
        self.indexes.append({"name": payload["name"]})
        return payload["name"]

    def aggregate(self, pipeline):
        self.pipelines.append(pipeline)
        return []


class _FakeAtlasDatabase:
    """Minimal fake MongoDB database for collection provisioning tests."""

    def __init__(self, collections):
        self._collections = {collection.name: collection for collection in collections}

    def list_collection_names(self):
        return list(self._collections)

    def create_collection(self, name):
        collection = _FakeAtlasCollection()
        collection.name = name
        collection.database = self
        self._collections[name] = collection
        return collection


def _normalize_search_index_payload(definition):
    """Return a dict payload from pymongo SearchIndexModel or legacy dict input."""
    if isinstance(definition, dict):
        return definition
    document = getattr(definition, "document", None)
    if isinstance(document, dict):
        return document
    return {
        "name": getattr(definition, "name", ""),
        "definition": getattr(definition, "definition", {}),
    }
