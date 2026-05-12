"""SQLAlchemy domain models for this bounded area."""

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
