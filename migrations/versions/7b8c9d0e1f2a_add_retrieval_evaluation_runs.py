"""Add persisted retrieval evaluation runs.

Revision ID: 7b8c9d0e1f2a
Revises: 6a7b8c9d0e1f
Create Date: 2026-05-19 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "7b8c9d0e1f2a"
down_revision = "6a7b8c9d0e1f"
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


def _create_index_if_missing(index_name, table_name, columns):
    """Create an index only when it is missing."""
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns)


def upgrade():
    """Create prompt-safe retrieval evaluation run history."""
    if not _table_exists("retrieval_evaluation_run"):
        op.create_table(
            "retrieval_evaluation_run",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("query_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("recall_at_k", sa.Float(), nullable=False, server_default="0"),
            sa.Column("mrr", sa.Float(), nullable=False, server_default="0"),
            sa.Column("ndcg_at_k", sa.Float(), nullable=False, server_default="0"),
            sa.Column(
                "permission_leak_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column(
                "forbidden_source_hit_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
            sa.Column("no_result_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_retrieval_evaluation_run_created",
        "retrieval_evaluation_run",
        ["created_at"],
    )


def downgrade():
    """Drop prompt-safe retrieval evaluation run history."""
    if _table_exists("retrieval_evaluation_run"):
        op.drop_table("retrieval_evaluation_run")
