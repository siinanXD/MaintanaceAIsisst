"""SQLAlchemy domain models for this bounded area."""

from app.domain_models.common import utc_now
from app.extensions import db


class Machine(db.Model):
    """Production machine with staffing requirements used by shift planning and inventory."""

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    produced_item = db.Column(db.String(160), nullable=False, default="")
    required_employees = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    materials = db.relationship("InventoryMaterial", back_populates="machine")

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
