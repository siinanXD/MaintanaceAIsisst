from datetime import date, datetime, timezone
from enum import Enum

from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db


class Role(str, Enum):
    MASTER_ADMIN = "master_admin"
    IT = "it"
    VERWALTUNG = "verwaltung"
    INSTANDHALTUNG = "instandhaltung"
    PRODUKTION = "produktion"
    PERSONALABTEILUNG = "personalabteilung"


class Priority(str, Enum):
    URGENT = "urgent"
    SOON = "soon"
    NORMAL = "normal"


class TaskStatus(str, Enum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class Department(db.Model):
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


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.PRODUKTION)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="users")
    employee = db.relationship("Employee", foreign_keys=[employee_id])
    created_tasks = db.relationship(
        "Task",
        foreign_keys="Task.created_by",
        back_populates="creator",
    )
    assigned_tasks = db.relationship(
        "Task",
        foreign_keys="Task.current_worker_id",
        back_populates="current_worker",
    )
    completed_tasks = db.relationship(
        "Task",
        foreign_keys="Task.completed_by_id",
        back_populates="completed_by_user",
    )
    dashboard_permissions = db.relationship(
        "DashboardPermission",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password):
        """Hash and store the user's password."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Return whether the provided password matches the stored hash."""
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        """Return whether the user has the master administrator role."""
        return self.role == Role.MASTER_ADMIN

    def to_dict(self):
        """Return a JSON-serializable representation of the user."""
        from app.permissions import serialize_permissions

        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "department": self.department.to_dict() if self.department else None,
            "employee": self.employee.to_dict("basic") if self.employee else None,
            "employee_id": self.employee_id,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "permissions": serialize_permissions(self),
        }


class Task(db.Model):
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
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
            "current_worker": (
                self.current_worker.to_dict() if self.current_worker else None
            ),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_by": self.completed_by_id,
            "completed_by_user": (
                self.completed_by_user.to_dict() if self.completed_by_user else None
            ),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class ErrorEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    machine = db.Column(db.String(160), nullable=False)
    error_code = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, nullable=False, default="")
    possible_causes = db.Column(db.Text, nullable=False, default="")
    solution = db.Column(db.Text, nullable=False, default="")
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="errors")
    machine_rel = db.relationship("Machine", foreign_keys=[machine_id])

    def to_dict(self):
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


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AIFeedback(db.Model):
    """Store user feedback for AI answers."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    rating = db.Column(db.String(40), nullable=False)
    comment = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship("User")

    def to_dict(self):
        """Return a JSON-serializable representation of the feedback."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
        }


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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


class Employee(db.Model):
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    documents = db.relationship(
        "EmployeeDocument",
        back_populates="employee",
        cascade="all, delete-orphan",
    )
    favorite_machine_rel = db.relationship("Machine", foreign_keys=[favorite_machine_id])

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
                    self.favorite_machine_rel.to_dict()
                    if self.favorite_machine_rel
                    else None
                ),
            }
        )
        if access_level == "shift":
            return base_data

        base_data.update(
            {
                "birth_date": (
                    self.birth_date.isoformat() if self.birth_date else None
                ),
                "city": self.city,
                "street": self.street,
                "postal_code": self.postal_code,
                "salary_group": self.salary_group,
                "documents": [document.to_dict() for document in self.documents],
                "created_at": self.created_at.isoformat(),
            }
        )
        return base_data


class EmployeeDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120), nullable=False, default="")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    employee = db.relationship("Employee", back_populates="documents")

    def to_dict(self):
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "uploaded_at": self.uploaded_at.isoformat(),
            "download_url": f"/api/employees/{self.employee_id}/documents/{self.id}",
        }


class Machine(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), unique=True, nullable=False)
    produced_item = db.Column(db.String(160), nullable=False, default="")
    required_employees = db.Column(db.Integer, nullable=False, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    materials = db.relationship("InventoryMaterial", back_populates="machine")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "produced_item": self.produced_item,
            "required_employees": self.required_employees,
            "created_at": self.created_at.isoformat(),
        }


class InventoryMaterial(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    unit_cost = db.Column(db.Float, nullable=False, default=0)
    quantity = db.Column(db.Integer, nullable=False, default=0)
    manufacturer = db.Column(db.String(160), nullable=False, default="")
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    machine = db.relationship("Machine", back_populates="materials")

    @property
    def total_value(self):
        """Return the total material value based on unit cost and quantity."""
        return round((self.unit_cost or 0) * (self.quantity or 0), 2)

    def to_dict(self):
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


class ShiftPlan(db.Model):
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    entries = db.relationship(
        "ShiftPlanEntry",
        back_populates="plan",
        cascade="all, delete-orphan",
    )
    creator = db.relationship("User", foreign_keys=[created_by])

    @property
    def is_published(self):
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
            "entries": [
                entry.to_dict(employee_access_level) for entry in self.entries
            ],
            "created_at": self.created_at.isoformat(),
        }


class ShiftPlanEntry(db.Model):
    __table_args__ = (
        db.UniqueConstraint(
            "plan_id", "employee_id", "work_date",
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

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
    changed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
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


class TokenBlocklist(db.Model):
    """Stores revoked JWT JTIs so logout is enforced server-side."""

    __tablename__ = "token_blocklist"

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)
    revoked_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<TokenBlocklist jti={self.jti}>"
