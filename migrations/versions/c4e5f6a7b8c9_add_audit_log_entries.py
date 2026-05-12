"""Add global audit log entries.

Revision ID: c4e5f6a7b8c9
Revises: b8d1f3a6c2e4
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "c4e5f6a7b8c9"
down_revision = "b8d1f3a6c2e4"
branch_labels = None
depends_on = None


def upgrade():
    """Create the global security audit log table."""
    op.create_table(
        "audit_log_entry",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("before_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("after_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("ip_address", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("user_agent", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_log_entry_action"), "audit_log_entry", ["action"])
    op.create_index(
        op.f("ix_audit_log_entry_created_at"),
        "audit_log_entry",
        ["created_at"],
    )
    op.create_index(
        op.f("ix_audit_log_entry_resource_type"),
        "audit_log_entry",
        ["resource_type"],
    )


def downgrade():
    """Drop the global security audit log table."""
    op.drop_index(op.f("ix_audit_log_entry_resource_type"), table_name="audit_log_entry")
    op.drop_index(op.f("ix_audit_log_entry_created_at"), table_name="audit_log_entry")
    op.drop_index(op.f("ix_audit_log_entry_action"), table_name="audit_log_entry")
    op.drop_table("audit_log_entry")
