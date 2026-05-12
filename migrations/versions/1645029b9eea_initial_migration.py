"""Create base application tables.

Revision ID: 1645029b9eea
Revises:
Create Date: 2026-05-04 22:47:43.856504

"""

from alembic import op

import app.models  # noqa: F401
from app.extensions import db

revision = "1645029b9eea"
down_revision = None
branch_labels = None
depends_on = None


BASE_TABLE_NAMES = frozenset(
    {
        "ai_feedback",
        "chat_message",
        "dashboard_permission",
        "department",
        "employee",
        "employee_document",
        "error_entry",
        "generated_document",
        "inventory_material",
        "machine",
        "shift_handover",
        "shift_plan",
        "shift_plan_change_log",
        "shift_plan_entry",
        "task",
        "token_blocklist",
        "user",
        "vacation_request",
    }
)


def _base_tables():
    """Return SQLAlchemy tables managed by the base migration."""
    return [table for table in db.metadata.sorted_tables if table.name in BASE_TABLE_NAMES]


def upgrade():
    """Create base application tables."""
    db.metadata.create_all(bind=op.get_bind(), tables=_base_tables())


def downgrade():
    """Drop base application tables."""
    db.metadata.drop_all(bind=op.get_bind(), tables=list(reversed(_base_tables())))
