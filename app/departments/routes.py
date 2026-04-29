from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.departments.services import create_department, ensure_default_departments
from app.models import Department, Role
from app.security import roles_required


departments_bp = Blueprint("departments", __name__)


@departments_bp.get("")
@jwt_required()
def list_departments():
    ensure_default_departments()
    departments = Department.query.order_by(Department.name.asc()).all()
    return jsonify([department.to_dict() for department in departments])


@departments_bp.post("")
@roles_required(Role.MASTER_ADMIN)
def add_department():
    department, error, status = create_department((request.get_json(silent=True) or {}).get("name"))
    if error:
        return jsonify(error), status
    return jsonify(department.to_dict()), status
