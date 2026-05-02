from flask import Blueprint, jsonify, request, send_from_directory

from app.models import Employee
from app.responses import error_response, service_error_response
from app.security import (
    current_user,
    dashboard_permission_required,
    employee_access_level,
    employee_access_required,
)
import app.services.employee_service as employee_svc


employees_bp = Blueprint("employees", __name__)


@employees_bp.get("")
@dashboard_permission_required("employees", "view")
@employee_access_required("basic")
def list_employees():
    """Return employees filtered by the current user's access level."""
    access_level = employee_access_level(current_user())
    return jsonify([e.to_dict(access_level) for e in employee_svc.list_employees()])


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
    employee = Employee.query.get_or_404(employee_id)
    updated, error, status = employee_svc.update_employee(employee, request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    return jsonify(updated.to_dict())


@employees_bp.delete("/<int:employee_id>")
@dashboard_permission_required("employees", "write")
@employee_access_required("confidential")
def delete_employee(employee_id):
    """Delete an employee and related documents."""
    employee = Employee.query.get_or_404(employee_id)
    _, error, status = employee_svc.delete_employee(employee)
    if error:
        return service_error_response(error, status)
    return "", 204


@employees_bp.post("/<int:employee_id>/documents")
@dashboard_permission_required("employees", "write")
@employee_access_required("confidential")
def upload_document(employee_id):
    """Upload a confidential document for an employee."""
    employee = Employee.query.get_or_404(employee_id)
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
