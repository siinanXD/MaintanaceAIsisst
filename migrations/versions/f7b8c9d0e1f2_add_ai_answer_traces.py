"""Add AI answer trace records.

Revision ID: f7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-06-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "f7b8c9d0e1f2"
down_revision = "f6a7b8c9d0e1"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return whether a table exists in the current migration connection."""
    return table_name in inspect(op.get_bind()).get_table_names()


def _index_names(table_name):
    """Return existing index names for a table."""
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name, table_name, columns, unique=False):
    """Create an index only when it does not exist."""
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def upgrade():
    """Create metadata-only AI answer trace records."""
    if not _table_exists("ai_answer_trace"):
        op.create_table(
            "ai_answer_trace",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("answer_id", sa.String(length=64), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("chat_message_id", sa.Integer(), nullable=False),
            sa.Column("audit_event_id", sa.Integer(), nullable=True),
            sa.Column("workflow", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("provider", sa.String(length=80), nullable=False, server_default=""),
            sa.Column("model", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("model_tier", sa.String(length=40), nullable=False, server_default=""),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column(
                "estimated_cost_usd",
                sa.Float(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("confidence_score", sa.Integer(), nullable=True),
            sa.Column(
                "confidence_level",
                sa.String(length=40),
                nullable=False,
                server_default="",
            ),
            sa.Column("source_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("sources_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("chunks_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["audit_event_id"], ["ai_audit_event.id"]),
            sa.ForeignKeyConstraint(["chat_message_id"], ["chat_message.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("answer_id"),
            sa.UniqueConstraint("chat_message_id"),
        )
    _create_index_if_missing(
        "ix_ai_answer_trace_answer_id",
        "ai_answer_trace",
        ["answer_id"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_ai_answer_trace_user_id",
        "ai_answer_trace",
        ["user_id"],
    )
    _create_index_if_missing(
        "ix_ai_answer_trace_created_at",
        "ai_answer_trace",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_ai_answer_trace_user_created",
        "ai_answer_trace",
        ["user_id", "created_at"],
    )
    _create_index_if_missing(
        "ix_ai_answer_trace_audit_event",
        "ai_answer_trace",
        ["audit_event_id"],
    )


def downgrade():
    """Remove AI answer trace records."""
    if _table_exists("ai_answer_trace"):
        op.drop_table("ai_answer_trace")
