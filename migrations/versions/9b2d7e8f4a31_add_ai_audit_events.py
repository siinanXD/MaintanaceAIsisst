"""Add AI audit events.

Revision ID: 9b2d7e8f4a31
Revises: 1645029b9eea
Create Date: 2026-05-11 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "9b2d7e8f4a31"
down_revision = "1645029b9eea"
branch_labels = None
depends_on = None


def upgrade():
    """Create metadata-only AI audit table."""
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
    op.create_index(
        op.f("ix_ai_audit_event_workflow"),
        "ai_audit_event",
        ["workflow"],
        unique=False,
    )


def downgrade():
    """Drop metadata-only AI audit table."""
    op.drop_index(op.f("ix_ai_audit_event_workflow"), table_name="ai_audit_event")
    op.drop_table("ai_audit_event")
