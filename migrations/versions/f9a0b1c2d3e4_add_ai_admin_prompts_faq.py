"""Add AI admin prompt, FAQ and response snippet tables.

Revision ID: f9a0b1c2d3e4
Revises: f8a9b0c1d2e3
Create Date: 2026-05-27 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "f9a0b1c2d3e4"
down_revision = "f8a9b0c1d2e3"
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


def _index_names(table_name):
    """Return existing index names for a table."""
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(index_name, table_name, columns, unique=False):
    """Create an index only when it is missing."""
    if index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, columns, unique=unique)


def _add_column_if_missing(table_name, column):
    """Add a table column only when it is missing."""
    if column.name not in _column_names(table_name):
        op.add_column(table_name, column)


def upgrade():
    """Create AI admin prompt, FAQ and response snippet storage."""
    if not _table_exists("ai_prompt_template"):
        op.create_table(
            "ai_prompt_template",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("workflow_key", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=160), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=False, server_default=""),
            sa.Column("response_mode", sa.String(length=20), nullable=False, server_default="text"),
            sa.Column("variables_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("workflow_key", name="uq_ai_prompt_template_workflow_key"),
        )
    _create_index_if_missing(
        "ix_ai_prompt_template_workflow_key",
        "ai_prompt_template",
        ["workflow_key"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_ai_prompt_template_is_active",
        "ai_prompt_template",
        ["is_active"],
    )

    if not _table_exists("ai_prompt_version"):
        op.create_table(
            "ai_prompt_version",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("template_id", sa.Integer(), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("system_prompt", sa.Text(), nullable=False, server_default=""),
            sa.Column("user_prompt_template", sa.Text(), nullable=False, server_default=""),
            sa.Column("json_schema", sa.Text(), nullable=False, server_default=""),
            sa.Column("rules_json", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("change_note", sa.Text(), nullable=False, server_default=""),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("activated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["template_id"], ["ai_prompt_template.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "template_id",
                "version",
                name="uq_ai_prompt_version_template_version",
            ),
        )
    _create_index_if_missing(
        "ix_ai_prompt_version_template_status",
        "ai_prompt_version",
        ["template_id", "status"],
    )
    _create_index_if_missing("ix_ai_prompt_version_status", "ai_prompt_version", ["status"])

    if not _table_exists("ai_faq_entry"):
        op.create_table(
            "ai_faq_entry",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("question", sa.Text(), nullable=False),
            sa.Column("answer", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False, server_default="wartung"),
            sa.Column("keywords", sa.Text(), nullable=False, server_default=""),
            sa.Column("machine", sa.String(length=160), nullable=False, server_default=""),
            sa.Column("department", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
            sa.Column("source", sa.String(length=40), nullable=False, server_default="manual"),
            sa.Column("source_ref_id", sa.Integer(), nullable=True),
            sa.Column("approved_by", sa.Integer(), nullable=True),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["approved_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_ai_faq_entry_status_updated",
        "ai_faq_entry",
        ["status", "updated_at"],
    )
    _create_index_if_missing(
        "ix_ai_faq_entry_department_status",
        "ai_faq_entry",
        ["department", "status"],
    )
    _create_index_if_missing(
        "ix_ai_faq_entry_category_status",
        "ai_faq_entry",
        ["category", "status"],
    )

    if not _table_exists("ai_response_snippet"):
        op.create_table(
            "ai_response_snippet",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("key", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("category", sa.String(length=80), nullable=False, server_default="fallback"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("key", name="uq_ai_response_snippet_key"),
        )
    _create_index_if_missing(
        "ix_ai_response_snippet_key",
        "ai_response_snippet",
        ["key"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_ai_response_snippet_is_active",
        "ai_response_snippet",
        ["is_active"],
    )

    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("prompt_template_key", sa.String(length=80), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("prompt_version_id", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        "ai_audit_event",
        sa.Column("prompt_version_number", sa.Integer(), nullable=True),
    )
    _create_index_if_missing(
        "ix_ai_audit_event_prompt_template_created",
        "ai_audit_event",
        ["prompt_template_key", "created_at"],
    )


def downgrade():
    """Drop AI admin prompt, FAQ and response snippet storage."""
    if _table_exists("ai_audit_event"):
        for column_name in ("prompt_version_number", "prompt_version_id", "prompt_template_key"):
            if column_name in _column_names("ai_audit_event"):
                op.drop_column("ai_audit_event", column_name)
    for table_name in (
        "ai_response_snippet",
        "ai_faq_entry",
        "ai_prompt_version",
        "ai_prompt_template",
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)
