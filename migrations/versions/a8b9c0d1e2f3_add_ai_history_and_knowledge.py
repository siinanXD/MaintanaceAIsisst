"""Add AI chat metadata and local knowledge index.

Revision ID: a8b9c0d1e2f3
Revises: f7a8b9c0d1e2
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return whether a table exists in the current migration connection."""
    return table_name in inspect(op.get_bind()).get_table_names()


def _column_exists(table_name, column_name):
    """Return whether a column exists on an existing table."""
    if not _table_exists(table_name):
        return False
    return column_name in {
        column["name"] for column in inspect(op.get_bind()).get_columns(table_name)
    }


def _index_names(table_name):
    """Return existing index names for a table."""
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(name, table_name, columns):
    """Create an index only when it is missing."""
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns)


def _add_column_if_missing(table_name, column):
    """Add a column only when it does not exist yet."""
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade():
    """Add AI history metadata and knowledge-base tables."""
    if _table_exists("chat_message"):
        _add_column_if_missing(
            "chat_message",
            sa.Column(
                "response_type",
                sa.String(length=80),
                nullable=False,
                server_default="assistant",
            ),
        )
        _add_column_if_missing(
            "chat_message",
            sa.Column(
                "diagnostics_json",
                sa.Text(),
                nullable=False,
                server_default="{}",
            ),
        )
        _add_column_if_missing(
            "chat_message",
            sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
        )
        _add_column_if_missing(
            "chat_message",
            sa.Column("audit_event_id", sa.Integer(), nullable=True),
        )
        _create_index_if_missing(
            "ix_chat_message_audit_event_id",
            "chat_message",
            ["audit_event_id"],
        )
        _create_index_if_missing(
            "ix_chat_message_created_at",
            "chat_message",
            ["created_at"],
        )

    if not _table_exists("knowledge_document"):
        op.create_table(
            "knowledge_document",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column(
                "source_type",
                sa.String(length=80),
                nullable=False,
                server_default="upload",
            ),
            sa.Column("source_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=220), nullable=False),
            sa.Column(
                "original_filename",
                sa.String(length=255),
                nullable=False,
                server_default="",
            ),
            sa.Column("relative_path", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("content_type", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("department", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("error_message", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("knowledge_chunk"):
        op.create_table(
            "knowledge_chunk",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("chunk_index", sa.Integer(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("token_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["knowledge_document.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "document_id",
                "chunk_index",
                name="uq_knowledge_chunk_document_index",
            ),
        )

    _create_index_if_missing("ix_knowledge_document_status", "knowledge_document", ["status"])
    _create_index_if_missing(
        "ix_knowledge_chunk_document_id",
        "knowledge_chunk",
        ["document_id"],
    )


def downgrade():
    """Remove AI history metadata and knowledge-base tables."""
    for table_name in ("knowledge_chunk", "knowledge_document"):
        if _table_exists(table_name):
            op.drop_table(table_name)
    if _table_exists("chat_message"):
        for column_name in (
            "audit_event_id",
            "source_count",
            "diagnostics_json",
            "response_type",
        ):
            if _column_exists("chat_message", column_name):
                op.drop_column("chat_message", column_name)
