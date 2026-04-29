from datetime import date, datetime
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
        return {"id": self.id, "name": self.name}


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum(Role), nullable=False, default=Role.PRODUKTION)
    department_id = db.Column(db.Integer, db.ForeignKey("department.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="users")
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

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == Role.MASTER_ADMIN

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role.value,
            "department": self.department.to_dict() if self.department else None,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    department = db.relationship("Department", back_populates="errors")

    def to_dict(self):
        return {
            "id": self.id,
            "machine": self.machine,
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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    documents = db.relationship(
        "EmployeeDocument",
        back_populates="employee",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "personnel_number": self.personnel_number,
            "name": self.name,
            "birth_date": self.birth_date.isoformat() if self.birth_date else None,
            "city": self.city,
            "street": self.street,
            "postal_code": self.postal_code,
            "department": self.department,
            "shift_model": self.shift_model,
            "current_shift": self.current_shift,
            "team": self.team,
            "salary_group": self.salary_group,
            "qualifications": self.qualifications,
            "favorite_machine": self.favorite_machine,
            "documents": [document.to_dict() for document in self.documents],
            "created_at": self.created_at.isoformat(),
        }


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
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    entries = db.relationship(
        "ShiftPlanEntry",
        back_populates="plan",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "start_date": self.start_date.isoformat(),
            "days": self.days,
            "rhythm": self.rhythm,
            "preferences": self.preferences,
            "notes": self.notes,
            "entries": [entry.to_dict() for entry in self.entries],
            "created_at": self.created_at.isoformat(),
        }


class ShiftPlanEntry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("shift_plan.id"), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"))
    work_date = db.Column(db.Date, nullable=False)
    shift = db.Column(db.String(80), nullable=False)
    start_time = db.Column(db.String(5), nullable=False)
    end_time = db.Column(db.String(5), nullable=False)
    notes = db.Column(db.Text, nullable=False, default="")

    plan = db.relationship("ShiftPlan", back_populates="entries")
    employee = db.relationship("Employee")
    machine = db.relationship("Machine")

    def to_dict(self):
        return {
            "id": self.id,
            "employee": self.employee.to_dict() if self.employee else None,
            "machine": self.machine.to_dict() if self.machine else None,
            "work_date": self.work_date.isoformat(),
            "shift": self.shift,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "notes": self.notes,
        }
