"""SQLAlchemy domain models for this bounded area."""

from datetime import date

from app.domain_models.common import Priority, TaskStatus, utc_now
from app.extensions import db


class Task(db.Model):
    """Maintenance task with lifecycle tracking from creation to completion."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    priority = db.Column(db.Enum(Priority), nullable=False, default=Priority.NORMAL)
    status = db.Column(db.Enum(TaskStatus), nullable=False, default=TaskStatus.OPEN)
    due_date = db.Column(db.Date, nullable=False, default=date.today)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    current_worker_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    started_at = db.Column(db.DateTime)
    completed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    completed_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    department = db.relationship("Department", back_populates="tasks")
    creator = db.relationship(
        "User",
        foreign_keys=[created_by],
        back_populates="created_tasks",
    )
    current_worker = db.relationship(
        "User",
        foreign_keys=[current_worker_id],
        back_populates="assigned_tasks",
    )
    completed_by_user = db.relationship(
        "User",
        foreign_keys=[completed_by_id],
        back_populates="completed_tasks",
    )

    def to_dict(self):
        """Return a JSON-serializable representation of the task."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "priority": self.priority.value,
            "status": self.status.value,
            "due_date": self.due_date.isoformat(),
            "department": self.department.to_dict() if self.department else None,
            "created_by": self.created_by,
            "creator": self.creator.to_dict() if self.creator else None,
            "current_worker_id": self.current_worker_id,
            "current_worker": (self.current_worker.to_dict() if self.current_worker else None),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_by": self.completed_by_id,
            "completed_by_user": (
                self.completed_by_user.to_dict() if self.completed_by_user else None
            ),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
