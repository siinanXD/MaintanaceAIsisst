import logging

from app.core.logging import safe_identifier
from app.models import Role


def test_logging_creates_app_and_error_logs(app):
    """Verify structured log files are configured for the application."""
    app.logger.info("test_general_log_event")
    app.logger.error("test_error_log_event")

    log_dir = app.config.get("LOG_DIR", "logs")
    app_log = f"{log_dir}/app.log"
    error_log = f"{log_dir}/error.log"

    with open(app_log, encoding="utf-8") as file:
        app_log_text = file.read()
    with open(error_log, encoding="utf-8") as file:
        error_log_text = file.read()

    assert "INFO" in app_log_text
    assert "test_general_log_event" in app_log_text
    assert "ERROR" in app_log_text
    assert "test_error_log_event" in app_log_text
    assert "test_error_log_event" in error_log_text


def test_login_logging_does_not_store_password(
    client,
    caplog,
    make_user,
    auth_headers,
):
    """Verify authentication logging avoids raw credentials."""
    make_user(
        username="logging_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
        password="TopSecret123!",
    )

    with caplog.at_level(logging.WARNING):
        response = client.post(
            "/api/v1/auth/login",
            json={"login": "logging_user", "password": "WrongSecret!"},
        )

    assert response.status_code == 401
    assert "login_failed" in caplog.text
    assert "WrongSecret!" not in caplog.text
    assert "logging_user" not in caplog.text
    assert safe_identifier("logging_user") in caplog.text

    success_response = client.get(
        "/api/v1/auth/me",
        headers=auth_headers("logging_user", "TopSecret123!"),
    )
    assert success_response.status_code == 200


def test_request_logging_records_method_endpoint_status_and_duration(client, caplog):
    """Verify request logging records safe request metadata."""
    with caplog.at_level(logging.INFO):
        response = client.get("/login")

    assert response.status_code == 200
    assert "request method=GET endpoint=web.login_page status=200" in caplog.text
    assert "duration_ms=" in caplog.text
