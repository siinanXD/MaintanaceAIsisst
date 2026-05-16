"""Add AI audit metrics.

Revision ID: a4c8d9e2f135
Revises: 9b2d7e8f4a31
Create Date: 2026-05-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "a4c8d9e2f135"
down_revision = "9b2d7e8f4a31"
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


def _add_column_if_missing(table_name, column):
    """Add a column only when it is missing."""
    if not _column_exists(table_name, column.name):
        op.add_column(table_name, column)


def upgrade():
    """Add metadata-only usage metrics to AI audit events."""
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("model_tier", sa.String(length=40), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column(
            "estimated_cost_usd",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade():
    """Remove AI audit usage metric columns."""
    op.drop_column("ai_audit_event", "estimated_cost_usd")
    op.drop_column("ai_audit_event", "total_tokens")
    op.drop_column("ai_audit_event", "cached_tokens")
    op.drop_column("ai_audit_event", "output_tokens")
    op.drop_column("ai_audit_event", "input_tokens")
    op.drop_column("ai_audit_event", "latency_ms")
    op.drop_column("ai_audit_event", "temperature")
    op.drop_column("ai_audit_event", "model_tier")
