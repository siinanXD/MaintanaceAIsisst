from pathlib import Path

from flask import Flask
from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from app.auth.routes import auth_bp
from app.config import Config
from app.core.logging import configure_logging
from app.docs.openapi import configure_api_documentation
from app.departments.services import ensure_default_departments
from app.departments.routes import departments_bp
from app.documents.routes import documents_bp
from app.errors.routes import errors_bp
from app.employees.routes import employees_bp
from app.extensions import db, jwt, migrate
from app.health.routes import health_bp, public_health_bp
from app.inventory.routes import inventory_bp
from app.machines.routes import machines_bp
from app.tasks.routes import tasks_bp
from app.ai.routes import ai_bp
from app.admin.routes import admin_bp
from app.shiftplans.routes import shiftplans_bp
from app.search.routes import search_bp
from app.web.routes import web_bp
from app.handover.routes import handover_bp
from app.vacations.routes import vacations_bp
from app.permissions import ensure_all_user_default_permissions
from app.responses import error_response


def _run_lightweight_migrations():
    """Apply small SQLite-safe schema updates for existing installations."""
    inspector = inspect(db.engine)
    table_names = inspector.get_table_names()
    if "user" not in table_names:
        return

    if "dashboard_permission" not in table_names:
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                """
                CREATE TABLE dashboard_permission (
                    id INTEGER NOT NULL PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    dashboard VARCHAR(40) NOT NULL,
                    can_view BOOLEAN NOT NULL DEFAULT 0,
                    can_write BOOLEAN NOT NULL DEFAULT 0,
                    employee_access_level VARCHAR(40) NOT NULL DEFAULT 'none',
                    FOREIGN KEY(user_id) REFERENCES user (id),
                    CONSTRAINT uq_dashboard_permission_user_dashboard
                        UNIQUE (user_id, dashboard)
                )
                """
            )

    columns = {column["name"] for column in inspector.get_columns("user")}
    if "is_active" not in columns:
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE user ADD COLUMN is_active BOOLEAN NOT NULL DEFAULT 1"
            )
    if "employee_id" not in columns:
        with db.engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE user ADD COLUMN employee_id INTEGER"
            )

    with db.engine.begin() as connection:
        if "task" in table_names:
            task_columns = {column["name"] for column in inspector.get_columns("task")}
            task_migrations = {
                "current_worker_id": "INTEGER",
                "started_at": "DATETIME",
                "completed_by_id": "INTEGER",
                "completed_at": "DATETIME",
            }
            for column_name, column_type in task_migrations.items():
                if column_name not in task_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE task ADD COLUMN {column_name} {column_type}"
                    )

        if "employee" in table_names:
            employee_columns = {column["name"] for column in inspector.get_columns("employee")}
            employee_migrations = {
                "qualifications": "TEXT NOT NULL DEFAULT ''",
                "favorite_machine": "VARCHAR(160) NOT NULL DEFAULT ''",
                "favorite_machine_id": "INTEGER",
                "vacation_days_per_year": "INTEGER NOT NULL DEFAULT 30",
            }
            for column_name, column_type in employee_migrations.items():
                if column_name not in employee_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE employee ADD COLUMN {column_name} {column_type}"
                    )

        if "error_entry" in table_names:
            error_columns = {column["name"] for column in inspector.get_columns("error_entry")}
            if "machine_id" not in error_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE error_entry ADD COLUMN machine_id INTEGER"
                )

        if "generated_document" in table_names:
            doc_columns = {
                column["name"] for column in inspector.get_columns("generated_document")
            }
            if "machine_id" not in doc_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE generated_document ADD COLUMN machine_id INTEGER"
                )

        if "shift_plan" in table_names:
            sp_columns = {
                column["name"] for column in inspector.get_columns("shift_plan")
            }
            shift_plan_migrations = {
                "department": "VARCHAR(120) NOT NULL DEFAULT ''",
                "created_by": "INTEGER",
                "status": "VARCHAR(20) NOT NULL DEFAULT 'draft'",
                "published_at": "DATETIME",
            }
            for column_name, column_type in shift_plan_migrations.items():
                if column_name not in sp_columns:
                    connection.exec_driver_sql(
                        f"ALTER TABLE shift_plan ADD COLUMN {column_name} {column_type}"
                    )

        if "shift_plan_entry" in table_names:
            spe_columns = {
                column["name"] for column in inspector.get_columns("shift_plan_entry")
            }
            if "created_at" not in spe_columns:
                connection.exec_driver_sql(
                    "ALTER TABLE shift_plan_entry ADD COLUMN created_at DATETIME"
                )


def register_error_handlers(app):
    """Register JSON error handlers for API and app-level failures."""

    @app.errorhandler(HTTPException)
    def handle_http_exception(error):
        """Return a consistent JSON response for HTTP errors."""
        if error.code and error.code >= 500:
            app.logger.exception("HTTP server error", exc_info=error)
        else:
            app.logger.warning(
                "HTTP error status=%s description=%s",
                error.code,
                error.description or error.name,
            )
        return error_response(error.description or error.name, error.code)

    @app.errorhandler(SQLAlchemyError)
    def handle_database_exception(error):
        """Roll back failed transactions and hide database internals."""
        db.session.rollback()
        app.logger.exception("Database error", exc_info=error)
        return error_response("Database error", 500)

    @app.errorhandler(Exception)
    def handle_unexpected_exception(error):
        """Return a consistent JSON response for unexpected server errors."""
        app.logger.exception("Unhandled server error", exc_info=error)
        return error_response("Internal server error", 500)


def create_app(config_class=Config):
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    configure_logging(app)

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    Path("data").mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
    Path(app.config["DOCUMENTS_FOLDER"]).mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)

    # Auth & administration
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")

    # Core domain: tasks, errors, documents
    app.register_blueprint(departments_bp, url_prefix="/api/v1/departments")
    app.register_blueprint(tasks_bp, url_prefix="/api/v1/tasks")
    app.register_blueprint(errors_bp, url_prefix="/api/v1/errors")
    app.register_blueprint(documents_bp, url_prefix="/api/v1/documents")

    # Workforce & production
    app.register_blueprint(employees_bp, url_prefix="/api/v1/employees")
    app.register_blueprint(machines_bp, url_prefix="/api/v1/machines")
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")
    app.register_blueprint(shiftplans_bp, url_prefix="/api/v1/shiftplans")
    app.register_blueprint(handover_bp, url_prefix="/api/v1/handover")
    app.register_blueprint(vacations_bp, url_prefix="/api/v1/vacations")

    # Cross-cutting: AI, search, health, frontend
    app.register_blueprint(ai_bp, url_prefix="/api/v1/ai")
    app.register_blueprint(search_bp, url_prefix="/api/v1/search")
    app.register_blueprint(health_bp, url_prefix="/api/v1/health")
    app.register_blueprint(public_health_bp)
    app.register_blueprint(web_bp)
    configure_api_documentation(app)
    register_error_handlers(app)

    with app.app_context():
        db.create_all()
        _run_lightweight_migrations()
        ensure_default_departments()
        ensure_all_user_default_permissions()

    return app
