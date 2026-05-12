"""SQLAlchemy domain models for this bounded area."""

import json

from app.domain_models.common import utc_now
from app.extensions import db


class ChatMessage(db.Model):
    """Persisted AI chat exchange for history and context retrieval."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)


class AIFeedback(db.Model):
    """Store user feedback for AI answers."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    rating = db.Column(db.String(40), nullable=False)
    comment = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship("User")

    def to_dict(self):
        """Return a JSON-serializable representation of the feedback."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat(),
        }


class AIAuditEvent(db.Model):
    """Metadata-only audit record for one AI workflow execution."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    workflow = db.Column(db.String(80), nullable=False, index=True)
    status = db.Column(db.String(80), nullable=False, default="unknown")
    provider = db.Column(db.String(80), nullable=False, default="")
    model = db.Column(db.String(120), nullable=False, default="")
    model_tier = db.Column(db.String(40), nullable=False, default="")
    temperature = db.Column(db.Float, nullable=False, default=0.0)
    latency_ms = db.Column(db.Integer, nullable=False, default=0)
    input_tokens = db.Column(db.Integer, nullable=False, default=0)
    output_tokens = db.Column(db.Integer, nullable=False, default=0)
    cached_tokens = db.Column(db.Integer, nullable=False, default=0)
    total_tokens = db.Column(db.Integer, nullable=False, default=0)
    estimated_cost_usd = db.Column(db.Float, nullable=False, default=0.0)
    fallback_used = db.Column(db.Boolean, nullable=False, default=False)
    requested_scopes = db.Column(db.Text, nullable=False, default="[]")
    allowed_scopes = db.Column(db.Text, nullable=False, default="[]")
    source_count = db.Column(db.Integer, nullable=False, default=0)
    error_category = db.Column(db.String(120), nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship("User")

    def to_dict(self):
        """Return a JSON-serializable audit event without prompts or answers."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "workflow": self.workflow,
            "status": self.status,
            "provider": self.provider,
            "model": self.model,
            "model_tier": self.model_tier,
            "temperature": self.temperature,
            "latency_ms": self.latency_ms,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cached_tokens": self.cached_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost_usd": self.estimated_cost_usd,
            "fallback_used": self.fallback_used,
            "requested_scopes": _loads_json_list(self.requested_scopes),
            "allowed_scopes": _loads_json_list(self.allowed_scopes),
            "source_count": self.source_count,
            "error_category": self.error_category,
            "created_at": self.created_at.isoformat(),
        }


def _loads_json_list(value):
    """Return a JSON-list text value as a safe Python list."""
    try:
        result = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return result if isinstance(result, list) else []
