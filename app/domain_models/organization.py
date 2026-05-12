"""SQLAlchemy domain models for this bounded area."""

import json

from app.domain_models.common import utc_now
from app.extensions import db


class Department(db.Model):
    """Organisational unit that groups users, tasks, and error entries."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    users = db.relationship("User", back_populates="department")
    tasks = db.relationship("Task", back_populates="department")
    errors = db.relationship("ErrorEntry", back_populates="department")

    def to_dict(self):
        """Return a JSON-serializable representation of the department."""
        return {"id": self.id, "name": self.name}


class DashboardPermission(db.Model):
    """Store dashboard-level permissions for one user."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    dashboard = db.Column(db.String(40), nullable=False)
    can_view = db.Column(db.Boolean, default=False, nullable=False)
    can_write = db.Column(db.Boolean, default=False, nullable=False)
    employee_access_level = db.Column(
        db.String(40),
        default="none",
        nullable=False,
    )

    user = db.relationship("User", back_populates="dashboard_permissions")

    __table_args__ = (
        db.UniqueConstraint(
            "user_id",
            "dashboard",
            name="uq_dashboard_permission_user_dashboard",
        ),
    )

    def to_dict(self):
        """Return a JSON-serializable representation of the permission."""
        return {
            "dashboard": self.dashboard,
            "can_view": self.can_view,
            "can_write": self.can_write,
            "employee_access_level": self.employee_access_level,
        }


class AuditLogEntry(db.Model):
    """Security-relevant administrative change log entry."""

    id = db.Column(db.Integer, primary_key=True)
    actor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(80), nullable=False, index=True)
    resource_type = db.Column(db.String(80), nullable=False, index=True)
    resource_id = db.Column(db.String(120), nullable=False, default="")
    before_json = db.Column(db.Text, nullable=False, default="{}")
    after_json = db.Column(db.Text, nullable=False, default="{}")
    ip_address = db.Column(db.String(80), nullable=False, default="")
    user_agent = db.Column(db.String(300), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    actor = db.relationship("User", foreign_keys=[actor_id])

    def to_dict(self):
        """Return a JSON-serializable audit entry without sensitive internals."""
        return {
            "id": self.id,
            "actor_id": self.actor_id,
            "actor": (
                {"id": self.actor.id, "username": self.actor.username} if self.actor else None
            ),
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "before": _loads_json_object(self.before_json),
            "after": _loads_json_object(self.after_json),
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat(),
        }


def _loads_json_object(value):
    """Return a JSON-object text value as a safe dictionary."""
    try:
        result = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}
