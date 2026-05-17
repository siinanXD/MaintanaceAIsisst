"""Add AI confidence scoring metadata.

Revision ID: 3d4e5f6a7b8c
Revises: 2c3d4e5f6a7b
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "3d4e5f6a7b8c"
down_revision = "2c3d4e5f6a7b"
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
    """Add optional confidence fields to chat history and audit events."""
    for table_name in ("chat_message", "ai_audit_event"):
        _add_column_if_missing(table_name, sa.Column("confidence_score", sa.Integer()))
        _add_column_if_missing(
            table_name,
            sa.Column(
                "confidence_level",
                sa.String(length=40),
                nullable=False,
                server_default="",
            ),
        )


def downgrade():
    """Remove optional confidence fields from chat history and audit events."""
    for table_name in ("chat_message", "ai_audit_event"):
        _drop_column_if_present(table_name, "confidence_level")
        _drop_column_if_present(table_name, "confidence_score")
