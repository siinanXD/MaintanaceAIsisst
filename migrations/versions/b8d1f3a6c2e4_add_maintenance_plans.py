"""Add recurring maintenance plans.

Revision ID: b8d1f3a6c2e4
Revises: a4c8d9e2f135
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect

revision = "b8d1f3a6c2e4"
down_revision = "a4c8d9e2f135"
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
    """Create the recurring maintenance plan table."""
    if not _table_exists("maintenance_plan"):
        op.create_table(
            "maintenance_plan",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("interval_days", sa.Integer(), nullable=False),
            sa.Column("next_due_date", sa.Date(), nullable=False),
            sa.Column("priority", sa.String(length=20), nullable=False),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("machine_id", sa.Integer(), nullable=True),
            sa.Column("department_id", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("last_generated_task_id", sa.Integer(), nullable=True),
            sa.Column("last_generated_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["created_by"], ["user.id"]),
            sa.ForeignKeyConstraint(["department_id"], ["department.id"]),
            sa.ForeignKeyConstraint(
                ["last_generated_task_id"],
                ["task.id"],
                ondelete="SET NULL",
            ),
            sa.ForeignKeyConstraint(["machine_id"], ["machine.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_maintenance_plan_active_due",
        "maintenance_plan",
        ["is_active", "next_due_date"],
    )


def downgrade():
    """Drop the recurring maintenance plan table."""
    op.drop_index("ix_maintenance_plan_active_due", table_name="maintenance_plan")
    op.drop_table("maintenance_plan")
