"""SQLAlchemy domain models for this bounded area."""

from app.domain_models.common import Priority, utc_now
from app.extensions import db


class Machine(db.Model):
    """Production machine with staffing requirements used by shift planning and inventory."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    produced_item = db.Column(db.String(160), nullable=False, default="")
    required_employees = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    materials = db.relationship("InventoryMaterial", back_populates="machine")
    maintenance_plans = db.relationship(
        "MaintenancePlan",
        back_populates="machine",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        """Return a JSON-serializable representation of the machine."""
        return {
            "id": self.id,
            "name": self.name,
            "produced_item": self.produced_item,
            "required_employees": self.required_employees,
            "created_at": self.created_at.isoformat(),
        }


class InventoryMaterial(db.Model):
    """Spare part or consumable material tracked in inventory and linked to a machine."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    unit_cost = db.Column(db.Float, nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    manufacturer = db.Column(db.String(160), nullable=False, default="")
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    machine = db.relationship("Machine", back_populates="materials")

    @property
    def total_value(self):
        """Return the total material value based on unit cost and quantity."""
        return round((self.unit_cost or 0) * (self.quantity or 0), 2)

    def to_dict(self):
        """Return a JSON-serializable representation of the inventory material."""
        return {
            "id": self.id,
            "name": self.name,
            "unit_cost": self.unit_cost,
            "quantity": self.quantity,
            "manufacturer": self.manufacturer,
            "machine_id": self.machine_id,
            "machine": self.machine.to_dict() if self.machine else None,
            "total_value": self.total_value,
            "created_at": self.created_at.isoformat(),
        }


class MaintenancePlan(db.Model):
    """Recurring maintenance plan that can generate scheduled tasks."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    interval_days = db.Column(db.Integer, nullable=False)
    next_due_date = db.Column(db.Date, nullable=False)
    priority = db.Column(db.Enum(Priority), nullable=False, default=Priority.NORMAL)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"))
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    last_generated_task_id = db.Column(
        db.Integer,
        db.ForeignKey("task.id", ondelete="SET NULL"),
    )
    last_generated_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    machine = db.relationship("Machine", back_populates="maintenance_plans")
    department = db.relationship("Department")
    creator = db.relationship("User", foreign_keys=[created_by])
    last_generated_task = db.relationship("Task", foreign_keys=[last_generated_task_id])

    def to_dict(self):
        """Return a JSON-serializable representation of the maintenance plan."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "interval_days": self.interval_days,
            "next_due_date": self.next_due_date.isoformat(),
            "priority": self.priority.value,
            "is_active": self.is_active,
            "machine_id": self.machine_id,
            "machine": self.machine.to_dict() if self.machine else None,
            "department": self.department.to_dict() if self.department else None,
            "created_by": self.created_by,
            "last_generated_task_id": self.last_generated_task_id,
            "last_generated_at": (
                self.last_generated_at.isoformat() if self.last_generated_at else None
            ),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
