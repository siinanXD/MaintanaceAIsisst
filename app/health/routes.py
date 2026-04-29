from flask import Blueprint, current_app, jsonify
from flask_jwt_extended import jwt_required
from sqlalchemy import inspect, text

from app.extensions import db
from app.models import Employee, EmployeeDocument, ErrorEntry, Task


health_bp = Blueprint("health", __name__)


@health_bp.get("/database")
@jwt_required()
def database_health():
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    with db.engine.connect() as connection:
        database_rows = connection.execute(text("PRAGMA database_list")).mappings().all()

    return jsonify(
        {
            "database_uri": current_app.config["SQLALCHEMY_DATABASE_URI"],
            "sqlite_files": [dict(row) for row in database_rows],
            "tables": table_names,
            "counts": {
                "tasks": Task.query.count(),
                "errors": ErrorEntry.query.count(),
                "employees": Employee.query.count(),
                "employee_documents": EmployeeDocument.query.count(),
            },
        }
    )
