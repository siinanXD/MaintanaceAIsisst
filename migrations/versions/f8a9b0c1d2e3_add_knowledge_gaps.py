"""Add knowledge gaps.

Revision ID: f8a9b0c1d2e3
Revises: e2f3a4b5c6d7
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "f8a9b0c1d2e3"
down_revision = "e2f3a4b5c6d7"
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


def _create_index_if_missing(index_name, table_name, columns):
    """Create an index only when it is missing."""
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade():
    """Create persisted AI knowledge-gap tracking."""
    if not _table_exists("knowledge_gap"):
        op.create_table(
            "knowledge_gap",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("question_hash", sa.String(length=64), nullable=False),
            sa.Column("context_text", sa.Text(), nullable=False, server_default=""),
            sa.Column("machine", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("department", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="open"),
            sa.Column("occurrence_count", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("task_id", sa.Integer(), nullable=True),
            sa.Column("audit_event_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_seen_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["audit_event_id"], ["ai_audit_event.id"]),
            sa.ForeignKeyConstraint(["task_id"], ["task.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )

    _create_index_if_missing(
        "ix_knowledge_gap_question_hash",
        "knowledge_gap",
        ["question_hash"],
    )
    _create_index_if_missing("ix_knowledge_gap_status", "knowledge_gap", ["status"])
    _create_index_if_missing(
        "ix_knowledge_gap_status_last_seen",
        "knowledge_gap",
        ["status", "last_seen_at"],
    )
    _create_index_if_missing(
        "ix_knowledge_gap_hash_status",
        "knowledge_gap",
        ["question_hash", "status"],
    )
    _create_index_if_missing(
        "ix_knowledge_gap_department_status",
        "knowledge_gap",
        ["department", "status"],
    )


def downgrade():
    """Drop persisted AI knowledge-gap tracking."""
    if _table_exists("knowledge_gap"):
        op.drop_table("knowledge_gap")
