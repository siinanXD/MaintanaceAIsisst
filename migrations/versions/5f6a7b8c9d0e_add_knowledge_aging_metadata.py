"""Add knowledge aging metadata.

Revision ID: 5f6a7b8c9d0e
Revises: 4e5f6a7b8c9d
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "5f6a7b8c9d0e"
down_revision = "4e5f6a7b8c9d"
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


def _add_column_if_missing(table_name, column):
    """Add a column only when it is missing."""
    if not _table_exists(table_name):
        return
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def _drop_column_if_present(table_name, column_name):
    """Drop a column only when the table and column exist."""
    if not _table_exists(table_name):
        return
    if column_name in _column_names(table_name):
        op.drop_column(table_name, column_name)


def upgrade():
    """Add confirmation and aging timestamps to knowledge documents."""
    _add_column_if_missing(
        "knowledge_document",
        sa.Column("last_confirmed_at", sa.DateTime(), nullable=True),
    )
    _add_column_if_missing(
        "knowledge_document",
        sa.Column("confirmation_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "knowledge_document",
        sa.Column("aging_checked_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    """Remove knowledge aging metadata."""
    _drop_column_if_present("knowledge_document", "aging_checked_at")
    _drop_column_if_present("knowledge_document", "confirmation_count")
    _drop_column_if_present("knowledge_document", "last_confirmed_at")
