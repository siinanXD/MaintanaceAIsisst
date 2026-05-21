"""Add audit value fields to operational events.

Revision ID: b1c2d3e4f5a6
Revises: a0b1c2d3e4f5
Create Date: 2026-05-21 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "b1c2d3e4f5a6"
down_revision = "a0b1c2d3e4f5"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return whether a table exists in the current migration connection."""
    return table_name in inspect(op.get_bind()).get_table_names()


def _column_names(table_name):
    """Return existing column names for a table."""
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name, column):
    """Add one column when the target table exists and the column is absent."""
    if _table_exists(table_name) and column.name not in _column_names(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.add_column(column)


def _drop_column_if_exists(table_name, column_name):
    """Drop one column when the target table exists and the column is present."""
    if _table_exists(table_name) and column_name in _column_names(table_name):
        with op.batch_alter_table(table_name) as batch:
            batch.drop_column(column_name)


def upgrade():
    """Add old/new value and description fields to operational events."""
    columns = (
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
    )
    for column in columns:
        _add_column_if_missing("operational_event", column)


def downgrade():
    """Remove audit value fields from operational events."""
    for column_name in ("description", "new_value", "old_value"):
        _drop_column_if_exists("operational_event", column_name)
