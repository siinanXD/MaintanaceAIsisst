"""
Employee service layer.

All employee business logic lives here. Routes should call these functions
and do nothing more than validate input, call the service, and return a response.
"""

import logging
from datetime import date
from pathlib import Path
from uuid import uuid4

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Employee, EmployeeDocument, Machine


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_machine_id(name):
    """Return the Machine.id for an exact case-insensitive name match, or None."""
    if not name:
        return None
    machine = Machine.query.filter(Machine.name.ilike(name)).first()
    return machine.id if machine else None


def _parse_birth_date(value):
    """Parse an optional ISO date string into a date object, or return None."""
    if not value:
        return None
    return date.fromisoformat(value)


# ---------------------------------------------------------------------------
# File-storage helpers
# ---------------------------------------------------------------------------


def employee_upload_dir(employee_id):
    """Return (and create) the upload directory for the given employee id."""
    path = Path(current_app.config["UPLOAD_FOLDER"]) / "employees" / str(employee_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------------------------------------------------------------------
# Employee CRUD
# ---------------------------------------------------------------------------


def list_employees():
    """Return all employees ordered alphabetically by name."""
    return Employee.query.order_by(Employee.name.asc()).all()


def create_employee(data):
    """Create and persist a new employee record.

    Validates required fields and enforces unique personnel numbers.

    Returns:
        (employee, None, 201)                  on success
        (None, {"error": "..."}, 400/409/500)  on failure
    """
    required = ["personnel_number", "name"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return None, {"error": f"Missing fields: {', '.join(missing)}"}, 400

    if Employee.query.filter_by(personnel_number=data["personnel_number"]).first():
        return None, {"error": "personnel_number already exists"}, 409

    try:
        fav_machine = data.get("favorite_machine", "")
        employee = Employee(
            personnel_number=data["personnel_number"],
            name=data["name"],
            birth_date=_parse_birth_date(data.get("birth_date")),
            city=data.get("city", ""),
            street=data.get("street", ""),
            postal_code=data.get("postal_code", ""),
            department=data.get("department", ""),
            shift_model=data.get("shift_model", ""),
            current_shift=data.get("current_shift", ""),
            team=int(data["team"]) if data.get("team") else None,
            salary_group=data.get("salary_group", ""),
            qualifications=data.get("qualifications", ""),
            favorite_machine=fav_machine,
            favorite_machine_id=_resolve_machine_id(fav_machine),
        )
    except ValueError:
        return None, {"error": "Invalid birth_date or team"}, 400

    try:
        db.session.add(employee)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("employee_create_failed personnel_number=%s", data.get("personnel_number"))
        return None, {"error": "Database error while creating employee"}, 500

    logger.info("employee_created employee_id=%s", employee.id)
    return employee, None, 201


def update_employee(employee, data):
    """Apply a partial update to an existing employee record.

    Only fields present in *data* are modified; absent keys are left unchanged.

    Returns:
        (employee, None, 200)                  on success
        (None, {"error": "..."}, 400/500)      on failure
    """
    scalar_fields = [
        "personnel_number",
        "name",
        "city",
        "street",
        "postal_code",
        "department",
        "shift_model",
        "current_shift",
        "salary_group",
        "qualifications",
        "favorite_machine",
    ]
    try:
        for field in scalar_fields:
            if field in data:
                setattr(employee, field, data[field])
        if "birth_date" in data:
            employee.birth_date = _parse_birth_date(data["birth_date"])
        if "team" in data:
            employee.team = int(data["team"]) if data["team"] else None
        if "favorite_machine" in data:
            employee.favorite_machine_id = _resolve_machine_id(data["favorite_machine"])
    except ValueError:
        return None, {"error": "Invalid birth_date or team"}, 400

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("employee_update_failed employee_id=%s", employee.id)
        return None, {"error": "Database error while updating employee"}, 500

    return employee, None, 200


def delete_employee(employee):
    """Delete an employee and cascade to related documents.

    Returns:
        (None, None, 204)                      on success
        (None, {"error": "..."}, 500)          on failure
    """
    try:
        db.session.delete(employee)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("employee_delete_failed employee_id=%s", employee.id)
        return None, {"error": "Database error while deleting employee"}, 500

    logger.info("employee_deleted employee_id=%s", employee.id)
    return None, None, 204


# ---------------------------------------------------------------------------
# Document management
# ---------------------------------------------------------------------------


def upload_employee_document(employee, file):
    """Persist an uploaded file and create the EmployeeDocument record.

    The file is stored under UPLOAD_FOLDER/employees/<employee_id>/ with a
    UUID-prefixed filename to avoid collisions.

    Returns:
        (document, None, 201)                  on success
        (None, {"error": "..."}, 400/500)      on failure
    """
    if not file or not file.filename:
        return None, {"error": "document file is required"}, 400

    original = secure_filename(file.filename)
    stored = f"{uuid4().hex}_{original}"
    upload_dir = employee_upload_dir(employee.id)

    try:
        file.save(upload_dir / stored)
    except OSError:
        logger.exception("employee_document_save_failed employee_id=%s", employee.id)
        return None, {"error": "File could not be saved"}, 500

    document = EmployeeDocument(
        employee=employee,
        original_filename=original,
        stored_filename=stored,
        content_type=file.mimetype or "",
    )
    try:
        db.session.add(document)
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("employee_document_create_failed employee_id=%s", employee.id)
        return None, {"error": "Database error while saving document"}, 500

    logger.info(
        "employee_document_uploaded employee_id=%s document_id=%s",
        employee.id, document.id,
    )
    return document, None, 201


def get_employee_document(employee_id, document_id):
    """Return the EmployeeDocument scoped to the given employee, or None."""
    return EmployeeDocument.query.filter_by(
        id=document_id,
        employee_id=employee_id,
    ).first()
