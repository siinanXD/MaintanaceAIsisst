"""SQLAlchemy notification delivery models."""

import json

from app.domain_models.common import utc_now
from app.extensions import db


class NotificationDelivery(db.Model):
    """Record one attempted notification delivery for dedupe and auditing."""

    id = db.Column(db.Integer, primary_key=True)
    notification_type = db.Column(db.String(80), nullable=False, index=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    recipient_email = db.Column(db.String(255), nullable=False, index=True)
    channel = db.Column(db.String(40), nullable=False, default="email")
    subject = db.Column(db.String(255), nullable=False, default="")
    status = db.Column(db.String(40), nullable=False, default="pending", index=True)
    error = db.Column(db.Text, nullable=False, default="")
    dedupe_key = db.Column(db.String(255), nullable=False, index=True)
    payload_json = db.Column(db.Text, nullable=False, default="{}")
    sent_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    recipient = db.relationship("User", foreign_keys=[recipient_user_id])

    def to_dict(self):
        """Return a JSON-serializable delivery record without mail secrets."""
        return {
            "id": self.id,
            "notification_type": self.notification_type,
            "recipient_user_id": self.recipient_user_id,
            "recipient_email": self.recipient_email,
            "channel": self.channel,
            "subject": self.subject,
            "status": self.status,
            "error": self.error,
            "dedupe_key": self.dedupe_key,
            "payload": _loads_json_object(self.payload_json),
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "created_at": self.created_at.isoformat(),
        }


def _loads_json_object(value):
    """Return a JSON-object text value as a safe dictionary."""
    try:
        result = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return result if isinstance(result, dict) else {}


class Notification(db.Model):
    """User-facing in-app notification shown in the topbar and notification list."""

    id = db.Column(db.Integer, primary_key=True)
    recipient_user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    notification_type = db.Column(db.String(80), nullable=False, index=True)
    title = db.Column(db.String(180), nullable=False)
    body = db.Column(db.Text, nullable=False, default="")
    link_url = db.Column(db.String(500), nullable=False, default="")
    is_read = db.Column(db.Boolean, nullable=False, default=False, index=True)
    read_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False, index=True)

    recipient = db.relationship("User", foreign_keys=[recipient_user_id])

    def to_dict(self):
        """Return a JSON-serializable in-app notification."""
        return {
            "id": self.id,
            "recipient_user_id": self.recipient_user_id,
            "notification_type": self.notification_type,
            "title": self.title,
            "body": self.body,
            "link_url": self.link_url,
            "is_read": self.is_read,
            "read_at": self.read_at.isoformat() if self.read_at else None,
            "created_at": self.created_at.isoformat(),
        }
