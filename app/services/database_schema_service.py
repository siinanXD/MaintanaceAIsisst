"""Database schema diagnostics for runtime readiness checks."""

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db

MIGRATION_COMMAND = "flask --app run:app db upgrade"

REQUIRED_TABLE_COLUMNS = {
    "site": {
        "code",
        "name",
        "timezone",
        "is_active",
    },
    "department": {
        "site_id",
    },
    "task": {
        "planned_minutes",
        "actual_minutes",
        "blocked_reason",
        "reopened_count",
    },
    "machine": {
        "site_id",
        "criticality",
        "status",
        "last_downtime_at",
    },
    "inventory_material": {
        "min_quantity",
        "criticality",
        "lead_time_days",
        "site_id",
    },
    "error_entry": {
        "severity",
        "cause_category",
        "impact",
        "downtime_minutes",
        "production_loss_minutes",
        "repeat_count",
        "last_seen_at",
    },
    "generated_document": {
        "quality_score",
        "quality_status",
        "quality_checked_at",
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
    "assistant_training_entry": {
        "title",
        "question",
        "answer",
        "keywords",
        "category",
        "department",
        "is_active",
        "priority",
        "created_by",
    },
    "operational_event": {
        "event_type",
        "feature",
        "entity_type",
        "entity_id",
        "site_id",
        "department_id",
        "machine_id",
        "task_id",
        "occurred_at",
        "actor_hash",
        "actor_role",
        "source",
        "metadata_json",
    },
    "operational_kpi_aggregate": {
        "period_type",
        "period_start",
        "site_id",
        "department_id",
        "feature",
        "metric_key",
        "metric_value",
        "metric_unit",
        "dimensions_json",
    },
}

LOCAL_DEV_SCHEMA_COLUMNS = {
    "department": (
        sa.Column("site_id", sa.Integer(), nullable=True),
    ),
    "task": (
        sa.Column("planned_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("actual_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked_reason", sa.String(length=220), nullable=False, server_default=""),
        sa.Column("reopened_count", sa.Integer(), nullable=False, server_default="0"),
    ),
    "machine": (
        sa.Column("site_id", sa.Integer(), nullable=True),
        sa.Column("criticality", sa.String(length=40), nullable=False, server_default="normal"),
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
        sa.Column("last_downtime_at", sa.DateTime(), nullable=True),
    ),
    "inventory_material": (
        sa.Column("min_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("criticality", sa.String(length=40), nullable=False, server_default="normal"),
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("site_id", sa.Integer(), nullable=True),
    ),
    "error_entry": (
        sa.Column("severity", sa.String(length=40), nullable=False, server_default="medium"),
        sa.Column("cause_category", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("impact", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("downtime_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "production_loss_minutes",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("repeat_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
    ),
    "generated_document": (
        sa.Column("quality_score", sa.Integer(), nullable=True),
        sa.Column(
            "quality_status",
            sa.String(length=40),
            nullable=False,
            server_default="not_checked",
        ),
        sa.Column("quality_checked_at", sa.DateTime(), nullable=True),
    ),
    "shift_plan": (
        sa.Column("coverage_percent", sa.Float(), nullable=False, server_default="0"),
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "critical_conflict_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("change_count", sa.Integer(), nullable=False, server_default="0"),
    ),
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


def ensure_local_development_schema():
    """Add safe additive columns for local auto-created development databases."""
    inspector = inspect(db.engine)
    table_names = set(inspector.get_table_names())
    with db.engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        for table_name, columns in LOCAL_DEV_SCHEMA_COLUMNS.items():
            if table_name not in table_names:
                continue
            existing_columns = {
                column["name"] for column in inspector.get_columns(table_name)
            }
            for column in columns:
                if column.name in existing_columns:
                    continue
                operations.add_column(table_name, clone_column(column))


def clone_column(column):
    """Return a new SQLAlchemy column for imperative ALTER TABLE operations."""
    server_default = column.server_default.arg if column.server_default is not None else None
    return sa.Column(
        column.name,
        column.type,
        nullable=column.nullable,
        server_default=server_default,
    )


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
