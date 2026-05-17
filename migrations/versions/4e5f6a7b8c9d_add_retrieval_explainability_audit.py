"""Add retrieval explainability audit metadata.

Revision ID: 4e5f6a7b8c9d
Revises: 3d4e5f6a7b8c
Create Date: 2026-05-17 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "4e5f6a7b8c9d"
down_revision = "3d4e5f6a7b8c"
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


def upgrade():
    """Add prompt-free retrieval explainability to AI audit events."""
    if not _table_exists("ai_audit_event"):
        return
    if "retrieval_explainability_json" not in _column_names("ai_audit_event"):
        op.add_column(
            "ai_audit_event",
            sa.Column(
                "retrieval_explainability_json",
                sa.Text(),
                nullable=False,
                server_default="{}",
            ),
        )


def downgrade():
    """Remove retrieval explainability from AI audit events."""
    if not _table_exists("ai_audit_event"):
        return
    if "retrieval_explainability_json" in _column_names("ai_audit_event"):
        op.drop_column("ai_audit_event", "retrieval_explainability_json")
