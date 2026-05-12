"""SQLAlchemy domain models for this bounded area."""

from datetime import UTC, datetime
from enum import Enum


def utc_now():
    """Return the current UTC timestamp."""
    return datetime.now(UTC)


class Role(str, Enum):
    """User roles controlling department access and admin capabilities."""

    MASTER_ADMIN = "master_admin"
    IT = "it"
    VERWALTUNG = "verwaltung"
    INSTANDHALTUNG = "instandhaltung"
    PRODUKTION = "produktion"
    PERSONALABTEILUNG = "personalabteilung"


class Priority(str, Enum):
    """Task priority levels ordered from most to least urgent."""

    URGENT = "urgent"
    SOON = "soon"
    NORMAL = "normal"


class TaskStatus(str, Enum):
    """Lifecycle states for a maintenance task."""

    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"
