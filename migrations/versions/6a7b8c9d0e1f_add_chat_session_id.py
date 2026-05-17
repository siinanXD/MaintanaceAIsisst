"""Add chat session identifiers.

Revision ID: 6a7b8c9d0e1f
Revises: 5f6a7b8c9d0e
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "6a7b8c9d0e1f"
down_revision = "5f6a7b8c9d0e"
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


def _create_index_if_missing(index_name, table_name, columns):
    """Create an index only when it is missing."""
    if not _table_exists(table_name):
        return
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_present(index_name, table_name):
    """Drop an index only when it exists."""
    if not _table_exists(table_name):
        return
    if index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade():
    """Add optional chat session identifiers for contextual memory."""
    _add_column_if_missing(
        "chat_message",
        sa.Column("session_id", sa.String(length=120), nullable=False, server_default=""),
    )
    _create_index_if_missing(
        "ix_chat_message_user_session_created",
        "chat_message",
        ["user_id", "session_id", "created_at"],
    )


def downgrade():
    """Remove chat session identifiers."""
    _drop_index_if_present("ix_chat_message_user_session_created", "chat_message")
    _drop_column_if_present("chat_message", "session_id")
