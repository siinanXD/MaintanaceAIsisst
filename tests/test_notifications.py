"""Tests for SMTP notifications and scheduled reminder jobs."""

from datetime import UTC, date, datetime, timedelta

from app.extensions import db
from app.models import AIAuditEvent, NotificationDelivery, Priority, Role, Task, TaskStatus, User
from app.services.mail_service import send_email
from app.services.notification_service import (
    send_ai_alerts,
    send_daily_briefings,
    send_overdue_reminders,
    send_task_alerts,
)


def test_mail_dry_run_creates_delivery_without_smtp(app, make_user, monkeypatch):
    """Verify dry-run records a delivery and never opens an SMTP connection."""
    user = make_user(username="mail_dry_run")

    def fail_smtp(*_args, **_kwargs):
        """Fail if SMTP is unexpectedly used."""
        raise AssertionError("SMTP must not be used in dry-run mode")

    monkeypatch.setattr("smtplib.SMTP", fail_smtp)

    with app.app_context():
        app.config["MAIL_DRY_RUN"] = True
        recipient = db.session.get(User, user["id"])
        delivery = send_email(
            recipient_email=recipient.email,
            subject="Dry run",
            body="Body",
            notification_type="test",
            dedupe_key="dry-run-key",
            recipient_user=recipient,
        )
        delivery_status = delivery.status
        delivery_error = delivery.error

    assert delivery_status == "dry_run"
    assert delivery_error == ""


def test_mail_smtp_failure_is_recorded(app, make_user, monkeypatch):
    """Verify SMTP failures become failed delivery records."""
    user = make_user(username="mail_failure")

    class FailingSMTP:
        """SMTP test double that fails while sending."""

        def __init__(self, *_args, **_kwargs):
            """Initialize the failing SMTP double."""

        def __enter__(self):
            """Return the SMTP context object."""
            return self

        def __exit__(self, *_args):
            """Exit the SMTP context."""
            return False

        def starttls(self):
            """Pretend TLS started."""

        def send_message(self, _message):
            """Raise a deterministic send failure."""
            raise OSError("smtp offline")

    monkeypatch.setattr("smtplib.SMTP", FailingSMTP)

    with app.app_context():
        app.config.update(
            MAIL_DRY_RUN=False,
            MAIL_ENABLED=True,
            MAIL_HOST="smtp.example.test",
            MAIL_FROM="noreply@example.test",
            MAIL_USERNAME="",
            MAIL_PASSWORD="",
        )
        recipient = db.session.get(User, user["id"])
        delivery = send_email(
            recipient_email=recipient.email,
            subject="Failure",
            body="Body",
            notification_type="test",
            dedupe_key="smtp-failure-key",
            recipient_user=recipient,
        )
        delivery_status = delivery.status
        delivery_error = delivery.error

    assert delivery_status == "failed"
    assert "smtp offline" in delivery_error


def test_urgent_task_alerts_are_deduped(app, make_user, make_task):
    """Verify urgent open tasks create one daily delivery per recipient."""
    admin = make_user(
        username="urgent_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    creator = make_user(username="urgent_creator")
    task_id = make_task(
        "CNC steht",
        creator_username=creator["username"],
        priority=Priority.URGENT,
        status=TaskStatus.OPEN,
        due_date_value=date.today(),
    )

    with app.app_context():
        task = db.session.get(Task, task_id)
        task.current_worker_id = creator["id"]
        db.session.commit()
        first = send_task_alerts()
        second = send_task_alerts()
        deliveries = NotificationDelivery.query.filter_by(notification_type="task_urgent").all()

    assert first["deliveries_created"] == 2
    assert second["deliveries_created"] == 0
    assert {delivery.recipient_email for delivery in deliveries} == {
        admin["email"],
        creator["email"],
    }


def test_overdue_reminders_ignore_done_and_cancelled_tasks(app, make_user, make_task):
    """Verify only unfinished overdue tasks generate reminder deliveries."""
    user = make_user(username="overdue_user")
    make_task(
        "Done old",
        creator_username=user["username"],
        status=TaskStatus.DONE,
        due_date_value=date.today() - timedelta(days=2),
    )
    make_task(
        "Cancelled old",
        creator_username=user["username"],
        status=TaskStatus.CANCELLED,
        due_date_value=date.today() - timedelta(days=2),
    )
    make_task(
        "Open old",
        creator_username=user["username"],
        status=TaskStatus.OPEN,
        due_date_value=date.today() - timedelta(days=1),
    )

    with app.app_context():
        summary = send_overdue_reminders()
        deliveries = NotificationDelivery.query.filter_by(notification_type="task_overdue").all()

    assert summary["scanned"] == 1
    assert len(deliveries) == 1
    assert deliveries[0].recipient_email == user["email"]


def test_ai_alerts_only_send_for_error_categories(app, make_user):
    """Verify AI error events create an aggregated admin alert."""
    admin = make_user(
        username="ai_alert_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_alert_user")
    now = datetime.now(UTC)

    with app.app_context():
        db.session.add_all(
            [
                AIAuditEvent(
                    user_id=user["id"],
                    workflow="chat",
                    status="error",
                    provider="openai",
                    model="gpt-test",
                    fallback_used=False,
                    error_category="rate_limit",
                    created_at=now,
                ),
                AIAuditEvent(
                    user_id=user["id"],
                    workflow="chat",
                    status="success",
                    provider="openai",
                    model="gpt-test",
                    fallback_used=False,
                    error_category="",
                    created_at=now,
                ),
            ]
        )
        db.session.commit()
        summary = send_ai_alerts(now=now)
        delivery = NotificationDelivery.query.filter_by(notification_type="ai_alert").one()

    assert summary["deliveries_created"] == 1
    assert delivery.recipient_email == admin["email"]
    assert delivery.subject == "Maintenance AI Warnung: 1 Fehler"
    assert "sk-" not in delivery.payload_json


def test_daily_briefing_sends_once_per_active_user(app, make_user, make_task):
    """Verify daily briefings use existing briefing logic and dedupe per user/date."""
    user = make_user(username="briefing_user")
    inactive = make_user(username="briefing_inactive", is_active=False)
    make_task(
        "Heute kritisch",
        creator_username=user["username"],
        priority=Priority.URGENT,
        status=TaskStatus.OPEN,
        due_date_value=date.today(),
    )

    with app.app_context():
        first = send_daily_briefings(today=date.today())
        second = send_daily_briefings(today=date.today())
        deliveries = NotificationDelivery.query.filter_by(notification_type="daily_briefing").all()

    assert first["deliveries_created"] == 1
    assert second["deliveries_created"] == 0
    assert [delivery.recipient_email for delivery in deliveries] == [user["email"]]
    assert inactive["email"] not in {delivery.recipient_email for delivery in deliveries}


def test_notification_admin_api_and_cli(client, make_user, auth_headers):
    """Verify admin delivery listing, test email endpoint, and CLI registration."""
    admin = make_user(
        username="notification_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="notification_user")
    headers = auth_headers(admin["username"])

    forbidden_response = client.get(
        "/api/v1/admin/notifications/deliveries",
        headers=auth_headers(user["username"]),
    )
    test_response = client.post(
        "/api/v1/admin/notifications/test-email",
        headers=headers,
        json={"recipient_email": "ops@example.test"},
    )
    list_response = client.get(
        "/api/v1/admin/notifications/deliveries?type=test_email",
        headers=headers,
    )
    cli_result = client.application.test_cli_runner().invoke(
        args=["notifications", "send-task-alerts"]
    )

    assert forbidden_response.status_code == 403
    assert test_response.status_code == 201
    assert test_response.get_json()["mail"]["dry_run"] is True
    assert list_response.status_code == 200
    assert list_response.get_json()["data"][0]["recipient_email"] == "ops@example.test"
    assert cli_result.exit_code == 0
