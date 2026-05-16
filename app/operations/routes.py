"""Operations KPI and event API routes."""

from flask import Blueprint, request

from app.responses import error_response, success_response
from app.security import current_user, dashboard_permission_required
from app.services.operations_tracking_service import (
    ai_quality_metrics,
    filtered_events_query,
    inventory_metrics,
    machine_metrics,
    operations_summary,
    task_metrics,
    workforce_metrics,
)

operations_bp = Blueprint("operations", __name__)


@operations_bp.get("/summary")
@dashboard_permission_required("dashboard", "view")
def summary():
    """Return cross-feature operations KPIs."""
    try:
        payload = operations_summary(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(payload, message="Operations summary loaded")


@operations_bp.get("/events")
@dashboard_permission_required("dashboard", "view")
def events():
    """Return filtered pseudonymized operations events."""
    try:
        query = filtered_events_query(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    limit = min(max(request.args.get("limit", default=50, type=int), 1), 200)
    offset = max(request.args.get("offset", default=0, type=int), 0)
    total = query.count()
    items = query.offset(offset).limit(limit).all()
    return success_response(
        {
            "items": [event.to_dict() for event in items],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
        message="Operations events loaded",
    )


@operations_bp.get("/tasks")
@dashboard_permission_required("tasks", "view")
def tasks():
    """Return task operations KPIs."""
    try:
        payload = task_metrics(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(payload, message="Task operations loaded")


@operations_bp.get("/machines")
@dashboard_permission_required("machines", "view")
def machines():
    """Return machine operations KPIs."""
    try:
        payload = machine_metrics(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(payload, message="Machine operations loaded")


@operations_bp.get("/inventory")
@dashboard_permission_required("inventory", "view")
def inventory():
    """Return inventory operations KPIs."""
    try:
        payload = inventory_metrics(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(payload, message="Inventory operations loaded")


@operations_bp.get("/workforce")
@dashboard_permission_required("shiftplans", "view")
def workforce():
    """Return workforce and shift planning KPIs."""
    try:
        payload = workforce_metrics(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(payload, message="Workforce operations loaded")


@operations_bp.get("/ai-quality")
@dashboard_permission_required("dashboard", "view")
def ai_quality():
    """Return AI quality and cost KPIs."""
    try:
        payload = ai_quality_metrics(request.args, current_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(payload, message="AI quality operations loaded")
