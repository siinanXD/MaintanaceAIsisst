"""Extend AI feedback links.

Revision ID: 1b2c3d4e5f6a
Revises: 0a1b2c3d4e5f
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "1b2c3d4e5f6a"
down_revision = "0a1b2c3d4e5f"
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
    """Add chat, audit, source, and review metadata to AI feedback."""
    if not _table_exists("ai_feedback"):
        return

    _add_column_if_missing("ai_feedback", sa.Column("chat_message_id", sa.Integer()))
    _add_column_if_missing("ai_feedback", sa.Column("audit_event_id", sa.Integer()))
    _add_column_if_missing(
        "ai_feedback",
        sa.Column("response_type", sa.String(length=80), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "ai_feedback",
        sa.Column("sources_json", sa.Text(), nullable=False, server_default="[]"),
    )
    _add_column_if_missing(
        "ai_feedback",
        sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_feedback",
        sa.Column("review_status", sa.String(length=40), nullable=False, server_default="open"),
    )
    _create_index_if_missing(
        "ix_ai_feedback_user_created",
        "ai_feedback",
        ["user_id", "created_at"],
    )
    _create_index_if_missing(
        "ix_ai_feedback_rating_created",
        "ai_feedback",
        ["rating", "created_at"],
    )
    _create_index_if_missing(
        "ix_ai_feedback_review_status",
        "ai_feedback",
        ["review_status"],
    )


def downgrade():
    """Remove extended AI feedback metadata."""
    if not _table_exists("ai_feedback"):
        return
    for index_name in (
        "ix_ai_feedback_review_status",
        "ix_ai_feedback_rating_created",
        "ix_ai_feedback_user_created",
    ):
        if index_name in _index_names("ai_feedback"):
            op.drop_index(index_name, table_name="ai_feedback")
    for column_name in (
        "review_status",
        "source_count",
        "sources_json",
        "response_type",
        "audit_event_id",
        "chat_message_id",
    ):
        if column_name in _column_names("ai_feedback"):
            op.drop_column("ai_feedback", column_name)
