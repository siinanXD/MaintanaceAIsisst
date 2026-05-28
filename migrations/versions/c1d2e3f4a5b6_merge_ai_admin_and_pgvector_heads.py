"""Merge AI admin and pgvector migration heads.

Revision ID: c1d2e3f4a5b6
Revises: 3f4a5b6c7d8e, f9a0b1c2d3e4
Create Date: 2026-05-27 15:00:00.000000

"""

revision = "c1d2e3f4a5b6"
down_revision = ("3f4a5b6c7d8e", "f9a0b1c2d3e4")
branch_labels = None
depends_on = None


def upgrade():
    """Merge both active schema branches without changing database objects."""


def downgrade():
    """Split the migration graph back into the previous two heads."""
