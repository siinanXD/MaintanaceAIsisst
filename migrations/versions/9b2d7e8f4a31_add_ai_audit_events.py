"""Add AI audit events.

Revision ID: 9b2d7e8f4a31
Revises: 1645029b9eea
Create Date: 2026-05-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "9b2d7e8f4a31"
down_revision = "1645029b9eea"
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


def _create_index_if_missing(name, table_name, columns):
    """Create an index only when it is missing."""
    if name not in _index_names(table_name):
        op.create_index(name, table_name, columns, unique=False)


def upgrade():
    """Create metadata-only AI audit table."""
    if not _table_exists("ai_audit_event"):
        op.create_table(
            "ai_audit_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("workflow", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=80), nullable=False),
            sa.Column("provider", sa.String(length=80), nullable=False),
            sa.Column("model", sa.String(length=120), nullable=False),
            sa.Column("fallback_used", sa.Boolean(), nullable=False),
            sa.Column("requested_scopes", sa.Text(), nullable=False),
            sa.Column("allowed_scopes", sa.Text(), nullable=False),
            sa.Column("source_count", sa.Integer(), nullable=False),
            sa.Column("error_category", sa.String(length=120), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        op.f("ix_ai_audit_event_workflow"),
        "ai_audit_event",
        ["workflow"],
    )


def downgrade():
    """Drop metadata-only AI audit table."""
    op.drop_index(op.f("ix_ai_audit_event_workflow"), table_name="ai_audit_event")
    op.drop_table("ai_audit_event")
