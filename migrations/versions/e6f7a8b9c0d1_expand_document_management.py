"""Expand document management.

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "e6f7a8b9c0d1"
down_revision = "d5e6f7a8b9c0"
branch_labels = None
depends_on = None


def _table_exists(table_name):
    """Return whether a table exists in the current migration connection."""
    return table_name in inspect(op.get_bind()).get_table_names()


def _columns(table_name):
    """Return existing column names for a table."""
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in inspect(op.get_bind()).get_columns(table_name)}


def _add_column_if_missing(table_name, column):
    """Add a column only when an older database still misses it."""
    if column.name not in _columns(table_name):
        op.add_column(table_name, column)


def _create_foreign_key_if_supported(name, source, referent, local_cols, remote_cols):
    """Create a foreign key when the dialect supports ALTER TABLE constraints."""
    if op.get_bind().dialect.name == "sqlite":
        return
    op.create_foreign_key(name, source, referent, local_cols, remote_cols)


def upgrade():
    """Add document versioning, approvals, manuals, and summaries."""
    _add_column_if_missing(
        "generated_document",
        sa.Column("status", sa.String(length=40), nullable=False, server_default="draft"),
    )
    _add_column_if_missing("generated_document", sa.Column("current_version_id", sa.Integer()))
    _add_column_if_missing(
        "generated_document",
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "generated_document",
        sa.Column(
            "summary_status",
            sa.String(length=40),
            nullable=False,
            server_default="not_started",
        ),
    )
    _add_column_if_missing("generated_document", sa.Column("approved_by", sa.Integer()))
    _add_column_if_missing("generated_document", sa.Column("approved_at", sa.DateTime()))
    _add_column_if_missing(
        "generated_document",
        sa.Column("approval_comment", sa.Text(), nullable=False, server_default=""),
    )
    _add_column_if_missing("generated_document", sa.Column("rejected_by", sa.Integer()))
    _add_column_if_missing("generated_document", sa.Column("rejected_at", sa.DateTime()))
    _add_column_if_missing(
        "generated_document",
        sa.Column("rejection_comment", sa.Text(), nullable=False, server_default=""),
    )

    if not _table_exists("document_version"):
        op.create_table(
            "document_version",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("relative_path", sa.String(length=500), nullable=False),
            sa.Column(
                "original_filename",
                sa.String(length=255),
                nullable=False,
                server_default="",
            ),
            sa.Column(
                "content_type",
                sa.String(length=120),
                nullable=False,
                server_default="text/html",
            ),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["document_id"], ["generated_document.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "document_id",
                "version_number",
                name="uq_document_version_document_number",
            ),
        )
    if not _table_exists("document_approval_event"):
        op.create_table(
            "document_approval_event",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("document_id", sa.Integer(), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("comment", sa.Text(), nullable=False, server_default=""),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["document_id"], ["generated_document.id"]),
            sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists("machine_manual"):
        op.create_table(
            "machine_manual",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("machine_id", sa.Integer(), nullable=True),
            sa.Column(
                "department",
                sa.String(length=120),
                nullable=False,
                server_default="",
            ),
            sa.Column("title", sa.String(length=180), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("relative_path", sa.String(length=500), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("analysis", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "analysis_status",
                sa.String(length=40),
                nullable=False,
                server_default="not_started",
            ),
            sa.Column("summary", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "summary_status",
                sa.String(length=40),
                nullable=False,
                server_default="not_started",
            ),
            sa.Column("current_version_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists("machine_manual_version"):
        op.create_table(
            "machine_manual_version",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("manual_id", sa.Integer(), nullable=False),
            sa.Column("version_number", sa.Integer(), nullable=False),
            sa.Column("relative_path", sa.String(length=500), nullable=False),
            sa.Column("original_filename", sa.String(length=255), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=False, server_default=""),
            sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("extracted_text", sa.Text(), nullable=False, server_default=""),
            sa.Column(
                "extraction_status",
                sa.String(length=40),
                nullable=False,
                server_default="not_started",
            ),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["manual_id"], ["machine_manual.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "manual_id",
                "version_number",
                name="uq_machine_manual_version_manual_number",
            ),
        )
    _create_foreign_key_if_supported(
        "fk_generated_document_current_version",
        "generated_document",
        "document_version",
        ["current_version_id"],
        ["id"],
    )
    _create_foreign_key_if_supported(
        "fk_machine_manual_current_version",
        "machine_manual",
        "machine_manual_version",
        ["current_version_id"],
        ["id"],
    )


def downgrade():
    """Remove expanded document management tables and columns."""
    if op.get_bind().dialect.name != "sqlite":
        op.drop_constraint(
            "fk_machine_manual_current_version",
            "machine_manual",
            type_="foreignkey",
        )
        op.drop_constraint(
            "fk_generated_document_current_version",
            "generated_document",
            type_="foreignkey",
        )
    for table_name in (
        "machine_manual_version",
        "machine_manual",
        "document_approval_event",
        "document_version",
    ):
        if _table_exists(table_name):
            op.drop_table(table_name)
    for column in (
        "rejection_comment",
        "rejected_at",
        "rejected_by",
        "approval_comment",
        "approved_at",
        "approved_by",
        "summary_status",
        "summary",
        "current_version_id",
        "status",
    ):
        if column in _columns("generated_document"):
            op.drop_column("generated_document", column)
