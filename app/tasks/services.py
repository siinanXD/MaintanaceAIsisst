from datetime import date, datetime
from sqlalchemy.exc import SQLAlchemyError

from app.extensions import db
from app.models import Department, Priority, Role, Task, TaskStatus
from app.services.ai_service import AIServiceError, MockAIProvider, get_ai_provider


def parse_date(value):
    """Parse an ISO date or default to today."""
    if not value:
        return date.today()
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("due_date must use YYYY-MM-DD") from exc


def parse_enum(enum_cls, value, default=None):
    """Parse an enum value with a helpful validation error."""
    if not value:
        return default
    try:
        return enum_cls(value)
    except ValueError as exc:
        valid = ", ".join(item.value for item in enum_cls)
        raise ValueError(f"Invalid value '{value}'. Use one of: {valid}") from exc


def get_department_for_payload(data, user):
    """Resolve and authorize the department from request data."""
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
    """Return the query for tasks visible to the user."""
    query = Task.query
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(Task.department_id == user.department_id)
    return query


def create_task(data, user):
    """Create a task for the current user."""
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
    """Update a task for the current user."""
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


def start_task(task, user):
    """Mark a task as in progress and assign it to the given user."""
    if task.status == TaskStatus.DONE:
        return None, {"error": "Done tasks cannot be started"}, 400
    if task.status == TaskStatus.CANCELLED:
        return None, {"error": "Cancelled tasks cannot be started"}, 400
    if task.status == TaskStatus.IN_PROGRESS:
        return None, {"error": "Task is already in progress"}, 409

    task.status = TaskStatus.IN_PROGRESS
    task.current_worker = user
    task.started_at = datetime.utcnow()
    task.completed_by_user = None
    task.completed_at = None

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while starting task"}, 500

    return task, None, 200


def complete_task(task, user):
    """Mark a task as done and store who completed it."""
    if task.status == TaskStatus.DONE:
        return None, {"error": "Task is already done"}, 409
    if task.status == TaskStatus.CANCELLED:
        return None, {"error": "Cancelled tasks cannot be completed"}, 400

    task.status = TaskStatus.DONE
    task.completed_by_user = user
    task.completed_at = datetime.utcnow()

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return None, {"error": "Database error while completing task"}, 500

    return task, None, 200


def validate_task_payload(data, require_title=True):
    """Validate task payload before creating or updating a task."""
    if require_title and not data.get("title"):
        raise ValueError("title is required")

    if "title" in data and not str(data["title"]).strip():
        raise ValueError("title must not be empty")


def suggest_task_from_text(data, user):
    """Build a non-persisted task suggestion using the configured AI provider."""
    text = str(data.get("text") or "").strip()
    if not text:
        return None, {"error": "text is required"}, 400
    if len(text) > 2000:
        return None, {"error": "text must not exceed 2000 characters"}, 400

    user_context = {
        "role": user.role.value,
        "department": user.department.name if user.department else "",
    }
    try:
        suggestion = get_ai_provider().suggest_task(text, user_context)
    except AIServiceError:
        suggestion = MockAIProvider().suggest_task(text, user_context)

    normalized = normalize_task_suggestion(suggestion, text, user)
    return normalized, None, 200


def normalize_task_suggestion(suggestion, original_text, user):
    """Validate and normalize an AI task suggestion."""
    suggestion = suggestion or {}
    department_name = suggestion.get("department")
    if user.role != Role.MASTER_ADMIN and user.department:
        department_name = user.department.name
    if not Department.query.filter_by(name=department_name).first():
        department_name = user.department.name if user.department else "Instandhaltung"

    priority = suggestion.get("priority", Priority.NORMAL.value)
    if priority not in {item.value for item in Priority}:
        priority = Priority.NORMAL.value

    status = suggestion.get("status", TaskStatus.OPEN.value)
    if status not in {item.value for item in TaskStatus}:
        status = TaskStatus.OPEN.value

    title = str(suggestion.get("title") or original_text[:80]).strip()
    return {
        "title": title[:160],
        "description": str(suggestion.get("description") or original_text).strip(),
        "department": department_name,
        "priority": priority,
        "status": status,
        "possible_cause": str(suggestion.get("possible_cause") or "").strip(),
        "recommended_action": str(
            suggestion.get("recommended_action") or ""
        ).strip(),
    }
