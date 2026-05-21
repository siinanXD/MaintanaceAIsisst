"""Add operational vacation planning fields.

Revision ID: a0b1c2d3e4f5
Revises: 9d0e1f2a3b4c
Create Date: 2026-05-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "a0b1c2d3e4f5"
down_revision = "9d0e1f2a3b4c"
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
    """Add representative, cancellation and impact fields to vacation requests."""
    columns = (
        sa.Column("cancelled_by", sa.Integer(), nullable=True),
        sa.Column("representative_employee_id", sa.Integer(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        sa.Column("shift_type", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("reason", sa.String(length=160), nullable=False, server_default=""),
        sa.Column("impact_level", sa.String(length=40), nullable=False, server_default="ok"),
        sa.Column("impact_summary", sa.Text(), nullable=False, server_default=""),
    )
    for column in columns:
        _add_column_if_missing("vacation_request", column)
    _create_index_if_missing(
        "vacation_request",
        "ix_vacation_request_representative",
        ["representative_employee_id", "start_date"],
    )


def downgrade():
    """Remove representative, cancellation and impact fields from vacation requests."""
    _drop_index_if_exists("vacation_request", "ix_vacation_request_representative")
    for column_name in (
        "impact_summary",
        "impact_level",
        "reason",
        "shift_type",
        "cancelled_at",
        "representative_employee_id",
        "cancelled_by",
    ):
        _drop_column_if_exists("vacation_request", column_name)
