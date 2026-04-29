from datetime import date
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Department, Priority, Role, Task, TaskStatus


def parse_date(value):
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must use YYYY-MM-DD") from exc


def parse_enum(enum_cls, value, default=None):
    if not value:
        return default
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid = ", ".join(item.value for item in enum_cls)
        raise ValueError(f"Invalid value '{value}'. Use one of: {valid}") from exc


def get_department_for_payload(data, user):
    department_id = data.get("department_id")
    department_name = data.get("department")
    department = None

    if department_id:
        department = Department.query.get(department_id)
    elif department_name:
        department = Department.query.filter_by(name=department_name).first()
    elif user.department_id:
        department = user.department

    if not department:
        raise ValueError("Valid department_id or department is required")
    if user.role != Role.MASTER_ADMIN and department.id != user.department_id:
        raise PermissionError("Users may only write tasks for their own department")
    return department


def visible_tasks_query(user):
    query = Task.query
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(Task.department_id == user.department_id)
    return query


def create_task(data, user):
    try:
        validate_task_payload(data, require_title=True)
        department = get_department_for_payload(data, user)

        task = Task(
            title=data["title"].strip(),
            description=data.get("description", ""),
            priority=parse_enum(Priority, data.get("priority"), Priority.NORMAL),
            status=parse_enum(TaskStatus, data.get("status"), TaskStatus.OPEN),
            due_date=parse_date(data.get("due_date")),
            department=department,
            created_by=user.id,
        )
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    db.session.add(task)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while creating task"}, 500

    return task, None, 201


def update_task(task, data, user):
    try:
        validate_task_payload(data, require_title=False)
        if "department_id" in data or "department" in data:
            task.department = get_department_for_payload(data, user)
        if "title" in data:
            task.title = data["title"].strip()
        if "description" in data:
            task.description = data["description"]
        if "priority" in data:
            task.priority = parse_enum(Priority, data["priority"], task.priority)
        if "status" in data:
            task.status = parse_enum(TaskStatus, data["status"], task.status)
        if "due_date" in data:
            task.due_date = parse_date(data["due_date"])
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while updating task"}, 500

    return task, None, 200


def validate_task_payload(data, require_title=True):
    """Validate task payload before creating or updating a task."""
    if require_title and not data.get("title"):
        raise ValueError("title is required")

    if "title" in data and not str(data["title"]).strip():
        raise ValueError("title must not be empty")
