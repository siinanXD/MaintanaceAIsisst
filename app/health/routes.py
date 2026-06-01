"""Health check API routes."""

from flask import Blueprint, current_app, jsonify
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Employee, EmployeeDocument, ErrorEntry, Role, Task
from app.responses import success_response
from app.security import roles_required
from app.services.ai_service import ai_api_key_configured, ai_provider_status
from app.services.database_schema_service import database_schema_status
from app.services.embedding_service import embedding_provider_status
from app.services.knowledge_service import knowledge_index_status
from app.services.operations_metrics_service import operations_metrics

health_bp = Blueprint("health", __name__)
public_health_bp = Blueprint("public_health", __name__)


@public_health_bp.get("/health")
def health_check():
    """Return a minimal unauthenticated health response for probes."""
    return jsonify({"status": "ok"})


@public_health_bp.get("/health/live")
def liveness_check():
    """Return a minimal liveness response for container probes."""
    return jsonify({"status": "ok"})


@public_health_bp.get("/health/ready")
def readiness_check():
    """Return readiness diagnostics for database, AI config, and RAG index."""
    database = database_probe()
    ai = ai_probe()
    schema = database_schema_status() if database["ok"] else {"ok": False}
    database["schema"] = schema
    database["ok"] = bool(database["ok"] and schema["ok"])
    rag = rag_probe() if database["ok"] else {"ok": False, "reason": "database_unavailable"}
    components = {
        "database": database,
        "ai": ai,
        "rag": rag,
    }
    degraded_components = _degraded_components(components)
    status_code = 200 if database["ok"] else 503
    status = "ok" if database["ok"] else "error"
    return (
        jsonify(
            {
                "status": status,
                "ready": not degraded_components,
                "degraded_components": degraded_components,
                "components": components,
            }
        ),
        status_code,
    )


@health_bp.get("/database")
@roles_required(Role.IT)
def database_health():
    """Return sensitive database diagnostics for IT and master admins."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    database_rows = []
    if db.engine.url.get_backend_name() == "sqlite":
        with db.engine.connect() as connection:
            database_rows = connection.execute(text("PRAGMA database_list")).mappings().all()

    return jsonify(
        {
            "database_uri": current_app.config["SQLALCHEMY_DATABASE_URI"],
            "schema": database_schema_status(),
            "sqlite_files": [dict(row) for row in database_rows],
            "tables": table_names,
            "counts": {
                "tasks": Task.query.count(),
                "errors": ErrorEntry.query.count(),
                "employees": Employee.query.count(),
                "employee_documents": EmployeeDocument.query.count(),
            },
        }
    )


@health_bp.get("/operations")
@roles_required(Role.MASTER_ADMIN)
def operations_health():
    """Return authenticated production operations metrics for administrators."""
    return success_response(operations_metrics(), message="Operations metrics loaded")


def database_probe():
    """Return database readiness metadata without exposing secrets."""
    try:
        with db.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "ok": True,
            "dialect": db.engine.url.get_backend_name(),
            "driver": db.engine.url.get_driver_name(),
        }
    except SQLAlchemyError as exc:
        current_app.logger.warning("database_health_failed error=%s", exc.__class__.__name__)
        return {
            "ok": False,
            "dialect": db.engine.url.get_backend_name(),
            "driver": db.engine.url.get_driver_name(),
            "error": exc.__class__.__name__,
        }


def _degraded_components(components):
    """Return component names whose readiness probe is not ok."""
    return [name for name, payload in components.items() if not bool((payload or {}).get("ok"))]


def ai_probe():
    """Return AI provider configuration readiness without external API calls."""
    provider = str(current_app.config.get("AI_PROVIDER", "mock")).lower()
    api_key_configured = ai_api_key_configured(current_app.config)
    provider_status = ai_provider_status(provider, api_key_configured)
    embedding_status = embedding_provider_status(current_app.config)
    reason = provider_status["reason"] or _embedding_readiness_reason(embedding_status)
    action = _ai_readiness_action(provider_status, embedding_status)
    payload = {
        "ok": bool(provider_status["ready"] and embedding_status["ready"]),
        "provider": provider,
        "api_key_configured": api_key_configured,
        "mode": provider_status["mode"],
        "reason": reason,
        "effective_provider": provider_status.get("effective_provider", provider),
        "configuration_action": action["configuration_action"],
        "recommended_action": action["recommended_action"],
        "embedding_provider": embedding_status,
    }
    if "base_url_configured" in provider_status:
        payload["base_url_configured"] = provider_status["base_url_configured"]
    return payload


def _ai_readiness_action(provider_status, embedding_status):
    """Return the remediation action for the degraded AI readiness component."""
    if not provider_status.get("ready", False):
        return {
            "configuration_action": provider_status.get(
                "configuration_action",
                "review_provider_configuration",
            ),
            "recommended_action": provider_status.get("recommended_action", ""),
        }
    if not embedding_status.get("ready", False):
        return {
            "configuration_action": embedding_status.get(
                "configuration_action",
                "review_embedding_provider_configuration",
            ),
            "recommended_action": embedding_status.get("recommended_action", ""),
        }
    return {
        "configuration_action": "none",
        "recommended_action": "AI- und Embedding-Provider sind einsatzbereit.",
    }


def _embedding_readiness_reason(embedding_status):
    """Return a top-level AI readiness reason for embedding-only failures."""
    if embedding_status.get("ready", False):
        return ""
    reason = str(embedding_status.get("reason") or "not_ready")
    return f"embedding_{reason}"


def _rag_readiness_reason(status):
    """Return a compact RAG readiness reason without exposing document content."""
    reasons = status.get("readiness_reasons") or []
    if reasons:
        return str(reasons[0])[:180]
    return "rag_not_ready"


def rag_probe():
    """Return RAG index readiness metadata."""
    try:
        status = knowledge_index_status()
        diagnostics = status["diagnostics"]
        rag_ready = bool(diagnostics["ready"])
        return {
            "ok": rag_ready,
            "enabled": diagnostics["rag_enabled"],
            "ready": diagnostics["ready"],
            "reason": "" if rag_ready else _rag_readiness_reason(status),
            "documents": status["documents"],
            "indexed": status["indexed"],
            "stale": status["stale"],
            "pending": status["pending"],
            "chunks": status["chunks"],
            "vector_store": diagnostics["vector_store"],
            "embedding_provider": diagnostics["embedding_provider"],
        }
    except SQLAlchemyError as exc:
        current_app.logger.warning("rag_health_failed error=%s", exc.__class__.__name__)
        return {
            "ok": False,
            "reason": "database_unavailable",
            "error": exc.__class__.__name__,
        }
