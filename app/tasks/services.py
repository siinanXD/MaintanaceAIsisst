"""
Backward-compatible re-exports.

Business logic has moved to app.services.task_service.
Import directly from there in new code.
"""
from app.services.task_service import (  # noqa: F401
    complete_task,
    create_task,
    get_department_for_payload,
    normalize_task_priorities,
    normalize_task_suggestion,
    parse_date,
    parse_enum,
    parse_priority_limit,
    prioritize_visible_tasks,
    start_task,
    suggest_task_from_text,
    update_task,
    update_task_status,
    validate_task_payload,
    visible_tasks_query,
)
