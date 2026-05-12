"""Add recurring maintenance plans.

Revision ID: b8d1f3a6c2e4
Revises: a4c8d9e2f135
Create Date: 2026-05-12 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

revision = "b8d1f3a6c2e4"
down_revision = "a4c8d9e2f135"
branch_labels = None
depends_on = None


def upgrade():
    """Create the recurring maintenance plan table."""
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
    op.create_index(
        "ix_maintenance_plan_active_due",
        "maintenance_plan",
        ["is_active", "next_due_date"],
    )


def downgrade():
    """Drop the recurring maintenance plan table."""
    op.drop_index("ix_maintenance_plan_active_due", table_name="maintenance_plan")
    op.drop_table("maintenance_plan")
