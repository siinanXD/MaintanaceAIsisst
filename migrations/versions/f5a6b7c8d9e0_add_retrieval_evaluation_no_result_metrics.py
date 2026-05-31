"""Add retrieval evaluation expected no-result metrics.

Revision ID: f5a6b7c8d9e0
Revises: f4a5b6c7d8e9
Create Date: 2026-05-30 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "f5a6b7c8d9e0"
down_revision = "f4a5b6c7d8e9"
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
    """Persist prompt-safe expected and unexpected no-result aggregates."""
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column(
            "expected_no_result_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column(
            "expected_no_result_success_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column(
            "expected_no_result_success_rate",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column(
            "unexpected_no_result_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    _add_column_if_missing(
        "retrieval_evaluation_run",
        sa.Column(
            "unexpected_no_result_rate",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade():
    """Remove prompt-safe expected and unexpected no-result aggregates."""
    _drop_column_if_present("retrieval_evaluation_run", "unexpected_no_result_rate")
    _drop_column_if_present("retrieval_evaluation_run", "unexpected_no_result_count")
    _drop_column_if_present(
        "retrieval_evaluation_run",
        "expected_no_result_success_rate",
    )
    _drop_column_if_present(
        "retrieval_evaluation_run",
        "expected_no_result_success_count",
    )
    _drop_column_if_present("retrieval_evaluation_run", "expected_no_result_count")
