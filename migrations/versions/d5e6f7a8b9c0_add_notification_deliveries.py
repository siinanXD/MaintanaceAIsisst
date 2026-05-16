"""Add notification delivery records.

Revision ID: d5e6f7a8b9c0
Revises: c4e5f6a7b8c9
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "d5e6f7a8b9c0"
down_revision = "c4e5f6a7b8c9"
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
        op.create_index(name, table_name, columns)


def upgrade():
    """Create notification delivery tracking table."""
    if not _table_exists("notification_delivery"):
        op.create_table(
            "notification_delivery",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("notification_type", sa.String(length=80), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=True),
            sa.Column("recipient_email", sa.String(length=255), nullable=False),
            sa.Column("channel", sa.String(length=40), nullable=False, server_default="email"),
            sa.Column("subject", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="pending"),
            sa.Column("error", sa.Text(), nullable=False, server_default=""),
            sa.Column("dedupe_key", sa.String(length=255), nullable=False),
            sa.Column("payload_json", sa.Text(), nullable=False, server_default="{}"),
            sa.Column("sent_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        op.f("ix_notification_delivery_created_at"),
        "notification_delivery",
        ["created_at"],
    )
    _create_index_if_missing(
        op.f("ix_notification_delivery_dedupe_key"),
        "notification_delivery",
        ["dedupe_key"],
    )
    _create_index_if_missing(
        op.f("ix_notification_delivery_notification_type"),
        "notification_delivery",
        ["notification_type"],
    )
    _create_index_if_missing(
        op.f("ix_notification_delivery_recipient_email"),
        "notification_delivery",
        ["recipient_email"],
    )
    _create_index_if_missing(
        op.f("ix_notification_delivery_status"),
        "notification_delivery",
        ["status"],
    )


def downgrade():
    """Drop notification delivery tracking table."""
    op.drop_index(op.f("ix_notification_delivery_status"), table_name="notification_delivery")
    op.drop_index(
        op.f("ix_notification_delivery_recipient_email"),
        table_name="notification_delivery",
    )
    op.drop_index(
        op.f("ix_notification_delivery_notification_type"),
        table_name="notification_delivery",
    )
    op.drop_index(
        op.f("ix_notification_delivery_dedupe_key"),
        table_name="notification_delivery",
    )
    op.drop_index(
        op.f("ix_notification_delivery_created_at"),
        table_name="notification_delivery",
    )
    op.drop_table("notification_delivery")
