"""Add AI audit metrics.

Revision ID: a4c8d9e2f135
Revises: 9b2d7e8f4a31
Create Date: 2026-05-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "a4c8d9e2f135"
down_revision = "9b2d7e8f4a31"
branch_labels = None
depends_on = None


def upgrade():
    """Add metadata-only usage metrics to AI audit events."""
    op.add_column(
        "ai_audit_event",
        sa.Column("model_tier", sa.String(length=40), nullable=False, server_default=""),
    )
    op.add_column(
        "ai_audit_event",
        sa.Column("temperature", sa.Float(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_audit_event",
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_audit_event",
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_audit_event",
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_audit_event",
        sa.Column("cached_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "ai_audit_event",
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
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
