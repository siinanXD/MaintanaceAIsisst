"""Add shift planning preview coverage state.

Revision ID: 2f3a4b5c6d8e
Revises: b1c2d3e4f5a6
Create Date: 2026-05-22 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "2f3a4b5c6d8e"
down_revision = "b1c2d3e4f5a6"
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


def _add_column_if_missing(table_name, column):
    """Add a column only when it is missing."""
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _create_index_if_missing(name, table_name, columns):
    """Create an index only when it is missing."""
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns)


def upgrade():
    """Add employee rotation state and persisted undercoverage slots."""
    _add_column_if_missing(
        "employee",
        sa.Column("last_shift", sa.String(length=120), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "employee",
        sa.Column("next_shift", sa.String(length=120), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "employee",
        sa.Column("rotation_state_updated_at", sa.DateTime(), nullable=True),
    )

    if not _table_exists("shift_plan_coverage_slot"):
        op.create_table(
            "shift_plan_coverage_slot",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("plan_id", sa.Integer(), nullable=False),
            sa.Column("machine_id", sa.Integer(), nullable=True),
            sa.Column("work_date", sa.Date(), nullable=False),
            sa.Column("shift", sa.String(length=80), nullable=False),
            sa.Column("required", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("assigned", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("missing", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("reason", sa.String(length=240), nullable=False, server_default=""),
            sa.Column("suggestion", sa.String(length=240), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
            sa.ForeignKeyConstraint(["plan_id"], ["shift_plan.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_shift_plan_coverage_machine_date",
        "shift_plan_coverage_slot",
        ["machine_id", "work_date"],
    )
    _create_index_if_missing(
        "ix_shift_plan_coverage_plan_date",
        "shift_plan_coverage_slot",
        ["plan_id", "work_date"],
    )


def downgrade():
    """Remove employee rotation state and persisted undercoverage slots."""
    if _table_exists("shift_plan_coverage_slot"):
        op.drop_table("shift_plan_coverage_slot")
    for column_name in ("rotation_state_updated_at", "next_shift", "last_shift"):
        if column_name in _column_names("employee"):
            op.drop_column("employee", column_name)
