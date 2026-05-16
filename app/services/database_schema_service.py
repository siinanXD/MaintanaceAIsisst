"""Database schema diagnostics for runtime readiness checks."""

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

MIGRATION_COMMAND = "flask --app run:app db upgrade"

REQUIRED_TABLE_COLUMNS = {
    "generated_document": {
        "status",
        "current_version_id",
        "summary",
        "summary_status",
        "approved_by",
        "approved_at",
        "approval_comment",
        "rejected_by",
        "rejected_at",
        "rejection_comment",
    },
    "chat_message": {
        "response_type",
        "diagnostics_json",
        "source_count",
        "audit_event_id",
    },
    "knowledge_document": {
        "source_type",
        "source_id",
        "title",
        "status",
        "is_public",
        "chunk_count",
        "error_message",
    },
    "knowledge_chunk": {
        "document_id",
        "chunk_index",
        "text",
        "token_text",
    },
    "background_job": {
        "job_type",
        "status",
        "payload_json",
        "result_json",
        "error_message",
        "attempts",
        "max_attempts",
        "locked_at",
        "started_at",
        "finished_at",
        "created_by",
    },
}


def database_schema_status():
    """Return whether the runtime database has all required AI/RAG columns."""
    try:
        inspector = inspect(db.engine)
        table_names = set(inspector.get_table_names())
        missing_tables = []
        missing_columns = {}

        for table_name, expected_columns in REQUIRED_TABLE_COLUMNS.items():
            if table_name not in table_names:
                missing_tables.append(table_name)
                continue

            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            missing = sorted(expected_columns - existing_columns)
            if missing:
                missing_columns[table_name] = missing

        is_ready = not missing_tables and not missing_columns
        return {
            "ok": is_ready,
            "missing_tables": sorted(missing_tables),
            "missing_columns": missing_columns,
            "migration_command": MIGRATION_COMMAND,
        }
    except SQLAlchemyError as exc:
        return {
            "ok": False,
            "missing_tables": [],
            "missing_columns": {},
            "error": exc.__class__.__name__,
            "migration_command": MIGRATION_COMMAND,
        }


def database_schema_error_payload(schema_status=None):
    """Return a consistent API payload for an outdated database schema."""
    status = schema_status or database_schema_status()
    return {
        "success": False,
        "error": "database_schema_outdated",
        "message": (
            "Database schema is outdated. Run "
            f"`{status['migration_command']}` and restart the app."
        ),
        "data": status,
    }
