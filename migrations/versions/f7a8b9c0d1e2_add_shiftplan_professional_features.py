"""Add professional shift planning features.

Revision ID: f7a8b9c0d1e2
Revises: e6f7a8b9c0d1
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "f7a8b9c0d1e2"
down_revision = "e6f7a8b9c0d1"
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
    """Create structured qualifications and in-app notifications."""
    if not _table_exists("employee_machine_qualification"):
        op.create_table(
            "employee_machine_qualification",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("employee_id", sa.Integer(), nullable=False),
            sa.Column("machine_id", sa.Integer(), nullable=False),
            sa.Column("level", sa.String(length=40), nullable=False, server_default="trained"),
            sa.Column("valid_until", sa.Date(), nullable=True),
            sa.Column("notes", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["employee_id"], ["employee.id"]),
            sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "employee_id",
                "machine_id",
                name="uq_employee_machine_qualification",
            ),
        )

    if not _table_exists("notification"):
        op.create_table(
            "notification",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("recipient_user_id", sa.Integer(), nullable=False),
            sa.Column("notification_type", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("body", sa.Text(), nullable=False, server_default=""),
            sa.Column("link_url", sa.String(length=500), nullable=False, server_default=""),
            sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("read_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["recipient_user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_notification_created_at",
        "notification",
        ["created_at"],
    )
    _create_index_if_missing(
        "ix_notification_is_read",
        "notification",
        ["is_read"],
    )
    _create_index_if_missing(
        "ix_notification_notification_type",
        "notification",
        ["notification_type"],
    )


def downgrade():
    """Remove structured qualifications and in-app notifications."""
    for table_name in ("notification", "employee_machine_qualification"):
        if _table_exists(table_name):
            op.drop_table(table_name)
