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


def prioritize_visible_tasks(data, user):
    """Return non-persisted AI priorities for tasks visible to the user."""
    try:
        status = parse_enum(TaskStatus, data.get("status"), None)
        limit = parse_priority_limit(data.get("limit", 20))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    query = visible_tasks_query(user)
    if status:
        query = query.filter(Task.status == status)

    tasks = query.order_by(Task.due_date.asc(), Task.id.desc()).limit(limit).all()
    serialized_tasks = [task.to_dict() for task in tasks]
    context = {
        "role": user.role.value,
        "department": user.department.name if user.department else "",
    }

    try:
        provider_result = get_ai_provider().prioritize_tasks(serialized_tasks, context)
    except AIServiceError:
        provider_result = MockAIProvider().prioritize_tasks(serialized_tasks, context)

    priorities = normalize_task_priorities(provider_result, tasks)
    return priorities, None, 200


def parse_priority_limit(value):
    """Parse and validate a task prioritization limit."""
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer between 1 and 100") from exc

    if limit < 1 or limit > 100:
        raise ValueError("limit must be an integer between 1 and 100")
    return limit


def normalize_task_priorities(provider_result, tasks):
    """Normalize provider priorities and attach full task payloads."""
    provider_items = _provider_priority_items(provider_result)
    priority_by_task_id = {
        int(item["task_id"]): item
        for item in provider_items
        if _has_valid_task_id(item)
    }
    fallback_items = MockAIProvider().prioritize_tasks(
        [task.to_dict() for task in tasks],
        {},
    )["priorities"]
    fallback_by_task_id = {item["task_id"]: item for item in fallback_items}

    normalized = []
    for task in tasks:
        item = priority_by_task_id.get(task.id, fallback_by_task_id[task.id])
        normalized.append(
            {
                "task": task.to_dict(),
                "score": _clamped_score(item.get("score")),
                "risk_level": _valid_risk_level(item.get("risk_level")),
                "reason": str(item.get("reason") or "").strip()[:500],
                "recommended_action": str(
                    item.get("recommended_action") or ""
                ).strip()[:500],
            }
        )

    return sorted(normalized, key=lambda item: item["score"], reverse=True)


def _provider_priority_items(provider_result):
    """Return provider priority items from a dict or list payload."""
    if isinstance(provider_result, list):
        return provider_result
    if isinstance(provider_result, dict):
        priorities = provider_result.get("priorities", [])
        if isinstance(priorities, list):
            return priorities
    return []


def _has_valid_task_id(item):
    """Return whether a provider priority item references a task id."""
    if not isinstance(item, dict):
        return False
    try:
        int(item.get("task_id"))
    except (TypeError, ValueError):
        return False
    return True


def _clamped_score(value):
    """Return a score constrained to the public 0-100 range."""
    try:
        score = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(100, score))


def _valid_risk_level(value):
    """Return a supported risk level or derive low as the safe default."""
    if value in {"low", "medium", "high", "critical"}:
        return value
    return "low"


def create_task(data, user):
    """Create a task for the current user."""
    try:
        validate_task_payload(data, require_title=True)
        department = get_department_for_payload(data, user)
        requested_status = parse_enum(TaskStatus, data.get("status"), TaskStatus.OPEN)

        task = Task(
            title=data["title"].strip(),
            description=data.get("description", ""),
            priority=parse_enum(Priority, data.get("priority"), Priority.NORMAL),
            status=TaskStatus.OPEN,
            due_date=parse_date(data.get("due_date")),
            department=department,
            created_by=user.id,
        )
        update_task_status(task, requested_status, user)
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
            status = parse_enum(TaskStatus, data["status"], task.status)
            update_task_status(task, status, user)
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


def update_task_status(task, new_status, user):
    """Apply a status change and keep workflow tracking fields consistent."""
    if task.status == new_status:
        return

    task.status = new_status
    if new_status == TaskStatus.OPEN:
        task.current_worker = None
        task.started_at = None
        task.completed_by_user = None
        task.completed_at = None
    elif new_status == TaskStatus.IN_PROGRESS:
        task.current_worker = user
        task.started_at = task.started_at or datetime.utcnow()
        task.completed_by_user = None
        task.completed_at = None
    elif new_status == TaskStatus.DONE:
        task.current_worker = task.current_worker or user
        task.started_at = task.started_at or datetime.utcnow()
        task.completed_by_user = user
        task.completed_at = datetime.utcnow()
    elif new_status == TaskStatus.CANCELLED:
        task.completed_by_user = None
        task.completed_at = None


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
