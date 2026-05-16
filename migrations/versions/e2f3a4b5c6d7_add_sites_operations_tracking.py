"""Add sites and operations tracking.

Revision ID: e2f3a4b5c6d7
Revises: d1e2f3a4b5c6
Create Date: 2026-05-16 00:00:00.000000

"""

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return whether a table exists in the current migration connection."""
    return table_name in inspect(op.get_bind()).get_table_names()


def _column_names(table_name):
    """Return existing column names for a table."""
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _index_names(table_name):
    """Return existing index names for a table."""
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(table_name, index_name, columns):
    """Create one index when the table exists and index is missing."""
    if _table_exists(table_name) and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, list(columns))


def _drop_index_if_exists(table_name, index_name):
    """Drop one index when the table exists and index is present."""
    if _table_exists(table_name) and index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def _add_column_if_missing(table_name, column):
    """Add a column inside a batch operation when it does not exist."""
    if _table_exists(table_name) and column.name not in _column_names(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(column)


def _drop_column_if_exists(table_name, column_name):
    """Drop a column inside a batch operation when it exists."""
    if _table_exists(table_name) and column_name in _column_names(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column(column_name)


def _ensure_default_site():
    """Insert the default site and return its id."""
    connection = op.get_bind()
    row = connection.execute(
        sa.text("SELECT id FROM site WHERE code = :code"),
        {"code": "werk-1"},
    ).first()
    if row:
        return row[0]
    now = datetime.utcnow()
    connection.execute(
        sa.text(
            "INSERT INTO site (code, name, timezone, is_active, created_at, updated_at) "
            "VALUES (:code, :name, :timezone, :is_active, :created_at, :updated_at)"
        ),
        {
            "code": "werk-1",
            "name": "Werk 1",
            "timezone": "Europe/Berlin",
            "is_active": True,
            "created_at": now,
            "updated_at": now,
        },
    )
    return connection.execute(
        sa.text("SELECT id FROM site WHERE code = :code"),
        {"code": "werk-1"},
    ).scalar()


def upgrade():
    """Create site and operations tables plus additive tracking columns."""
    if not _table_exists("site"):
        op.create_table(
            "site",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("code", sa.String(length=40), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column(
                "timezone",
                sa.String(length=80),
                nullable=False,
                server_default="Europe/Berlin",
            ),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code"),
        )
    _create_index_if_missing("site", "ix_site_is_active", ("is_active",))
    default_site_id = _ensure_default_site()

    _add_column_if_missing("department", sa.Column("site_id", sa.Integer(), nullable=True))
    if _table_exists("department") and "site_id" in _column_names("department"):
        op.get_bind().execute(
            sa.text("UPDATE department SET site_id = :site_id WHERE site_id IS NULL"),
            {"site_id": default_site_id},
        )
    _create_index_if_missing("department", "ix_department_site_id", ("site_id",))
    _create_index_if_missing("department", "ix_department_site_name", ("site_id", "name"))

    _add_column_if_missing(
        "task",
        sa.Column("planned_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "task",
        sa.Column("actual_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "task",
        sa.Column("blocked_reason", sa.String(length=220), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "task",
        sa.Column("reopened_count", sa.Integer(), nullable=False, server_default="0"),
    )

    _add_column_if_missing("machine", sa.Column("site_id", sa.Integer(), nullable=True))
    _add_column_if_missing(
        "machine",
        sa.Column("criticality", sa.String(length=40), nullable=False, server_default="normal"),
    )
    _add_column_if_missing(
        "machine",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="running"),
    )
    _add_column_if_missing("machine", sa.Column("last_downtime_at", sa.DateTime(), nullable=True))
    _create_index_if_missing("machine", "ix_machine_site_id", ("site_id",))

    _add_column_if_missing(
        "inventory_material",
        sa.Column("min_quantity", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "inventory_material",
        sa.Column("criticality", sa.String(length=40), nullable=False, server_default="normal"),
    )
    _add_column_if_missing(
        "inventory_material",
        sa.Column("lead_time_days", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("inventory_material", sa.Column("site_id", sa.Integer(), nullable=True))
    _create_index_if_missing("inventory_material", "ix_inventory_material_site_id", ("site_id",))

    _add_column_if_missing(
        "error_entry",
        sa.Column("severity", sa.String(length=40), nullable=False, server_default="medium"),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("cause_category", sa.String(length=120), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("impact", sa.String(length=160), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("downtime_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("production_loss_minutes", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("repeat_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing("error_entry", sa.Column("last_seen_at", sa.DateTime(), nullable=True))

    _add_column_if_missing("generated_document", sa.Column("quality_score", sa.Integer()))
    _add_column_if_missing(
        "generated_document",
        sa.Column(
            "quality_status",
            sa.String(length=40),
            nullable=False,
            server_default="not_checked",
        ),
    )
    _add_column_if_missing(
        "generated_document",
        sa.Column("quality_checked_at", sa.DateTime(), nullable=True),
    )

    _add_column_if_missing(
        "shift_plan",
        sa.Column("coverage_percent", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "shift_plan",
        sa.Column("conflict_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "shift_plan",
        sa.Column("critical_conflict_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "shift_plan",
        sa.Column("change_count", sa.Integer(), nullable=False, server_default="0"),
    )

    if not _table_exists("operational_event"):
        op.create_table(
            "operational_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("feature", sa.String(length=80), nullable=False),
            sa.Column("entity_type", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("entity_id", sa.Integer(), nullable=True),
            sa.Column("site_id", sa.Integer(), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("machine_id", sa.Integer(), nullable=True),
            sa.Column("task_id", sa.Integer(), nullable=True),
            sa.Column("occurred_at", sa.DateTime(), nullable=False),
            sa.Column("actor_hash", sa.String(length=128), nullable=False, server_default=""),
            sa.Column("actor_role", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("source", sa.String(length=80), nullable=False, server_default="app"),
            sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
            sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
            sa.ForeignKeyConstraint(["site_id"], ["site.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    for index_name, columns in (
        ("ix_operational_event_event_type", ("event_type",)),
        ("ix_operational_event_feature", ("feature",)),
        ("ix_operational_event_site_id", ("site_id",)),
        ("ix_operational_event_department_id", ("department_id",)),
        ("ix_operational_event_machine_id", ("machine_id",)),
        ("ix_operational_event_task_id", ("task_id",)),
        ("ix_operational_event_actor_hash", ("actor_hash",)),
        ("ix_operational_event_occurred_at", ("occurred_at",)),
        ("ix_operational_event_site_time", ("site_id", "occurred_at")),
        ("ix_operational_event_feature_time", ("feature", "occurred_at")),
        ("ix_operational_event_type_time", ("event_type", "occurred_at")),
        ("ix_operational_event_department_time", ("department_id", "occurred_at")),
        ("ix_operational_event_entity", ("entity_type", "entity_id")),
    ):
        _create_index_if_missing("operational_event", index_name, columns)

    if not _table_exists("operational_kpi_aggregate"):
        op.create_table(
            "operational_kpi_aggregate",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("period_type", sa.String(length=20), nullable=False, server_default="day"),
            sa.Column("period_start", sa.Date(), nullable=False),
            sa.Column("site_id", sa.Integer(), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=True),
            sa.Column("feature", sa.String(length=80), nullable=False),
            sa.Column("metric_key", sa.String(length=120), nullable=False),
            sa.Column("metric_value", sa.Float(), nullable=False, server_default="0"),
            sa.Column("metric_unit", sa.String(length=40), nullable=False, server_default="count"),
            sa.Column("dimensions_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
            sa.ForeignKeyConstraint(["site_id"], ["site.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "period_type",
                "period_start",
                "site_id",
                "department_id",
                "feature",
                "metric_key",
                "dimensions_json",
                name="uq_operational_kpi_scope_metric",
            ),
        )
    for index_name, columns in (
        ("ix_operational_kpi_aggregate_period_start", ("period_start",)),
        ("ix_operational_kpi_aggregate_site_id", ("site_id",)),
        ("ix_operational_kpi_aggregate_department_id", ("department_id",)),
        ("ix_operational_kpi_aggregate_feature", ("feature",)),
        ("ix_operational_kpi_aggregate_metric_key", ("metric_key",)),
        ("ix_operational_kpi_scope", ("period_type", "period_start", "site_id", "department_id")),
        ("ix_operational_kpi_feature_metric", ("feature", "metric_key")),
    ):
        _create_index_if_missing("operational_kpi_aggregate", index_name, columns)


def downgrade():
    """Remove operations tracking structures and additive tracking columns."""
    for table_name, index_name in (
        ("operational_kpi_aggregate", "ix_operational_kpi_feature_metric"),
        ("operational_kpi_aggregate", "ix_operational_kpi_scope"),
        ("operational_kpi_aggregate", "ix_operational_kpi_aggregate_metric_key"),
        ("operational_kpi_aggregate", "ix_operational_kpi_aggregate_feature"),
        ("operational_kpi_aggregate", "ix_operational_kpi_aggregate_department_id"),
        ("operational_kpi_aggregate", "ix_operational_kpi_aggregate_site_id"),
        ("operational_kpi_aggregate", "ix_operational_kpi_aggregate_period_start"),
        ("operational_event", "ix_operational_event_entity"),
        ("operational_event", "ix_operational_event_department_time"),
        ("operational_event", "ix_operational_event_type_time"),
        ("operational_event", "ix_operational_event_feature_time"),
        ("operational_event", "ix_operational_event_site_time"),
        ("operational_event", "ix_operational_event_occurred_at"),
        ("operational_event", "ix_operational_event_actor_hash"),
        ("operational_event", "ix_operational_event_task_id"),
        ("operational_event", "ix_operational_event_machine_id"),
        ("operational_event", "ix_operational_event_department_id"),
        ("operational_event", "ix_operational_event_site_id"),
        ("operational_event", "ix_operational_event_feature"),
        ("operational_event", "ix_operational_event_event_type"),
        ("inventory_material", "ix_inventory_material_site_id"),
        ("machine", "ix_machine_site_id"),
        ("department", "ix_department_site_name"),
        ("department", "ix_department_site_id"),
        ("site", "ix_site_is_active"),
    ):
        _drop_index_if_exists(table_name, index_name)

    if _table_exists("operational_kpi_aggregate"):
        op.drop_table("operational_kpi_aggregate")
    if _table_exists("operational_event"):
        op.drop_table("operational_event")

    for column_name in (
        "coverage_percent",
        "conflict_count",
        "critical_conflict_count",
        "change_count",
    ):
        _drop_column_if_exists("shift_plan", column_name)
    for column_name in ("quality_score", "quality_status", "quality_checked_at"):
        _drop_column_if_exists("generated_document", column_name)
    for column_name in (
        "severity",
        "cause_category",
        "impact",
        "downtime_minutes",
        "production_loss_minutes",
        "repeat_count",
        "last_seen_at",
    ):
        _drop_column_if_exists("error_entry", column_name)
    for column_name in ("min_quantity", "criticality", "lead_time_days", "site_id"):
        _drop_column_if_exists("inventory_material", column_name)
    for column_name in ("site_id", "criticality", "status", "last_downtime_at"):
        _drop_column_if_exists("machine", column_name)
    for column_name in ("planned_minutes", "actual_minutes", "blocked_reason", "reopened_count"):
        _drop_column_if_exists("task", column_name)
    _drop_column_if_exists("department", "site_id")
    if _table_exists("site"):
        op.drop_table("site")
