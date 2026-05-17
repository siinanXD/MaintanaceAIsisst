"""Employee API routes."""

from flask import Blueprint, jsonify, request, send_from_directory
from sqlalchemy.orm import joinedload, selectinload

import app.services.employee_service as employee_svc
from app.extensions import db
from app.models import Employee, EmployeeMachineQualification
from app.responses import error_response, paginate_query, service_error_response
from app.security import (
    current_user,
    dashboard_permission_required,
    employee_access_level,
    employee_access_required,
)
from app.services.qualification_service import (
    qualification_matrix,
    update_employee_qualifications,
)

employees_bp = Blueprint("employees", __name__)


@employees_bp.get("")
@dashboard_permission_required("employees", "view")
@employee_access_required("basic")
def list_employees():
    """Return employees filtered by the current user's access level with optional pagination.

    Query params:
        page  — page number (default 1)
        limit — items per page, 1-100 (default 20)
    """
    access_level = employee_access_level(current_user())
    query = Employee.query.options(
        joinedload(Employee.favorite_machine_rel),
        selectinload(Employee.documents),
        selectinload(Employee.machine_qualifications).joinedload(
            EmployeeMachineQualification.machine
        ),
    ).order_by(Employee.name.asc(), Employee.id.asc())
    return paginate_query(query, lambda e: e.to_dict(access_level))


@employees_bp.get("/qualifications")
@dashboard_permission_required("employees", "view")
@employee_access_required("shift")
def list_qualifications():
    """Return the structured employee-machine qualification matrix."""
    return jsonify(qualification_matrix())


@employees_bp.post("")
@dashboard_permission_required("employees", "write")
@employee_access_required("confidential")
def create_employee():
    """Create an employee with confidential personnel data."""
    employee, error, status = employee_svc.create_employee(request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    return jsonify(employee.to_dict()), status


@employees_bp.put("/<int:employee_id>")
@dashboard_permission_required("employees", "write")
@employee_access_required("confidential")
def update_employee(employee_id):
    """Update an employee with confidential personnel data."""
    employee = db.get_or_404(Employee, employee_id)
    updated, error, status = employee_svc.update_employee(
        employee, request.get_json(silent=True) or {}
    )
    if error:
        return service_error_response(error, status)
    return jsonify(updated.to_dict())


@employees_bp.put("/<int:employee_id>/qualifications")
@dashboard_permission_required("employees", "write")
@employee_access_required("shift")
def update_qualifications(employee_id):
    """Replace structured machine qualifications for one employee."""
    employee = db.get_or_404(Employee, employee_id)
    payload, error, status = update_employee_qualifications(
        employee,
        request.get_json(silent=True) or {},
    )
    if error:
        return service_error_response(error, status)
    return jsonify(payload), status


@employees_bp.delete("/<int:employee_id>")
@dashboard_permission_required("employees", "write")
@employee_access_required("confidential")
def delete_employee(employee_id):
    """Delete an employee and related documents."""
    employee = db.get_or_404(Employee, employee_id)
    _, error, status = employee_svc.delete_employee(employee)
    if error:
        return service_error_response(error, status)
    return "", 204


@employees_bp.post("/<int:employee_id>/documents")
@dashboard_permission_required("employees", "write")
@employee_access_required("confidential")
def upload_document(employee_id):
    """Upload a confidential document for an employee."""
    employee = db.get_or_404(Employee, employee_id)
    file = request.files.get("document")
    document, error, status = employee_svc.upload_employee_document(employee, file)
    if error:
        return service_error_response(error, status)
    return jsonify(document.to_dict()), status


@employees_bp.get("/<int:employee_id>/documents/<int:document_id>")
@dashboard_permission_required("employees", "view")
@employee_access_required("confidential")
def download_document(employee_id, document_id):
    """Download a confidential employee document."""
    document = employee_svc.get_employee_document(employee_id, document_id)
    if not document:
        return error_response("Document not found", 404)
    upload_dir = employee_svc.employee_upload_dir(employee_id)
    return send_from_directory(
        upload_dir,
        document.stored_filename,
        as_attachment=True,
        download_name=document.original_filename,
    )
