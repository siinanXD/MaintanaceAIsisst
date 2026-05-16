"""Tests for database schema diagnostics."""

from app.services.database_schema_service import database_schema_status


def test_database_schema_status_reports_ready_test_schema(app):
    """Verify the schema checker accepts the current model metadata."""
    with app.app_context():
        status = database_schema_status()

    assert status["ok"] is True
    assert status["missing_tables"] == []
    assert status["missing_columns"] == {}
    assert "db upgrade" in status["migration_command"]
