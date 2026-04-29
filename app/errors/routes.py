from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.errors.services import (
    create_error_entry,
    search_errors,
    update_error_entry,
    visible_errors_query,
)
from app.extensions import db
from app.models import ErrorEntry
from app.security import current_user, same_department_or_admin


errors_bp = Blueprint("errors", __name__)


@errors_bp.get("")
@jwt_required()
def list_errors():
    user = current_user()
    entries = visible_errors_query(user).order_by(ErrorEntry.error_code.asc()).all()
    return jsonify([entry.to_dict() for entry in entries])


@errors_bp.post("")
@jwt_required()
def add_error():
    entry, error, status = create_error_entry(request.get_json(silent=True) or {}, current_user())
    if error:
        return jsonify(error), status
    return jsonify(entry.to_dict()), status


@errors_bp.get("/search")
@jwt_required()
def search():
    entries = search_errors(request.args.get("query", ""), current_user())
    return jsonify([entry.to_dict() for entry in entries])


@errors_bp.get("/<int:error_id>")
@jwt_required()
def get_error(error_id):
    entry = ErrorEntry.query.get_or_404(error_id)
    if not same_department_or_admin(entry):
        return jsonify({"error": "Forbidden"}), 403
    return jsonify(entry.to_dict())


@errors_bp.put("/<int:error_id>")
@jwt_required()
def edit_error(error_id):
    entry = ErrorEntry.query.get_or_404(error_id)
    if not same_department_or_admin(entry):
        return jsonify({"error": "Forbidden"}), 403
    updated, error, status = update_error_entry(
        entry,
        request.get_json(silent=True) or {},
        current_user(),
    )
    if error:
        return jsonify(error), status
    return jsonify(updated.to_dict())


@errors_bp.delete("/<int:error_id>")
@jwt_required()
def delete_error(error_id):
    entry = ErrorEntry.query.get_or_404(error_id)
    if not same_department_or_admin(entry):
        return jsonify({"error": "Forbidden"}), 403
    db.session.delete(entry)
    db.session.commit()
    return "", 204
