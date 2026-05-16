"""Add assistant training entries.

Revision ID: c0d1e2f3a4b5
Revises: b9c0d1e2f3a4
Create Date: 2026-05-16 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
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
    """Create the manual assistant training table."""
    if not _table_exists("assistant_training_entry"):
        op.create_table(
            "assistant_training_entry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=220), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("keywords", sa.Text(), nullable=False, server_default=""),
            sa.Column("category", sa.String(length=80), nullable=False, server_default="wartung"),
            sa.Column("department", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("priority", sa.Integer(), nullable=False, server_default="50"),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_assistant_training_entry_is_active",
        "assistant_training_entry",
        ["is_active"],
    )


def downgrade():
    """Remove the manual assistant training table."""
    if _table_exists("assistant_training_entry"):
        op.drop_table("assistant_training_entry")
