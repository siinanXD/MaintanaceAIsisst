"""Tests for the central maintenance_ai MongoDB bootstrap service."""

import sys
from types import ModuleType

from app.services.mongodb_service import (
    MAINTENANCE_MONGODB_COLLECTIONS,
    ensure_maintenance_mongodb_ready,
    get_mongodb_database,
    mongodb_database_name,
    mongodb_is_configured,
    mongodb_uri,
    reset_mongodb_client_cache,
)


def test_mongodb_is_not_configured_without_uri():
    """Verify bootstrap is skipped when no MongoDB URI is configured."""
    assert mongodb_is_configured({}) is False
    result = ensure_maintenance_mongodb_ready({})
    assert result["skipped"] is True
    assert result["configured"] is False


def test_mongodb_uri_prefers_mongodb_uri_over_atlas_alias(app):
    """Verify the maintenance URI helper prefers MONGODB_URI."""
    with app.app_context():
        app.config["MONGODB_URI"] = "mongodb://example.test:27017"
        app.config["MONGODB_ATLAS_URI"] = "mongodb://atlas.example.test:27017"
        assert mongodb_uri() == "mongodb://example.test:27017"


def test_mongodb_database_name_defaults_to_maintenance_ai(app):
    """Verify the configured database name defaults to maintenance_ai."""
    with app.app_context():
        app.config.pop("MONGODB_DB_NAME", None)
        app.config.pop("MONGODB_ATLAS_DATABASE", None)
        assert mongodb_database_name() == "maintenance_ai"


def test_ensure_maintenance_mongodb_ready_creates_collections_and_indexes(app, monkeypatch):
    """Verify missing collections and indexes are created in maintenance_ai only."""
    fake_state = _install_fake_mongodb(monkeypatch)
    with app.app_context():
        app.config["MONGODB_URI"] = "mongodb://127.0.0.1:27017"
        app.config["MONGODB_DB_NAME"] = "maintenance_ai"
        result = ensure_maintenance_mongodb_ready()

    assert result["ok"] is True
    assert result["database"] == "maintenance_ai"
    assert set(fake_state["created_collections"]) == set(MAINTENANCE_MONGODB_COLLECTIONS)
    assert "users.users_email_unique" in fake_state["created_indexes"]
    assert "tasks.tasks_status" in fake_state["created_indexes"]
    assert "audit_logs.audit_logs_created_at" in fake_state["created_indexes"]
    assert fake_state["touched_databases"] == {"maintenance_ai"}


def test_ensure_maintenance_mongodb_ready_is_idempotent(app, monkeypatch):
    """Verify repeated bootstrap calls do not recreate existing collections or indexes."""
    _install_fake_mongodb(monkeypatch)
    with app.app_context():
        app.config["MONGODB_URI"] = "mongodb://127.0.0.1:27017"
        app.config["MONGODB_DB_NAME"] = "maintenance_ai"
        first = ensure_maintenance_mongodb_ready()
        second = ensure_maintenance_mongodb_ready()

    assert first["collections_created"]
    assert second["collections_created"] == []
    assert second["indexes_created"] == []


def test_get_mongodb_database_never_opens_other_databases(app, monkeypatch):
    """Verify the service only returns the configured maintenance database."""
    fake_state = _install_fake_mongodb(monkeypatch)
    with app.app_context():
        app.config["MONGODB_URI"] = "mongodb://127.0.0.1:27017"
        app.config["MONGODB_DB_NAME"] = "maintenance_ai"
        database = get_mongodb_database()
        database["users"].insert_one({"email": "demo@example.test"})

    assert fake_state["touched_databases"] == {"maintenance_ai"}
    assert "ai_email" not in fake_state["touched_databases"]


def _install_fake_mongodb(monkeypatch):
    """Install a fake pymongo client that tracks database and index operations."""
    fake_state = {
        "databases": {},
        "created_collections": [],
        "created_indexes": [],
        "touched_databases": set(),
    }

    class FakeCollection:
        """In-memory MongoDB collection double."""

        def __init__(self, database, name):
            self.database = database
            self.name = name
            self._indexes = {}

        def create_index(self, keys, name, unique=False):
            self._indexes[name] = {"keys": keys, "unique": unique}
            fake_state["created_indexes"].append(f"{self.name}.{name}")

        def index_information(self):
            return dict(self._indexes)

        def insert_one(self, document):
            return {"inserted_id": document.get("_id", "1")}

    class FakeDatabase:
        """In-memory MongoDB database double."""

        def __init__(self, name):
            self.name = name
            self._collections = {}

        def list_collection_names(self):
            return list(self._collections)

        def create_collection(self, name):
            collection = FakeCollection(self, name)
            self._collections[name] = collection
            fake_state["created_collections"].append(name)
            return collection

        def __getitem__(self, name):
            if name not in self._collections:
                self._collections[name] = FakeCollection(self, name)
            return self._collections[name]

    class FakeAdmin:
        """Minimal admin database double."""

        def command(self, _command_name):
            return {"ok": 1}

    class FakeClient:
        """Minimal MongoClient double."""

        admin = FakeAdmin()

        def __init__(self, *_args, **_kwargs):
            pass

        def __getitem__(self, database_name):
            fake_state["touched_databases"].add(database_name)
            if database_name not in fake_state["databases"]:
                fake_state["databases"][database_name] = FakeDatabase(database_name)
            return fake_state["databases"][database_name]

        def close(self):
            return None

    pymongo_module = ModuleType("pymongo")
    pymongo_module.MongoClient = FakeClient
    monkeypatch.setitem(sys.modules, "pymongo", pymongo_module)
    reset_mongodb_client_cache()
    return fake_state
