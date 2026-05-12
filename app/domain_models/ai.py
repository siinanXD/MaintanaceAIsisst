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
    response_type = db.Column(db.String(80), nullable=False, default="assistant")
    diagnostics_json = db.Column(db.Text, nullable=False, default="{}")
    source_count = db.Column(db.Integer, nullable=False, default=0)
    audit_event_id = db.Column(db.Integer, db.ForeignKey("ai_audit_event.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    audit_event = db.relationship("AIAuditEvent", foreign_keys=[audit_event_id])

    def diagnostics(self):
        """Return stored diagnostics as a safe dictionary."""
        try:
            data = json.loads(self.diagnostics_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def to_dict(self, include_user=False):
        """Return a JSON-serializable chat history entry."""
        payload = {
            "id": self.id,
            "user_id": self.user_id,
            "message": self.message,
            "response": self.response,
            "response_type": self.response_type,
            "diagnostics": self.diagnostics(),
            "source_count": self.source_count,
            "audit_event_id": self.audit_event_id,
            "created_at": self.created_at.isoformat(),
        }
        if include_user:
            payload["user"] = (
                {
                    "id": self.user.id,
                    "username": self.user.username,
                    "email": self.user.email,
                }
                if self.user
                else None
            )
        return payload


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


class KnowledgeDocument(db.Model):
    """Searchable document registered in the local AI knowledge base."""

    id = db.Column(db.Integer, primary_key=True)
    source_type = db.Column(db.String(80), nullable=False, default="upload")
    source_id = db.Column(db.Integer)
    title = db.Column(db.String(220), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False, default="")
    relative_path = db.Column(db.String(500), nullable=False, default="")
    content_type = db.Column(db.String(120), nullable=False, default="")
    file_size = db.Column(db.Integer, nullable=False, default=0)
    department = db.Column(db.String(120), nullable=False, default="")
    status = db.Column(db.String(40), nullable=False, default="pending", index=True)
    is_public = db.Column(db.Boolean, nullable=False, default=True)
    chunk_count = db.Column(db.Integer, nullable=False, default=0)
    error_message = db.Column(db.Text, nullable=False, default="")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])
    chunks = db.relationship(
        "KnowledgeChunk",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="KnowledgeChunk.chunk_index.asc()",
    )

    def to_dict(self, include_chunks=False):
        """Return a JSON-serializable knowledge document."""
        payload = {
            "id": self.id,
            "source_type": self.source_type,
            "source_id": self.source_id,
            "title": self.title,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "department": self.department,
            "status": self.status,
            "is_public": self.is_public,
            "chunk_count": self.chunk_count,
            "error_message": self.error_message,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_chunks:
            payload["chunks"] = [chunk.to_dict() for chunk in self.chunks]
        return payload


class KnowledgeChunk(db.Model):
    """Token-searchable text chunk for a knowledge document."""

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("knowledge_document.id"),
        nullable=False,
        index=True,
    )
    chunk_index = db.Column(db.Integer, nullable=False)
    text = db.Column(db.Text, nullable=False)
    token_text = db.Column(db.Text, nullable=False, default="")
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    document = db.relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        db.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunk_document_index",
        ),
    )

    def to_dict(self):
        """Return a JSON-serializable knowledge chunk."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "created_at": self.created_at.isoformat(),
        }


def _loads_json_list(value):
    """Return a JSON-list text value as a safe Python list."""
    try:
        result = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return result if isinstance(result, list) else []
