"""Add pgvector embeddings to knowledge chunks.

Revision ID: 3f4a5b6c7d8e
Revises: 2f3a4b5c6d8e
Create Date: 2026-05-26 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - migration environment should install pgvector
    Vector = None

revision = "3f4a5b6c7d8e"
down_revision = "2f3a4b5c6d8e"
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


def _embedding_column_type():
    """Return the best available migration type for knowledge embeddings."""
    if Vector is None:
        return sa.JSON()
    return Vector()


def upgrade():
    """Add stored embeddings for PostgreSQL pgvector retrieval."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    if not _table_exists("knowledge_chunk"):
        return
    if "embedding" not in _column_names("knowledge_chunk"):
        op.add_column(
            "knowledge_chunk",
            sa.Column("embedding", _embedding_column_type(), nullable=True),
        )


def downgrade():
    """Remove stored embeddings from knowledge chunks."""
    if not _table_exists("knowledge_chunk"):
        return
    if "embedding" in _column_names("knowledge_chunk"):
        op.drop_column("knowledge_chunk", "embedding")
