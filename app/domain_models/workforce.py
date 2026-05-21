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
        "VacationRequest",
        back_populates="employee",
        cascade="all, delete-orphan",
        foreign_keys="VacationRequest.employee_id",
    )
    machine_qualifications = db.relationship(
        "EmployeeMachineQualification",
        back_populates="employee",
        cascade="all, delete-orphan",
        order_by="EmployeeMachineQualification.machine_id.asc()",
    )

    __table_args__ = (
        db.Index("ix_employee_department_name", "department", "name"),
        db.Index("ix_employee_favorite_machine", "favorite_machine_id"),
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
                "machine_qualifications": [
                    qualification.to_dict() for qualification in self.machine_qualifications
                ],
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


class EmployeeMachineQualification(db.Model):
    """Structured machine qualification for shift planning decisions."""

    __table_args__ = (
        db.UniqueConstraint(
            "employee_id",
            "machine_id",
            name="uq_employee_machine_qualification",
        ),
        db.Index("ix_employee_machine_qualification_machine", "machine_id"),
        db.Index("ix_employee_machine_qualification_valid_until", "valid_until"),
    )

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=False)
    level = db.Column(db.String(40), nullable=False, default="trained")
    valid_until = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )

    employee = db.relationship("Employee", back_populates="machine_qualifications")
    machine = db.relationship("Machine")

    def is_valid_for(self, work_date):
        """Return whether the qualification is valid on the given date."""
        return not self.valid_until or self.valid_until >= work_date

    def to_dict(self):
        """Return a JSON-serializable machine qualification."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "employee": self.employee.to_dict("basic") if self.employee else None,
            "machine_id": self.machine_id,
            "machine": self.machine.to_dict() if self.machine else None,
            "level": self.level,
            "valid_until": self.valid_until.isoformat() if self.valid_until else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


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
    coverage_percent = db.Column(db.Float, nullable=False, default=0.0)
    conflict_count = db.Column(db.Integer, nullable=False, default=0)
    critical_conflict_count = db.Column(db.Integer, nullable=False, default=0)
    change_count = db.Column(db.Integer, nullable=False, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    entries = db.relationship(
        "ShiftPlanEntry",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.Index("ix_shift_plan_department_start", "department", "start_date"),
        db.Index("ix_shift_plan_status_start", "status", "start_date"),
    )

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
            "coverage_percent": self.coverage_percent,
            "conflict_count": self.conflict_count,
            "critical_conflict_count": self.critical_conflict_count,
            "change_count": self.change_count,
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
        db.Index("ix_shift_plan_entry_plan_date", "plan_id", "work_date"),
        db.Index("ix_shift_plan_entry_employee_date", "employee_id", "work_date"),
        db.Index("ix_shift_plan_entry_machine_date", "machine_id", "work_date"),
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
    area = db.Column(db.String(120), nullable=False, default="")
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    shift_date = db.Column(db.Date, nullable=False)
    shift_type = db.Column(db.String(40), nullable=False)
    previous_shift = db.Column(db.String(40), nullable=False, default="")
    next_shift = db.Column(db.String(40), nullable=False, default="")
    status = db.Column(db.String(20), nullable=False, default="open")
    production_status = db.Column(db.String(40), nullable=False, default="")
    machine_status = db.Column(db.String(40), nullable=False, default="")
    safety_notes = db.Column(db.Text, nullable=False, default="")
    material_notes = db.Column(db.Text, nullable=False, default="")
    responsible_employee = db.Column(db.String(160), nullable=False, default="")
    problem_category = db.Column(db.String(80), nullable=False, default="")
    cause = db.Column(db.Text, nullable=False, default="")
    action_taken = db.Column(db.Text, nullable=False, default="")
    duration_minutes = db.Column(db.Integer, nullable=False, default=0)
    follow_up_task = db.Column(db.Text, nullable=False, default="")
    involved_employees = db.Column(db.Text, nullable=False, default="")
    confirmed = db.Column(db.Boolean, nullable=False, default=False)
    handed_over_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    handed_over_at = db.Column(db.DateTime, nullable=True)
    content = db.Column(db.Text, nullable=False, default="")
    open_tasks = db.Column(db.Text, nullable=False, default="")
    machine_notes = db.Column(db.Text, nullable=False, default="")
    next_notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    plan = db.relationship("ShiftPlan")
    author = db.relationship("User", foreign_keys=[handed_over_by])
    machine = db.relationship("Machine", foreign_keys=[machine_id])

    __table_args__ = (
        db.Index("ix_shift_handover_department_date", "department", "shift_date"),
        db.Index("ix_shift_handover_status_date", "status", "shift_date"),
        db.Index("ix_shift_handover_machine_date", "machine_id", "shift_date"),
    )

    def to_dict(self):
        """Return a JSON-serializable representation of the shift handover record."""
        return {
            "id": self.id,
            "plan_id": self.plan_id,
            "department": self.department,
            "area": self.area,
            "machine_id": self.machine_id,
            "machine": self.machine.to_dict() if self.machine else None,
            "shift_date": self.shift_date.isoformat(),
            "shift_type": self.shift_type,
            "previous_shift": self.previous_shift,
            "next_shift": self.next_shift,
            "status": self.status,
            "production_status": self.production_status,
            "machine_status": self.machine_status,
            "safety_notes": self.safety_notes,
            "material_notes": self.material_notes,
            "responsible_employee": self.responsible_employee,
            "problem_category": self.problem_category,
            "cause": self.cause,
            "action_taken": self.action_taken,
            "duration_minutes": self.duration_minutes,
            "follow_up_task": self.follow_up_task,
            "involved_employees": self.involved_employees,
            "confirmed": self.confirmed,
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
    cancelled_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    representative_employee_id = db.Column(
        db.Integer,
        db.ForeignKey("employee.id"),
        nullable=True,
    )
    decided_at = db.Column(db.DateTime, nullable=True)
    cancelled_at = db.Column(db.DateTime, nullable=True)
    shift_type = db.Column(db.String(40), nullable=False, default="")
    reason = db.Column(db.String(160), nullable=False, default="")
    impact_level = db.Column(db.String(40), nullable=False, default="ok")
    impact_summary = db.Column(db.Text, nullable=False, default="")
    notes = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    employee = db.relationship(
        "Employee",
        back_populates="vacation_requests",
        foreign_keys=[employee_id],
    )
    requester = db.relationship("User", foreign_keys=[requested_by])
    approver = db.relationship("User", foreign_keys=[approved_by])
    canceller = db.relationship("User", foreign_keys=[cancelled_by])
    representative = db.relationship("Employee", foreign_keys=[representative_employee_id])

    __table_args__ = (
        db.Index("ix_vacation_request_employee_status", "employee_id", "status"),
        db.Index("ix_vacation_request_status_start", "status", "start_date"),
        db.Index(
            "ix_vacation_request_representative",
            "representative_employee_id",
            "start_date",
        ),
    )

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
            "cancelled_by": self.canceller.username if self.canceller else None,
            "decided_at": self.decided_at.isoformat() if self.decided_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "department": self.employee.department if self.employee else "",
            "shift_type": self.shift_type,
            "reason": self.reason,
            "representative_employee_id": self.representative_employee_id,
            "representative": (
                self.representative.to_dict("basic") if self.representative else None
            ),
            "impact_level": self.impact_level,
            "impact_summary": self.impact_summary,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }
