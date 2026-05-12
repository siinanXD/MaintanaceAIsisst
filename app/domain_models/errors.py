"""SQLAlchemy domain models for this bounded area."""

from app.domain_models.common import utc_now
from app.extensions import db


class ErrorEntry(db.Model):
    """Error catalog entry linking a machine fault to its causes and solution."""

    id = db.Column(db.Integer, primary_key=True)
    machine = db.Column(db.String(160), nullable=False)
    error_code = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    possible_causes = db.Column(db.Text, nullable=False, default="")
    solution = db.Column(db.Text, nullable=False, default="")
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    department = db.relationship("Department", back_populates="errors")
    machine_rel = db.relationship("Machine", foreign_keys=[machine_id])

    def to_dict(self):
        """Return a JSON-serializable representation of the error catalog entry."""
        return {
            "id": self.id,
            "machine": self.machine,
            "machine_id": self.machine_id,
            "machine_obj": self.machine_rel.to_dict() if self.machine_rel else None,
            "error_code": self.error_code,
            "title": self.title,
            "description": self.description,
            "possible_causes": self.possible_causes,
            "solution": self.solution,
            "department": self.department.to_dict() if self.department else None,
            "created_at": self.created_at.isoformat(),
        }
