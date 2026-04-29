from datetime import date

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.extensions import db
from app.models import Priority, Task, TaskStatus
from app.security import current_user, same_department_or_admin
from app.tasks.services import (
    complete_task,
    create_task,
    start_task,
    update_task,
    visible_tasks_query,
)


tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.get("")
@jwt_required()
def list_tasks():
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
        return jsonify({"error": "Invalid status or priority filter"}), 400
    tasks = query.order_by(Task.due_date.asc(), Task.id.desc()).all()
    return jsonify([task.to_dict() for task in tasks])


@tasks_bp.post("")
@jwt_required()
def add_task():
    task, error, status = create_task(request.get_json(silent=True) or {}, current_user())
    if error:
        return jsonify(error), status
    return jsonify(task.to_dict()), status


@tasks_bp.get("/today")
@jwt_required()
def today_tasks():
    user = current_user()
    tasks = (
        visible_tasks_query(user)
        .filter(Task.due_date == date.today())
        .order_by(Task.priority.asc(), Task.id.desc())
        .all()
    )
    return jsonify([task.to_dict() for task in tasks])


@tasks_bp.get("/<int:task_id>")
@jwt_required()
def get_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not same_department_or_admin(task):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(task.to_dict())


@tasks_bp.put("/<int:task_id>")
@jwt_required()
def edit_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not same_department_or_admin(task):
        return jsonify({"error": "Forbidden"}), 403
    updated, error, status = update_task(task, request.get_json(silent=True) or {}, current_user())
    if error:
        return jsonify(error), status
    return jsonify(updated.to_dict())


@tasks_bp.post("/<int:task_id>/start")
@jwt_required()
def start_task_endpoint(task_id):
    """Start a visible task for the current user."""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not same_department_or_admin(task):
        return jsonify({"error": "Forbidden"}), 403

    updated, error, status = start_task(task, current_user())
    if error:
        return jsonify(error), status
    return jsonify(updated.to_dict()), status


@tasks_bp.post("/<int:task_id>/complete")
@jwt_required()
def complete_task_endpoint(task_id):
    """Complete a visible task for the current user."""
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    if not same_department_or_admin(task):
        return jsonify({"error": "Forbidden"}), 403

    updated, error, status = complete_task(task, current_user())
    if error:
        return jsonify(error), status
    return jsonify(updated.to_dict()), status


@tasks_bp.delete("/<int:task_id>")
@jwt_required()
def delete_task(task_id):
    task = Task.query.get_or_404(task_id)
    if not same_department_or_admin(task):
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(task)
    db.session.commit()
    return "", 204
