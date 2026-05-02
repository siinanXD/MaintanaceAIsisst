from datetime import date

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models import Priority, Task, TaskStatus
from app.responses import error_response, paginate_query, service_error_response, success_response
from app.security import (
    current_user,
    dashboard_permission_required,
    same_department_or_admin,
)
from app.services.task_service import (
    create_task,
    delete_task,
    prioritize_visible_tasks,
    start_task,
    suggest_task_from_text,
    update_task,
    visible_tasks_query,
)
from app.services.workflow_service import complete_task_workflow


tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.get("")
@dashboard_permission_required("tasks", "view")
def list_tasks():
    """Return visible tasks for the current user with optional pagination and filters.

    Query params:
        status   — open | in_progress | done | cancelled
        priority — urgent | soon | normal
        page     — page number (default 1)
        limit    — items per page, 1-100 (default 20)
    """
    user = current_user()
    query = visible_tasks_query(user)
    status = request.args.get("status")
    priority = request.args.get("priority")
    try:
        if status:
            query = query.filter(Task.status == TaskStatus(status))
        if priority:
            query = query.filter(Task.priority == Priority(priority))
    except ValueError:
        return error_response("Invalid status or priority filter", 400)
    query = query.order_by(Task.due_date.asc(), Task.id.desc())
    return paginate_query(query, lambda t: t.to_dict())


@tasks_bp.post("")
@dashboard_permission_required("tasks", "write")
def add_task():
    """Create a task in an allowed department."""
    task, error, status = create_task(request.get_json(silent=True) or {}, current_user())
    if error:
        return service_error_response(error, status)
    return jsonify(task.to_dict()), status


@tasks_bp.post("/suggest")
@dashboard_permission_required("tasks", "write")
def suggest_task():
    """Return a non-persisted AI task suggestion from free text."""
    data = request.get_json(silent=True) or {}
    suggestion, error, status = suggest_task_from_text(data, current_user())
    if error:
        return service_error_response(error, status)
    return success_response(suggestion, message="Task suggestion generated")


@tasks_bp.post("/prioritize")
@dashboard_permission_required("tasks", "view")
def prioritize_tasks():
    """Return non-persisted priorities for visible tasks."""
    priorities, error, status = prioritize_visible_tasks(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(priorities, status, "Task priorities loaded")


@tasks_bp.get("/today")
@dashboard_permission_required("tasks", "view")
def today_tasks():
    """Return today's visible tasks."""
    user = current_user()
    tasks = (
        visible_tasks_query(user)
        .filter(Task.due_date == date.today())
        .order_by(Task.priority.asc(), Task.id.desc())
        .all()
    )
    return jsonify([task.to_dict() for task in tasks])


@tasks_bp.get("/<int:task_id>")
@dashboard_permission_required("tasks", "view")
def get_task(task_id):
    """Return a visible task by id."""
    task = Task.query.get_or_404(task_id)
    if not same_department_or_admin(task):
        return error_response("Forbidden", 403)
    return jsonify(task.to_dict())


@tasks_bp.put("/<int:task_id>")
@dashboard_permission_required("tasks", "write")
def edit_task(task_id):
    """Update a visible task."""
    task = Task.query.get_or_404(task_id)
    if not same_department_or_admin(task):
        return error_response("Forbidden", 403)
    updated, error, status = update_task(task, request.get_json(silent=True) or {}, current_user())
    if error:
        return service_error_response(error, status)
    return jsonify(updated.to_dict())


@tasks_bp.post("/<int:task_id>/start")
@dashboard_permission_required("tasks", "write")
def start_task_endpoint(task_id):
    """Start a visible task for the current user."""
    task = db.session.get(Task, task_id)
    if not task:
        return error_response("Task not found", 404)
    if not same_department_or_admin(task):
        return error_response("Forbidden", 403)

    updated, error, status = start_task(task, current_user())
    if error:
        return service_error_response(error, status)
    return success_response(updated.to_dict(), status, "Task started")


@tasks_bp.post("/<int:task_id>/complete")
@dashboard_permission_required("tasks", "write")
def complete_task_endpoint(task_id):
    """Complete a visible task for the current user."""
    task = db.session.get(Task, task_id)
    if not task:
        return error_response("Task not found", 404)
    if not same_department_or_admin(task):
        return error_response("Forbidden", 403)

    updated, document, error, status = complete_task_workflow(
        task,
        current_user(),
        request.get_json(silent=True) or {},
    )
    if error:
        return service_error_response(error, status)
    payload = updated.to_dict()
    if document:
        payload["generated_document"] = document.to_dict()
    return success_response(payload, status, "Task completed")


@tasks_bp.delete("/<int:task_id>")
@dashboard_permission_required("tasks", "write")
def delete_task_endpoint(task_id):
    """Delete a visible task."""
    task = Task.query.get_or_404(task_id)
    if not same_department_or_admin(task):
        return error_response("Forbidden", 403)
    _, error, status = delete_task(task)
    if error:
        return service_error_response(error, status)
    return "", 204
