"""SQLAlchemy domain models for this bounded area."""

from app.domain_models.common import utc_now
from app.extensions import db


class GeneratedDocument(db.Model):
    """Store metadata for generated maintenance documents."""

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    document_type = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    relative_path = db.Column(db.String(500), nullable=False)
    department = db.Column(db.String(120), nullable=False, default="")
    machine = db.Column(db.String(160), nullable=False, default="")
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    task = db.relationship("Task")
    creator = db.relationship("User")
    machine_rel = db.relationship("Machine", foreign_keys=[machine_id])

    def to_dict(self):
        """Return a JSON-serializable representation of the document metadata."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "document_type": self.document_type,
            "title": self.title,
            "relative_path": self.relative_path,
            "department": self.department,
            "machine": self.machine,
            "machine_id": self.machine_id,
            "machine_obj": self.machine_rel.to_dict() if self.machine_rel else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "download_url": f"/api/documents/{self.id}/download",
            "detail_url": f"/api/documents/{self.id}",
        }


class EmployeeDocument(db.Model):
    """File attachment stored on disk and associated with an employee record."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120), nullable=False, default="")
    uploaded_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    employee = db.relationship("Employee", back_populates="documents")

    def to_dict(self):
        """Return a JSON-serializable representation of the employee document metadata."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "uploaded_at": self.uploaded_at.isoformat(),
            "download_url": f"/api/employees/{self.employee_id}/documents/{self.id}",
        }
