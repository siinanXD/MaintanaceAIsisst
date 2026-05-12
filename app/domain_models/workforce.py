"""SQLAlchemy domain models for this bounded area."""

from app.domain_models.common import utc_now
from app.extensions import db


class Employee(db.Model):
    """Personnel record with confidential HR data, shift assignment, and qualifications."""

    id = db.Column(db.Integer, primary_key=True)
    personnel_number = db.Column(db.String(80), unique=True, nullable=False)
    name = db.Column(db.String(160), nullable=False)
    birth_date = db.Column(db.Date)
    city = db.Column(db.String(120), nullable=False, default="")
    street = db.Column(db.String(160), nullable=False, default="")
    postal_code = db.Column(db.String(20), nullable=False, default="")
    department = db.Column(db.String(120), nullable=False, default="")
    shift_model = db.Column(db.String(80), nullable=False, default="")
    current_shift = db.Column(db.String(120), nullable=False, default="")
    team = db.Column(db.Integer)
    salary_group = db.Column(db.String(80), nullable=False, default="")
    qualifications = db.Column(db.Text, nullable=False, default="")
    favorite_machine = db.Column(db.String(160), nullable=False, default="")
    favorite_machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    vacation_days_per_year = db.Column(db.Integer, nullable=False, default=30)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    documents = db.relationship(
        "EmployeeDocument",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    favorite_machine_rel = db.relationship("Machine", foreign_keys=[favorite_machine_id])
    vacation_requests = db.relationship(
        "VacationRequest", back_populates="employee", cascade="all, delete-orphan"
    )

    def to_dict(self, access_level="confidential"):
        """Return employee data filtered by the requested access level."""
        base_data = {
            "id": self.id,
            "personnel_number": self.personnel_number,
            "name": self.name,
            "department": self.department,
            "team": self.team,
        }
        if access_level in ("none", "basic"):
            return base_data

        base_data.update(
            {
                "shift_model": self.shift_model,
                "current_shift": self.current_shift,
                "qualifications": self.qualifications,
                "favorite_machine": self.favorite_machine,
                "favorite_machine_id": self.favorite_machine_id,
                "favorite_machine_obj": (
                    self.favorite_machine_rel.to_dict() if self.favorite_machine_rel else None
                ),
            }
        )
        if access_level == "shift":
            return base_data

        base_data.update(
            {
                "birth_date": (self.birth_date.isoformat() if self.birth_date else None),
                "city": self.city,
                "street": self.street,
                "postal_code": self.postal_code,
                "salary_group": self.salary_group,
                "documents": [document.to_dict() for document in self.documents],
                "created_at": self.created_at.isoformat(),
            }
        )
        return base_data


class ShiftPlan(db.Model):
    """AI-generated shift schedule covering a department for a defined date range."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    days = db.Column(db.Integer, nullable=False, default=7)
    rhythm = db.Column(db.String(160), nullable=False, default="")
    preferences = db.Column(db.Text, nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    department = db.Column(db.String(120), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="draft")
    published_at = db.Column(db.DateTime, nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    entries = db.relationship(
        "ShiftPlanEntry",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    creator = db.relationship("User", foreign_keys=[created_by])

    @property
    def is_published(self):
        """Return True when the plan has been published and is visible to workers."""
        return self.status == "published"

    def to_dict(self, employee_access_level="confidential"):
        """Return shift plan data with filtered employee fields."""
        return {
            "id": self.id,
            "title": self.title,
            "start_date": self.start_date.isoformat(),
            "days": self.days,
            "rhythm": self.rhythm,
            "preferences": self.preferences,
            "notes": self.notes,
            "department": self.department,
            "status": self.status,
            "published_at": self.published_at.isoformat() if self.published_at else None,
            "created_by": self.creator.username if self.creator else None,
            "entries": [entry.to_dict(employee_access_level) for entry in self.entries],
            "created_at": self.created_at.isoformat(),
        }


class ShiftPlanEntry(db.Model):
    """Single employee-machine-day assignment within a shift plan."""

    __table_args__ = (
        db.UniqueConstraint(
            "plan_id",
            "employee_id",
            "work_date",
            name="uq_entry_emp_day",
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("shift_plan.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"))
    work_date = db.Column(db.Date, nullable=False)
    shift = db.Column(db.String(80), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    plan = db.relationship("ShiftPlan", back_populates="entries")
    employee = db.relationship("Employee")
    machine = db.relationship("Machine")

    def to_dict(self, employee_access_level="confidential"):
        """Return shift plan entry data with filtered employee fields."""
        return {
            "id": self.id,
            "employee": (
                self.employee.to_dict(employee_access_level)
                if self.employee and employee_access_level != "none"
                else None
            ),
            "machine": self.machine.to_dict() if self.machine else None,
            "work_date": self.work_date.isoformat(),
            "shift": self.shift,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ShiftPlanChangeLog(db.Model):
    """Tracks every manual change to shift plan entries."""

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(
        db.Integer,
        db.ForeignKey("shift_plan_entry.id", ondelete="SET NULL"),
        nullable=True,
    )
    plan_id = db.Column(
        db.Integer,
        db.ForeignKey("shift_plan.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    changed_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    action = db.Column(db.String(20), nullable=False)
    field_name = db.Column(db.String(80), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)

    user = db.relationship("User", foreign_keys=[user_id])

    def to_dict(self):
        """Return a JSON-serializable representation of the changelog entry."""
        return {
            "id": self.id,
            "entry_id": self.entry_id,
            "plan_id": self.plan_id,
            "user": self.user.username if self.user else None,
            "changed_at": self.changed_at.isoformat(),
            "action": self.action,
            "field_name": self.field_name,
            "old_value": self.old_value,
            "new_value": self.new_value,
        }


class ShiftHandover(db.Model):
    """Digital shift handover log."""

    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(
        db.Integer, db.ForeignKey("shift_plan.id", ondelete="SET NULL"), nullable=True
    )
    department = db.Column(db.String(120), nullable=False, default="")
    shift_date = db.Column(db.Date, nullable=False)
    shift_type = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="open")
    handed_over_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    handed_over_at = db.Column(db.DateTime, nullable=True)
    content = db.Column(db.Text, nullable=False, default="")
    open_tasks = db.Column(db.Text, nullable=False, default="")
    machine_notes = db.Column(db.Text, nullable=False, default="")
    next_notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    plan = db.relationship("ShiftPlan")
    author = db.relationship("User", foreign_keys=[handed_over_by])

    def to_dict(self):
        """Return a JSON-serializable representation of the shift handover record."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "department": self.department,
            "shift_date": self.shift_date.isoformat(),
            "shift_type": self.shift_type,
            "status": self.status,
            "handed_over_by": self.author.username if self.author else None,
            "handed_over_at": self.handed_over_at.isoformat() if self.handed_over_at else None,
            "content": self.content,
            "open_tasks": self.open_tasks,
            "machine_notes": self.machine_notes,
            "next_notes": self.next_notes,
            "created_at": self.created_at.isoformat(),
        }


class VacationRequest(db.Model):
    """Employee vacation request with approval workflow."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    days_used = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="pending")
    requested_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    decided_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    employee = db.relationship("Employee", back_populates="vacation_requests")
    requester = db.relationship("User", foreign_keys=[requested_by])
    approver = db.relationship("User", foreign_keys=[approved_by])

    def to_dict(self):
        """Return a JSON-serializable representation of the vacation request."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee": self.employee.to_dict("basic") if self.employee else None,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "days_used": self.days_used,
            "status": self.status,
            "requested_by": self.requester.username if self.requester else None,
            "approved_by": self.approver.username if self.approver else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
