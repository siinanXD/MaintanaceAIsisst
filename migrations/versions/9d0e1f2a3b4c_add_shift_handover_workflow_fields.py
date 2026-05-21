"""Add structured shift handover workflow fields.

Revision ID: 9d0e1f2a3b4c
Revises: 8c9d0e1f2a3b
Create Date: 2026-05-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "9d0e1f2a3b4c"
down_revision = "8c9d0e1f2a3b"
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
    """Add one column when the target table exists and the column is absent."""
    if _table_exists(table_name) and column.name not in _column_names(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(column)


def _drop_column_if_exists(table_name, column_name):
    """Drop one column when the target table exists and the column is present."""
    if _table_exists(table_name) and column_name in _column_names(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column(column_name)


def _create_index_if_missing(table_name, index_name, columns):
    """Create one index when the table exists and index is missing."""
    if _table_exists(table_name) and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, list(columns))


def _drop_index_if_exists(table_name, index_name):
    """Drop one index when the table exists and index is present."""
    if _table_exists(table_name) and index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade():
    """Add structured operational fields to shift handover records."""
    columns = (
        sa.Column("area", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("machine_id", sa.Integer(), nullable=True),
        sa.Column("previous_shift", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("next_shift", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("production_status", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("machine_status", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("safety_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("material_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("responsible_employee", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("problem_category", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("cause", sa.Text(), nullable=False, server_default=""),
        sa.Column("action_taken", sa.Text(), nullable=False, server_default=""),
        sa.Column("duration_minutes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("follow_up_task", sa.Text(), nullable=False, server_default=""),
        sa.Column("involved_employees", sa.Text(), nullable=False, server_default=""),
        sa.Column("confirmed", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    for column in columns:
        _add_column_if_missing("shift_handover", column)
    _create_index_if_missing(
        "shift_handover",
        "ix_shift_handover_machine_date",
        ["machine_id", "shift_date"],
    )


def downgrade():
    """Remove structured operational fields from shift handover records."""
    _drop_index_if_exists("shift_handover", "ix_shift_handover_machine_date")
    for column_name in (
        "confirmed",
        "involved_employees",
        "follow_up_task",
        "duration_minutes",
        "action_taken",
        "cause",
        "problem_category",
        "responsible_employee",
        "material_notes",
        "safety_notes",
        "machine_status",
        "production_status",
        "next_shift",
        "previous_shift",
        "machine_id",
        "area",
    ):
        _drop_column_if_exists("shift_handover", column_name)
