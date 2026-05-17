"""Add technical entity storage to knowledge chunks.

Revision ID: 2c3d4e5f6a7b
Revises: 1b2c3d4e5f6a
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "2c3d4e5f6a7b"
down_revision = "1b2c3d4e5f6a"
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


def upgrade():
    """Add serialized entity metadata for chunk-level retrieval signals."""
    if not _table_exists("knowledge_chunk"):
        return
    if "entities_json" not in _column_names("knowledge_chunk"):
        op.add_column(
            "knowledge_chunk",
            sa.Column("entities_json", sa.Text(), nullable=False, server_default="{}"),
        )


def downgrade():
    """Remove serialized entity metadata from knowledge chunks."""
    if not _table_exists("knowledge_chunk"):
        return
    if "entities_json" in _column_names("knowledge_chunk"):
        op.drop_column("knowledge_chunk", "entities_json")
