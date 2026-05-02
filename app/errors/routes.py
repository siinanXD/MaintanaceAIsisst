from flask import Blueprint, jsonify, request

from app.services.error_service import (
    analyze_error_description,
    create_error_entry,
    search_errors,
    suggest_similar_errors,
    update_error_entry,
    visible_errors_query,
)
from app.extensions import db
from app.models import ErrorEntry
from app.responses import error_response, service_error_response, success_response
from app.security import (
    current_user,
    dashboard_permission_required,
    same_department_or_admin,
)


errors_bp = Blueprint("errors", __name__)


@errors_bp.get("")
@dashboard_permission_required("errors", "view")
def list_errors():
    """Return visible error catalog entries."""
    user = current_user()
    entries = visible_errors_query(user).order_by(ErrorEntry.error_code.asc()).all()
    return jsonify([entry.to_dict() for entry in entries])


@errors_bp.post("")
@dashboard_permission_required("errors", "write")
def add_error():
    """Create an error catalog entry in an allowed department."""
    entry, error, status = create_error_entry(request.get_json(silent=True) or {}, current_user())
    if error:
        return service_error_response(error, status)
    return jsonify(entry.to_dict()), status


@errors_bp.post("/analyze")
@dashboard_permission_required("errors", "write")
def analyze_error():
    """Return a non-persisted AI analysis for an error description."""
    analysis, error, status = analyze_error_description(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(analysis, message="Error analysis generated")


@errors_bp.post("/similar")
@dashboard_permission_required("errors", "view")
def similar_errors():
    """Return visible error catalog entries similar to a description."""
    result, error, status = suggest_similar_errors(
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Similar errors loaded")


@errors_bp.get("/search")
@dashboard_permission_required("errors", "view")
def search():
    """Search visible error catalog entries."""
    entries = search_errors(request.args.get("query", ""), current_user())
    return jsonify([entry.to_dict() for entry in entries])


@errors_bp.get("/<int:error_id>")
@dashboard_permission_required("errors", "view")
def get_error(error_id):
    """Return a visible error catalog entry by id."""
    entry = ErrorEntry.query.get_or_404(error_id)
    if not same_department_or_admin(entry):
        return error_response("Forbidden", 403)
    return jsonify(entry.to_dict())


@errors_bp.put("/<int:error_id>")
@dashboard_permission_required("errors", "write")
def edit_error(error_id):
    """Update a visible error catalog entry."""
    entry = ErrorEntry.query.get_or_404(error_id)
    if not same_department_or_admin(entry):
        return error_response("Forbidden", 403)
    updated, error, status = update_error_entry(
        entry,
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return service_error_response(error, status)
    return jsonify(updated.to_dict())


@errors_bp.delete("/<int:error_id>")
@dashboard_permission_required("errors", "write")
def delete_error(error_id):
    """Delete a visible error catalog entry."""
    entry = ErrorEntry.query.get_or_404(error_id)
    if not same_department_or_admin(entry):
        return error_response("Forbidden", 403)
    db.session.delete(entry)
    db.session.commit()
    return "", 204
