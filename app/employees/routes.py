from datetime import date
from pathlib import Path
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models import Employee, EmployeeDocument, Role
from app.security import roles_required


employees_bp = Blueprint("employees", __name__)


def parse_birth_date(value):
    if not value:
        return None
    return date.fromisoformat(value)


def employee_upload_dir(employee_id):
    path = Path(current_app.config["UPLOAD_FOLDER"]) / "employees" / str(employee_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


@employees_bp.get("")
@roles_required(Role.MASTER_ADMIN)
def list_employees():
    employees = Employee.query.order_by(Employee.name.asc()).all()
    return jsonify([employee.to_dict() for employee in employees])


@employees_bp.post("")
@roles_required(Role.MASTER_ADMIN)
def create_employee():
    data = request.get_json(silent=True) or {}
    required = ["personnel_number", "name"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return jsonify({"error": f"Missing fields: {', '.join(missing)}"}), 400

    if Employee.query.filter_by(personnel_number=data["personnel_number"]).first():
        return jsonify({"error": "personnel_number already exists"}), 409

    try:
        employee = Employee(
            personnel_number=data["personnel_number"],
            name=data["name"],
            birth_date=parse_birth_date(data.get("birth_date")),
            city=data.get("city", ""),
            street=data.get("street", ""),
            postal_code=data.get("postal_code", ""),
            department=data.get("department", ""),
            shift_model=data.get("shift_model", ""),
            current_shift=data.get("current_shift", ""),
            team=int(data["team"]) if data.get("team") else None,
            salary_group=data.get("salary_group", ""),
            qualifications=data.get("qualifications", ""),
            favorite_machine=data.get("favorite_machine", ""),
        )
    except ValueError:
        return jsonify({"error": "Invalid birth_date or team"}), 400

    db.session.add(employee)
    db.session.commit()
    return jsonify(employee.to_dict()), 201


@employees_bp.put("/<int:employee_id>")
@roles_required(Role.MASTER_ADMIN)
def update_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    data = request.get_json(silent=True) or {}

    fields = [
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
    for field in fields:
        if field in data:
            setattr(employee, field, data[field])
    if "birth_date" in data:
        employee.birth_date = parse_birth_date(data["birth_date"])
    if "team" in data:
        employee.team = int(data["team"]) if data["team"] else None

    db.session.commit()
    return jsonify(employee.to_dict())


@employees_bp.delete("/<int:employee_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_employee(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    db.session.delete(employee)
    db.session.commit()
    return "", 204


@employees_bp.post("/<int:employee_id>/documents")
@roles_required(Role.MASTER_ADMIN)
def upload_document(employee_id):
    employee = Employee.query.get_or_404(employee_id)
    file = request.files.get("document")
    if not file or not file.filename:
        return jsonify({"error": "document file is required"}), 400

    original = secure_filename(file.filename)
    stored = f"{uuid4().hex}_{original}"
    upload_dir = employee_upload_dir(employee.id)
    file.save(upload_dir / stored)

    document = EmployeeDocument(
        employee=employee,
        original_filename=original,
        stored_filename=stored,
        content_type=file.mimetype or "",
    )
    db.session.add(document)
    db.session.commit()
    return jsonify(document.to_dict()), 201


@employees_bp.get("/<int:employee_id>/documents/<int:document_id>")
@roles_required(Role.MASTER_ADMIN)
def download_document(employee_id, document_id):
    document = EmployeeDocument.query.filter_by(
        id=document_id,
        employee_id=employee_id,
    ).first_or_404()
    upload_dir = employee_upload_dir(employee_id)
    return send_from_directory(
        upload_dir,
        document.stored_filename,
        as_attachment=True,
        download_name=document.original_filename,
    )
