"""SQLAlchemy domain models for this bounded area."""

import json

from app.domain_models.common import utc_now
from app.extensions import db

try:
    from pgvector.sqlalchemy import Vector
except ImportError:  # pragma: no cover - dependency is installed in supported envs
    Vector = None


def _knowledge_embedding_type():
    """Return a portable SQLAlchemy type for stored knowledge embeddings."""
    if Vector is None:
        return db.JSON
    return Vector()


class ChatMessage(db.Model):
    """Persisted AI chat exchange for history and context retrieval."""

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    response_type = db.Column(db.String(80), nullable=False, default="assistant")
    session_id = db.Column(db.String(120), nullable=False, default="")
    diagnostics_json = db.Column(db.Text, nullable=False, default="{}")
    source_count = db.Column(db.Integer, nullable=False, default=0)
    confidence_score = db.Column(db.Integer)
    confidence_level = db.Column(db.String(40), nullable=False, default="")
    audit_event_id = db.Column(db.Integer, db.ForeignKey("ai_audit_event.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    audit_event = db.relationship("AIAuditEvent", foreign_keys=[audit_event_id])

    __table_args__ = (
        db.Index("ix_chat_message_user_created", "user_id", "created_at"),
        db.Index("ix_chat_message_user_session_created", "user_id", "session_id", "created_at"),
        db.Index("ix_chat_message_created", "created_at"),
    )

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
            "session_id": self.session_id,
            "diagnostics": self.diagnostics(),
            "source_count": self.source_count,
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
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
    chat_message_id = db.Column(db.Integer, db.ForeignKey("chat_message.id"))
    audit_event_id = db.Column(db.Integer)
    prompt = db.Column(db.Text, nullable=False)
    response = db.Column(db.Text, nullable=False)
    response_type = db.Column(db.String(80), nullable=False, default="")
    rating = db.Column(db.String(40), nullable=False)
    comment = db.Column(db.Text, nullable=False, default="")
    sources_json = db.Column(db.Text, nullable=False, default="[]")
    source_count = db.Column(db.Integer, nullable=False, default=0)
    review_status = db.Column(db.String(40), nullable=False, default="open", index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship("User")
    chat_message = db.relationship("ChatMessage", foreign_keys=[chat_message_id])

    __table_args__ = (
        db.Index("ix_ai_feedback_user_created", "user_id", "created_at"),
        db.Index("ix_ai_feedback_rating_created", "rating", "created_at"),
    )

    def sources(self):
        """Return stored answer sources as a safe list."""
        try:
            data = json.loads(self.sources_json or "[]")
        except (TypeError, json.JSONDecodeError):
            return []
        return data if isinstance(data, list) else []

    def to_dict(self):
        """Return a JSON-serializable representation of the feedback."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "chat_message_id": self.chat_message_id,
            "audit_event_id": self.audit_event_id,
            "response_type": self.response_type,
            "rating": self.rating,
            "comment": self.comment,
            "source_count": self.source_count,
            "sources": self.sources(),
            "review_status": self.review_status,
            "created_at": self.created_at.isoformat(),
        }


class AssistantTrainingEntry(db.Model):
    """Admin-maintained assistant knowledge used as manual RAG training data."""

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(220), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    keywords = db.Column(db.Text, nullable=False, default="")
    category = db.Column(db.String(80), nullable=False, default="wartung")
    department = db.Column(db.String(120), nullable=False, default="")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    priority = db.Column(db.Integer, nullable=False, default=50)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.Index(
            "ix_assistant_training_active_department",
            "is_active",
            "department",
        ),
        db.Index(
            "ix_assistant_training_category_priority",
            "category",
            "priority",
        ),
    )

    def to_dict(self):
        """Return a JSON-serializable training entry."""
        return {
            "id": self.id,
            "title": self.title,
            "question": self.question,
            "answer": self.answer,
            "keywords": self.keywords,
            "category": self.category,
            "department": self.department,
            "is_active": self.is_active,
            "priority": self.priority,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AIPromptTemplate(db.Model):
    """Admin-managed prompt template grouped by AI workflow."""

    id = db.Column(db.Integer, primary_key=True)
    workflow_key = db.Column(db.String(80), nullable=False, unique=True, index=True)
    name = db.Column(db.String(160), nullable=False)
    purpose = db.Column(db.Text, nullable=False, default="")
    response_mode = db.Column(db.String(20), nullable=False, default="text")
    variables_json = db.Column(db.Text, nullable=False, default="[]")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    versions = db.relationship(
        "AIPromptVersion",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="AIPromptVersion.version.desc()",
    )

    def variables(self):
        """Return prompt variable definitions as a safe list."""
        return _loads_json_list(self.variables_json)

    def active_version(self):
        """Return the active version for this template, if present."""
        return next((version for version in self.versions if version.status == "active"), None)

    def to_dict(self, include_versions=False):
        """Return a JSON-serializable prompt template."""
        active = self.active_version()
        payload = {
            "id": self.id,
            "workflow_key": self.workflow_key,
            "name": self.name,
            "purpose": self.purpose,
            "response_mode": self.response_mode,
            "variables": self.variables(),
            "is_active": self.is_active,
            "active_version_id": active.id if active else None,
            "active_version_number": active.version if active else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }
        if include_versions:
            payload["versions"] = [
                version.to_dict(include_prompt=True) for version in self.versions
            ]
        return payload


class AIPromptVersion(db.Model):
    """Versioned prompt text for one admin-managed prompt template."""

    id = db.Column(db.Integer, primary_key=True)
    template_id = db.Column(db.Integer, db.ForeignKey("ai_prompt_template.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="draft", index=True)
    system_prompt = db.Column(db.Text, nullable=False, default="")
    user_prompt_template = db.Column(db.Text, nullable=False, default="")
    json_schema = db.Column(db.Text, nullable=False, default="")
    rules_json = db.Column(db.Text, nullable=False, default="[]")
    change_note = db.Column(db.Text, nullable=False, default="")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    activated_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    template = db.relationship("AIPromptTemplate", back_populates="versions")
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint(
            "template_id",
            "version",
            name="uq_ai_prompt_version_template_version",
        ),
        db.Index("ix_ai_prompt_version_template_status", "template_id", "status"),
    )

    def rules(self):
        """Return additional prompt rules as a safe list."""
        return _loads_json_list(self.rules_json)

    def to_dict(self, include_prompt=False):
        """Return a JSON-serializable prompt version."""
        payload = {
            "id": self.id,
            "template_id": self.template_id,
            "version": self.version,
            "status": self.status,
            "change_note": self.change_note,
            "created_by": self.creator.username if self.creator else None,
            "activated_at": self.activated_at.isoformat() if self.activated_at else None,
            "created_at": self.created_at.isoformat(),
        }
        if include_prompt:
            payload.update(
                {
                    "system_prompt": self.system_prompt,
                    "user_prompt_template": self.user_prompt_template,
                    "json_schema": self.json_schema,
                    "rules": self.rules(),
                }
            )
        return payload


class AIFAQEntry(db.Model):
    """Admin-approved FAQ answer that can become a searchable AI knowledge source."""

    __tablename__ = "ai_faq_entry"

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="wartung")
    keywords = db.Column(db.Text, nullable=False, default="")
    machine = db.Column(db.String(160), nullable=False, default="")
    department = db.Column(db.String(120), nullable=False, default="")
    status = db.Column(db.String(40), nullable=False, default="draft", index=True)
    source = db.Column(db.String(40), nullable=False, default="manual")
    source_ref_id = db.Column(db.Integer)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approved_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])
    approver = db.relationship("User", foreign_keys=[approved_by])

    __table_args__ = (
        db.Index("ix_ai_faq_entry_status_updated", "status", "updated_at"),
        db.Index("ix_ai_faq_entry_department_status", "department", "status"),
        db.Index("ix_ai_faq_entry_category_status", "category", "status"),
    )

    def to_dict(self):
        """Return a JSON-serializable FAQ entry."""
        return {
            "id": self.id,
            "question": self.question,
            "answer": self.answer,
            "category": self.category,
            "keywords": self.keywords,
            "machine": self.machine,
            "department": self.department,
            "status": self.status,
            "source": self.source,
            "source_ref_id": self.source_ref_id,
            "created_by": self.creator.username if self.creator else None,
            "approved_by": self.approver.username if self.approver else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class AIResponseSnippet(db.Model):
    """Reusable admin-managed response snippet for common AI answer states."""

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), nullable=False, unique=True, index=True)
    title = db.Column(db.String(160), nullable=False)
    body = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(80), nullable=False, default="fallback")
    is_active = db.Column(db.Boolean, nullable=False, default=True, index=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])

    def to_dict(self):
        """Return a JSON-serializable response snippet."""
        return {
            "id": self.id,
            "key": self.key,
            "title": self.title,
            "body": self.body,
            "category": self.category,
            "is_active": self.is_active,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
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
    confidence_score = db.Column(db.Integer)
    confidence_level = db.Column(db.String(40), nullable=False, default="")
    retrieval_explainability_json = db.Column(db.Text, nullable=False, default="{}")
    error_category = db.Column(db.String(120), nullable=False, default="")
    prompt_template_key = db.Column(db.String(80), nullable=False, default="")
    prompt_version_id = db.Column(db.Integer, db.ForeignKey("ai_prompt_version.id"))
    prompt_version_number = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    user = db.relationship("User")
    prompt_version = db.relationship("AIPromptVersion", foreign_keys=[prompt_version_id])

    __table_args__ = (
        db.Index("ix_ai_audit_event_created", "created_at"),
        db.Index("ix_ai_audit_event_workflow_created", "workflow", "created_at"),
        db.Index("ix_ai_audit_event_status_created", "status", "created_at"),
    )

    def retrieval_explainability(self):
        """Return stored retrieval explainability as safe metadata."""
        from app.services.retrieval_explainability_service import explainability_from_json

        return explainability_from_json(self.retrieval_explainability_json)

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
            "confidence_score": self.confidence_score,
            "confidence_level": self.confidence_level,
            "retrieval_explainability": self.retrieval_explainability(),
            "error_category": self.error_category,
            "prompt_template_key": self.prompt_template_key,
            "prompt_version_id": self.prompt_version_id,
            "prompt_version_number": self.prompt_version_number,
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
    quality_status = db.Column(db.String(40), nullable=False, default="draft")
    last_confirmed_at = db.Column(db.DateTime)
    confirmation_count = db.Column(db.Integer, nullable=False, default=0)
    aging_checked_at = db.Column(db.DateTime)
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

    __table_args__ = (
        db.Index("ix_knowledge_document_source_status", "source_type", "status"),
        db.Index("ix_knowledge_document_department_status", "department", "status"),
        db.Index(
            "ix_knowledge_document_quality_status",
            "quality_status",
            "updated_at",
        ),
        db.Index("ix_knowledge_document_updated", "updated_at"),
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
            "quality_status": self.quality_status,
            "last_confirmed_at": (
                self.last_confirmed_at.isoformat() if self.last_confirmed_at else None
            ),
            "confirmation_count": self.confirmation_count,
            "aging_checked_at": (
                self.aging_checked_at.isoformat() if self.aging_checked_at else None
            ),
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
    entities_json = db.Column(db.Text, nullable=False, default="{}")
    embedding = db.Column(_knowledge_embedding_type())
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    document = db.relationship("KnowledgeDocument", back_populates="chunks")

    __table_args__ = (
        db.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_knowledge_chunk_document_index",
        ),
    )

    def entities(self):
        """Return stored technical entities as a normalized dictionary."""
        from app.services.technical_entity_service import entities_from_json

        return entities_from_json(self.entities_json)

    def retrieval_metadata(self):
        """Return optional section-aware chunk metadata from the stored JSON payload."""
        import json

        try:
            payload = json.loads(self.entities_json or "{}")
        except (TypeError, json.JSONDecodeError):
            return {}
        metadata = payload.get("_chunk_metadata")
        return metadata if isinstance(metadata, dict) else {}

    def to_dict(self):
        """Return a JSON-serializable knowledge chunk."""
        payload = {
            "id": self.id,
            "document_id": self.document_id,
            "chunk_index": self.chunk_index,
            "text": self.text,
            "entities": self.entities(),
            "created_at": self.created_at.isoformat(),
        }
        metadata = self.retrieval_metadata()
        if metadata:
            payload["metadata"] = metadata
        return payload


class KnowledgeGap(db.Model):
    """Unanswered or low-confidence AI question requiring knowledge follow-up."""

    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    question_hash = db.Column(db.String(64), nullable=False, index=True)
    context_text = db.Column(db.Text, nullable=False, default="")
    machine = db.Column(db.String(160), nullable=False, default="")
    department = db.Column(db.String(120), nullable=False, default="")
    status = db.Column(db.String(40), nullable=False, default="open", index=True)
    occurrence_count = db.Column(db.Integer, nullable=False, default=1)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"))
    audit_event_id = db.Column(db.Integer, db.ForeignKey("ai_audit_event.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    last_seen_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    user = db.relationship("User", foreign_keys=[user_id])
    task = db.relationship("Task", foreign_keys=[task_id])
    audit_event = db.relationship("AIAuditEvent", foreign_keys=[audit_event_id])

    __table_args__ = (
        db.Index("ix_knowledge_gap_status_last_seen", "status", "last_seen_at"),
        db.Index("ix_knowledge_gap_hash_status", "question_hash", "status"),
        db.Index("ix_knowledge_gap_department_status", "department", "status"),
    )

    def to_dict(self):
        """Return a JSON-serializable knowledge-gap payload."""
        return {
            "id": self.id,
            "question": self.question,
            "context": self.context_text,
            "machine": self.machine,
            "department": self.department,
            "status": self.status,
            "occurrence_count": self.occurrence_count,
            "user_id": self.user_id,
            "created_by": self.user.username if self.user else None,
            "task_id": self.task_id,
            "audit_event_id": self.audit_event_id,
            "created_at": self.created_at.isoformat(),
            "last_seen_at": self.last_seen_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


class RetrievalEvaluationRun(db.Model):
    """Persisted aggregate metrics for one golden retrieval evaluation run."""

    id = db.Column(db.Integer, primary_key=True)
    query_count = db.Column(db.Integer, nullable=False, default=0)
    recall_at_k = db.Column(db.Float, nullable=False, default=0.0)
    mrr = db.Column(db.Float, nullable=False, default=0.0)
    ndcg_at_k = db.Column(db.Float, nullable=False, default=0.0)
    keyword_query_count = db.Column(db.Integer, nullable=False, default=0)
    keyword_hit_rate = db.Column(db.Float, nullable=False, default=0.0)
    permission_leak_count = db.Column(db.Integer, nullable=False, default=0)
    forbidden_source_hit_count = db.Column(db.Integer, nullable=False, default=0)
    no_result_count = db.Column(db.Integer, nullable=False, default=0)
    no_result_rate = db.Column(db.Float, nullable=False, default=0.0)
    expected_no_result_count = db.Column(db.Integer, nullable=False, default=0)
    expected_no_result_success_count = db.Column(db.Integer, nullable=False, default=0)
    expected_no_result_success_rate = db.Column(db.Float, nullable=False, default=0.0)
    unexpected_no_result_count = db.Column(db.Integer, nullable=False, default=0)
    unexpected_no_result_rate = db.Column(db.Float, nullable=False, default=0.0)
    min_source_count_fail_count = db.Column(db.Integer, nullable=False, default=0)
    min_source_count_pass_rate = db.Column(db.Float, nullable=False, default=0.0)
    query_type_expected_count = db.Column(db.Integer, nullable=False, default=0)
    query_type_match_count = db.Column(db.Integer, nullable=False, default=0)
    query_type_accuracy = db.Column(db.Float, nullable=False, default=0.0)
    source_metadata_count = db.Column(db.Integer, nullable=False, default=0)
    source_id_coverage_rate = db.Column(db.Float, nullable=False, default=0.0)
    source_type_coverage_rate = db.Column(db.Float, nullable=False, default=0.0)
    source_pair_coverage_rate = db.Column(db.Float, nullable=False, default=0.0)
    metadata_pair_coverage_rate = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    __table_args__ = (db.Index("ix_retrieval_evaluation_run_created", "created_at"),)

    def to_dict(self):
        """Return a prompt-safe evaluation run payload."""
        return {
            "id": self.id,
            "query_count": self.query_count,
            "recall_at_k": round(float(self.recall_at_k or 0.0), 4),
            "mrr": round(float(self.mrr or 0.0), 4),
            "ndcg_at_k": round(float(self.ndcg_at_k or 0.0), 4),
            "keyword_query_count": int(self.keyword_query_count or 0),
            "keyword_hit_rate": round(float(self.keyword_hit_rate or 0.0), 4),
            "permission_leak_count": int(self.permission_leak_count or 0),
            "forbidden_source_hit_count": int(self.forbidden_source_hit_count or 0),
            "no_result_count": int(self.no_result_count or 0),
            "no_result_rate": round(float(self.no_result_rate or 0.0), 4),
            "expected_no_result_count": int(self.expected_no_result_count or 0),
            "expected_no_result_success_count": int(self.expected_no_result_success_count or 0),
            "expected_no_result_success_rate": round(
                float(self.expected_no_result_success_rate or 0.0),
                4,
            ),
            "unexpected_no_result_count": int(self.unexpected_no_result_count or 0),
            "unexpected_no_result_rate": round(
                float(self.unexpected_no_result_rate or 0.0),
                4,
            ),
            "min_source_count_fail_count": int(self.min_source_count_fail_count or 0),
            "min_source_count_pass_rate": round(
                float(self.min_source_count_pass_rate or 0.0),
                4,
            ),
            "query_type_expected_count": int(self.query_type_expected_count or 0),
            "query_type_match_count": int(self.query_type_match_count or 0),
            "query_type_accuracy": round(float(self.query_type_accuracy or 0.0), 4),
            "source_metadata_count": int(self.source_metadata_count or 0),
            "source_id_coverage_rate": round(float(self.source_id_coverage_rate or 0.0), 4),
            "source_type_coverage_rate": round(
                float(self.source_type_coverage_rate or 0.0),
                4,
            ),
            "source_pair_coverage_rate": round(
                float(self.source_pair_coverage_rate or 0.0),
                4,
            ),
            "metadata_pair_coverage_rate": round(
                float(self.metadata_pair_coverage_rate or 0.0),
                4,
            ),
            "created_at": self.created_at.isoformat(),
        }


class BackgroundJob(db.Model):
    """Persisted background job for asynchronous maintenance workflows."""

    id = db.Column(db.Integer, primary_key=True)
    job_type = db.Column(db.String(120), nullable=False, index=True)
    status = db.Column(db.String(40), nullable=False, default="queued", index=True)
    payload_json = db.Column(db.Text, nullable=False, default="{}")
    result_json = db.Column(db.Text, nullable=False, default="{}")
    error_message = db.Column(db.Text, nullable=False, default="")
    attempts = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)
    locked_at = db.Column(db.DateTime)
    started_at = db.Column(db.DateTime)
    finished_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.Index(
            "ix_background_job_claim",
            "status",
            "job_type",
            "created_at",
            "id",
        ),
        db.Index("ix_background_job_locked_at", "locked_at"),
    )

    def payload(self):
        """Return the stored job payload as a dictionary."""
        return _loads_json_dict(self.payload_json)

    def result(self):
        """Return the stored job result as a dictionary."""
        return _loads_json_dict(self.result_json)

    def to_dict(self):
        """Return a JSON-serializable background job."""
        return {
            "id": self.id,
            "job_type": self.job_type,
            "status": self.status,
            "payload": self.payload(),
            "result": self.result(),
            "error_message": self.error_message,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "locked_at": self.locked_at.isoformat() if self.locked_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


def _loads_json_dict(value):
    """Return a safe dictionary from stored JSON text."""
    try:
        data = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _loads_json_list(value):
    """Return a JSON-list text value as a safe Python list."""
    try:
        result = json.loads(value or "[]")
    except (TypeError, json.JSONDecodeError):
        return []
    return result if isinstance(result, list) else []
