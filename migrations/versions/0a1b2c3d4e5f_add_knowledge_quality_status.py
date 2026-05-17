"""Add knowledge quality status.

Revision ID: 0a1b2c3d4e5f
Revises: f8a9b0c1d2e3
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "0a1b2c3d4e5f"
down_revision = "f8a9b0c1d2e3"
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


def upgrade():
    """Add a separate quality workflow status for knowledge documents."""
    if not _table_exists("knowledge_document"):
        return

    if "quality_status" not in _column_names("knowledge_document"):
        op.add_column(
            "knowledge_document",
            sa.Column(
                "quality_status",
                sa.String(length=40),
                nullable=False,
                server_default="draft",
            ),
        )

    op.execute(
        sa.text(
            "UPDATE knowledge_document "
            "SET quality_status = 'ai_suggested' "
            "WHERE source_type = 'generated_document' "
            "AND quality_status = 'draft'"
        )
    )

    if "ix_knowledge_document_quality_status" not in _index_names("knowledge_document"):
        op.create_index(
            "ix_knowledge_document_quality_status",
            "knowledge_document",
            ["quality_status", "updated_at"],
        )


def downgrade():
    """Remove the knowledge quality workflow status."""
    if not _table_exists("knowledge_document"):
        return
    if "ix_knowledge_document_quality_status" in _index_names("knowledge_document"):
        op.drop_index("ix_knowledge_document_quality_status", table_name="knowledge_document")
    if "quality_status" in _column_names("knowledge_document"):
        op.drop_column("knowledge_document", "quality_status")
