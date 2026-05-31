"""Add retrieval evaluation keyword and no-result rates.

Revision ID: d2e3f4a5b6c7
Revises: c1d2e3f4a5b6
Create Date: 2026-05-30 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "d2e3f4a5b6c7"
down_revision = "c1d2e3f4a5b6"
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


def _drop_column_if_present(table_name, column_name):
    """Drop a column only when it exists."""
    if _column_exists(table_name, column_name):
        op.drop_column(table_name, column_name)


def upgrade():
    """Persist prompt-safe keyword and no-result evaluation aggregates."""
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column("keyword_query_count", sa.Integer(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column("keyword_hit_rate", sa.Float(), nullable=False, server_default="0"),
    )
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column("no_result_rate", sa.Float(), nullable=False, server_default="0"),
    )


def downgrade():
    """Remove prompt-safe keyword and no-result evaluation aggregates."""
    _drop_column_if_present("retrieval_evaluation_run", "no_result_rate")
    _drop_column_if_present("retrieval_evaluation_run", "keyword_hit_rate")
    _drop_column_if_present("retrieval_evaluation_run", "keyword_query_count")
