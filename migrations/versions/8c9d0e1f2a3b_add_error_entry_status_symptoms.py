"""Add error entry status and symptoms.

Revision ID: 8c9d0e1f2a3b
Revises: 7b8c9d0e1f2a
Create Date: 2026-05-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "8c9d0e1f2a3b"
down_revision = "7b8c9d0e1f2a"
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
    """Add structured lifecycle fields to error catalog entries."""
    _add_column_if_missing(
        "error_entry",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("symptoms", sa.Text(), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "error_entry",
        sa.Column("closed_at", sa.DateTime(), nullable=True),
    )
    _create_index_if_missing("error_entry", "ix_error_entry_status", ["status"])


def downgrade():
    """Remove structured lifecycle fields from error catalog entries."""
    _drop_index_if_exists("error_entry", "ix_error_entry_status")
    _drop_column_if_exists("error_entry", "closed_at")
    _drop_column_if_exists("error_entry", "symptoms")
    _drop_column_if_exists("error_entry", "status")
