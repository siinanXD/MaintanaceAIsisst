"""Tests for database schema diagnostics."""

from app.extensions import db
from app.services.database_schema_service import (
    database_schema_status,
    ensure_local_development_schema,
)


def test_database_schema_status_reports_ready_test_schema(app):
    """Verify the schema checker accepts the current model metadata."""
    with app.app_context():
        status = database_schema_status()

    assert status["ok"] is True
    assert status["missing_tables"] == []
    assert status["missing_columns"] == {}
    assert "db upgrade" in status["migration_command"]


def test_local_development_schema_adds_missing_tracking_columns(app):
    """Verify local startup can repair additive columns in existing SQLite databases."""
    with app.app_context():
        db.session.execute(db.text("ALTER TABLE task DROP COLUMN planned_minutes"))
        db.session.commit()

        ensure_local_development_schema()
        status = database_schema_status()

    assert status["missing_columns"].get("task") is None


def test_local_development_schema_adds_missing_ai_feedback_columns(app):
    """Verify local startup can repair additive AI feedback columns."""
    with app.app_context():
        db.session.execute(db.text("ALTER TABLE ai_feedback DROP COLUMN sources_json"))
        db.session.commit()

        ensure_local_development_schema()
        status = database_schema_status()

    assert status["missing_columns"].get("ai_feedback") is None


def test_local_development_schema_adds_missing_retrieval_evaluation_columns(app):
    """Verify local startup repairs additive retrieval evaluation metric columns."""
    with app.app_context():
        db.session.execute(
            db.text(
                "ALTER TABLE retrieval_evaluation_run "
                "DROP COLUMN query_type_accuracy"
            )
        )
        db.session.commit()

        ensure_local_development_schema()
        status = database_schema_status()

    assert status["missing_columns"].get("retrieval_evaluation_run") is None
