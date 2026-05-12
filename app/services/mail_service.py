"""SMTP mail delivery service with dry-run support."""

import json
import logging
import smtplib
from datetime import UTC, datetime
from email.message import EmailMessage

from flask import current_app

from app.extensions import db
from app.models import NotificationDelivery

logger = logging.getLogger(__name__)

SUCCESS_STATUSES = {"sent", "dry_run"}


def mail_config_status():
    """Return redacted mail configuration status for diagnostics."""
    return {
        "enabled": bool(current_app.config.get("MAIL_ENABLED")),
        "dry_run": bool(current_app.config.get("MAIL_DRY_RUN")),
        "host_configured": bool(current_app.config.get("MAIL_HOST")),
        "port": int(current_app.config.get("MAIL_PORT", 587)),
        "username_configured": bool(current_app.config.get("MAIL_USERNAME")),
        "from_configured": bool(current_app.config.get("MAIL_FROM")),
        "use_tls": bool(current_app.config.get("MAIL_USE_TLS")),
    }


def send_email(
    *,
    recipient_email,
    subject,
    body,
    notification_type,
    dedupe_key,
    recipient_user=None,
    payload=None,
):
    """Send or record one notification email and persist the delivery result."""
    if was_delivered(recipient_email, dedupe_key):
        return None

    delivery = NotificationDelivery(
        notification_type=notification_type,
        recipient_user_id=getattr(recipient_user, "id", None),
        recipient_email=str(recipient_email or "").strip().lower(),
        channel="email",
        subject=str(subject or "")[:255],
        status="pending",
        dedupe_key=str(dedupe_key or "")[:255],
        payload_json=_json_dump(payload or {}),
    )
    db.session.add(delivery)
    db.session.flush()

    try:
        _validate_delivery(delivery, body)
        if current_app.config.get("MAIL_DRY_RUN"):
            delivery.status = "dry_run"
            delivery.sent_at = datetime.now(UTC)
            logger.info(
                "mail_dry_run notification_type=%s delivery_id=%s recipient=%s",
                notification_type,
                delivery.id,
                delivery.recipient_email,
            )
        elif not current_app.config.get("MAIL_ENABLED"):
            delivery.status = "disabled"
            delivery.error = "MAIL_ENABLED is false"
        else:
            _send_smtp(delivery.recipient_email, delivery.subject, body)
            delivery.status = "sent"
            delivery.sent_at = datetime.now(UTC)
    except (OSError, smtplib.SMTPException, ValueError) as exc:
        delivery.status = "failed"
        delivery.error = str(exc)[:1000]
        logger.warning(
            "mail_delivery_failed notification_type=%s delivery_id=%s error=%s",
            notification_type,
            delivery.id,
            exc,
        )
    db.session.commit()
    return delivery


def was_delivered(recipient_email, dedupe_key):
    """Return whether a dedupe key was already successfully delivered."""
    if not recipient_email or not dedupe_key:
        return False
    return (
        NotificationDelivery.query.filter(
            NotificationDelivery.recipient_email == str(recipient_email).strip().lower(),
            NotificationDelivery.dedupe_key == str(dedupe_key)[:255],
            NotificationDelivery.channel == "email",
            NotificationDelivery.status.in_(SUCCESS_STATUSES),
        ).first()
        is not None
    )


def _send_smtp(recipient_email, subject, body):
    """Send one plain-text message through the configured SMTP server."""
    host = str(current_app.config.get("MAIL_HOST") or "").strip()
    port = int(current_app.config.get("MAIL_PORT", 587))
    sender = str(current_app.config.get("MAIL_FROM") or "").strip()
    username = str(current_app.config.get("MAIL_USERNAME") or "").strip()
    password = str(current_app.config.get("MAIL_PASSWORD") or "")

    if not host:
        raise ValueError("MAIL_HOST is required when mail is enabled")
    if not sender:
        raise ValueError("MAIL_FROM is required when mail is enabled")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient_email
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(host, port, timeout=15) as smtp:
        if current_app.config.get("MAIL_USE_TLS"):
            smtp.starttls()
        if username:
            smtp.login(username, password)
        smtp.send_message(message)


def _validate_delivery(delivery, body):
    """Validate fields required for a delivery attempt."""
    if not delivery.recipient_email or "@" not in delivery.recipient_email:
        raise ValueError("recipient_email must be a valid email address")
    if not delivery.subject:
        raise ValueError("subject is required")
    if not body:
        raise ValueError("body is required")
    if not delivery.dedupe_key:
        raise ValueError("dedupe_key is required")


def _json_dump(value):
    """Serialize delivery metadata without leaking secret objects."""
    return json.dumps(value or {}, ensure_ascii=True, sort_keys=True, default=str)
