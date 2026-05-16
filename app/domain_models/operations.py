"""Operations tracking models for plant-wide KPI reporting."""

import json

from app.domain_models.common import utc_now
from app.extensions import db


class OperationalEvent(db.Model):
    """Pseudonymized event emitted by workflows for operations analytics."""

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    feature = db.Column(db.String(80), nullable=False, index=True)
    entity_type = db.Column(db.String(80), nullable=False, default="")
    entity_id = db.Column(db.Integer)
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"), nullable=True, index=True)
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("department.id"),
        nullable=True,
        index=True,
    )
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=True, index=True)
    occurred_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)
    actor_hash = db.Column(db.String(128), nullable=False, default="", index=True)
    actor_role = db.Column(db.String(80), nullable=False, default="")
    source = db.Column(db.String(80), nullable=False, default="app")
    metadata_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    site = db.relationship("Site")
    department = db.relationship("Department")
    machine = db.relationship("Machine")
    task = db.relationship("Task")

    __table_args__ = (
        db.Index("ix_operational_event_site_time", "site_id", "occurred_at"),
        db.Index("ix_operational_event_feature_time", "feature", "occurred_at"),
        db.Index("ix_operational_event_type_time", "event_type", "occurred_at"),
        db.Index(
            "ix_operational_event_department_time",
            "department_id",
            "occurred_at",
        ),
        db.Index("ix_operational_event_entity", "entity_type", "entity_id"),
    )

    def metadata_dict(self):
        """Return event metadata as a safe dictionary."""
        try:
            data = json.loads(self.metadata_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def to_dict(self, include_metadata=True):
        """Return a JSON-serializable event payload."""
        payload = {
            "id": self.id,
            "event_type": self.event_type,
            "feature": self.feature,
            "entity_type": self.entity_type,
            "entity_id": self.entity_id,
            "site_id": self.site_id,
            "site": self.site.to_dict() if self.site else None,
            "department_id": self.department_id,
            "department": self.department.to_dict() if self.department else None,
            "machine_id": self.machine_id,
            "task_id": self.task_id,
            "occurred_at": self.occurred_at.isoformat(),
            "actor_hash": self.actor_hash,
            "actor_role": self.actor_role,
            "source": self.source,
            "created_at": self.created_at.isoformat(),
        }
        if include_metadata:
            payload["metadata"] = self.metadata_dict()
        return payload


class OperationalKpiAggregate(db.Model):
    """Long-lived aggregate metric derived from operations events and domain data."""

    id = db.Column(db.Integer, primary_key=True)
    period_type = db.Column(db.String(20), nullable=False, default="day")
    period_start = db.Column(db.Date, nullable=False, index=True)
    site_id = db.Column(db.Integer, db.ForeignKey("site.id"), nullable=True, index=True)
    department_id = db.Column(
        db.Integer,
        db.ForeignKey("department.id"),
        nullable=True,
        index=True,
    )
    feature = db.Column(db.String(80), nullable=False, index=True)
    metric_key = db.Column(db.String(120), nullable=False, index=True)
    metric_value = db.Column(db.Float, nullable=False, default=0.0)
    metric_unit = db.Column(db.String(40), nullable=False, default="count")
    dimensions_json = db.Column(db.Text, nullable=False, default="{}")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    site = db.relationship("Site")
    department = db.relationship("Department")

    __table_args__ = (
        db.UniqueConstraint(
            "period_type",
            "period_start",
            "site_id",
            "department_id",
            "feature",
            "metric_key",
            "dimensions_json",
            name="uq_operational_kpi_scope_metric",
        ),
        db.Index(
            "ix_operational_kpi_scope",
            "period_type",
            "period_start",
            "site_id",
            "department_id",
        ),
        db.Index("ix_operational_kpi_feature_metric", "feature", "metric_key"),
    )

    def dimensions(self):
        """Return aggregate dimensions as a safe dictionary."""
        try:
            data = json.loads(self.dimensions_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def to_dict(self):
        """Return a JSON-serializable aggregate payload."""
        return {
            "id": self.id,
            "period_type": self.period_type,
            "period_start": self.period_start.isoformat(),
            "site_id": self.site_id,
            "department_id": self.department_id,
            "feature": self.feature,
            "metric_key": self.metric_key,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "dimensions": self.dimensions(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
