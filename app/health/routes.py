"""Health check API routes."""

from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Employee, EmployeeDocument, ErrorEntry, Role, Task
from app.responses import success_response
from app.security import roles_required
from app.services.database_schema_service import database_schema_status
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
    status_code = 200 if database["ok"] else 503
    status = "ok" if database["ok"] else "error"
    return (
        jsonify(
            {
                "status": status,
                "components": {
                    "database": database,
                    "ai": ai,
                    "rag": rag,
                },
            }
        ),
        status_code,
    )


@health_bp.get("/database")
@jwt_required()
def database_health():
    """Return authenticated database diagnostics for administrators and tests."""
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


def ai_probe():
    """Return AI provider configuration readiness without external API calls."""
    provider = str(current_app.config.get("AI_PROVIDER", "mock")).lower()
    api_key_configured = bool(current_app.config.get("OPENAI_API_KEY"))
    requires_key = provider in {"openai", "gemini"}
    return {
        "ok": bool(api_key_configured or not requires_key),
        "provider": provider,
        "api_key_configured": api_key_configured,
        "mode": "external" if requires_key and api_key_configured else "local_fallback",
    }


def rag_probe():
    """Return RAG index readiness metadata."""
    try:
        status = knowledge_index_status()
        diagnostics = status["diagnostics"]
        return {
            "ok": bool(diagnostics["rag_enabled"]),
            "enabled": diagnostics["rag_enabled"],
            "ready": diagnostics["ready"],
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
