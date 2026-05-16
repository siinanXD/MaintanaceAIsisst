"""SQLAlchemy domain models for this bounded area."""

from app.domain_models.common import utc_now
from app.extensions import db


class GeneratedDocument(db.Model):
    """Store metadata for generated maintenance documents."""

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.Integer, db.ForeignKey("task.id"), nullable=False)
    document_type = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(180), nullable=False)
    relative_path = db.Column(db.String(500), nullable=False)
    department = db.Column(db.String(120), nullable=False, default="")
    machine = db.Column(db.String(160), nullable=False, default="")
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    status = db.Column(db.String(40), nullable=False, default="draft")
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "document_version.id",
            name="fk_generated_document_current_version",
            use_alter=True,
        ),
    )
    summary = db.Column(db.Text, nullable=False, default="")
    summary_status = db.Column(db.String(40), nullable=False, default="not_started")
    quality_score = db.Column(db.Integer, nullable=False, default=0)
    quality_status = db.Column(db.String(40), nullable=False, default="not_checked")
    quality_checked_at = db.Column(db.DateTime)
    approved_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    approved_at = db.Column(db.DateTime)
    approval_comment = db.Column(db.Text, nullable=False, default="")
    rejected_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    rejected_at = db.Column(db.DateTime)
    rejection_comment = db.Column(db.Text, nullable=False, default="")

    task = db.relationship("Task")
    creator = db.relationship("User", foreign_keys=[created_by])
    machine_rel = db.relationship("Machine", foreign_keys=[machine_id])
    approver = db.relationship("User", foreign_keys=[approved_by])
    rejecter = db.relationship("User", foreign_keys=[rejected_by])
    versions = db.relationship(
        "DocumentVersion",
        back_populates="document",
        cascade="all, delete-orphan",
        foreign_keys="DocumentVersion.document_id",
        order_by="DocumentVersion.version_number.desc()",
    )
    approval_events = db.relationship(
        "DocumentApprovalEvent",
        back_populates="document",
        cascade="all, delete-orphan",
        order_by="DocumentApprovalEvent.created_at.desc()",
    )

    __table_args__ = (
        db.Index("ix_generated_document_task_id", "task_id"),
        db.Index(
            "ix_generated_document_department_created",
            "department",
            "created_at",
        ),
        db.Index("ix_generated_document_machine_created", "machine_id", "created_at"),
        db.Index("ix_generated_document_status_created", "status", "created_at"),
        db.Index("ix_generated_document_created_at", "created_at"),
    )

    def to_dict(self):
        """Return a JSON-serializable representation of the document metadata."""
        return {
            "id": self.id,
            "task_id": self.task_id,
            "document_type": self.document_type,
            "title": self.title,
            "relative_path": self.relative_path,
            "department": self.department,
            "machine": self.machine,
            "machine_id": self.machine_id,
            "machine_obj": self.machine_rel.to_dict() if self.machine_rel else None,
            "created_by": self.created_by,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "current_version_id": self.current_version_id,
            "version": self.current_version.version_number if self.current_version else None,
            "summary": self.summary,
            "summary_status": self.summary_status,
            "quality_score": self.quality_score,
            "quality_status": self.quality_status,
            "quality_checked_at": (
                self.quality_checked_at.isoformat() if self.quality_checked_at else None
            ),
            "approved_by": self.approver.username if self.approver else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "approval_comment": self.approval_comment,
            "rejected_by": self.rejecter.username if self.rejecter else None,
            "rejected_at": self.rejected_at.isoformat() if self.rejected_at else None,
            "rejection_comment": self.rejection_comment,
            "download_url": f"/api/v1/documents/{self.id}/download",
            "pdf_url": f"/api/v1/documents/{self.id}/download.pdf",
            "detail_url": f"/api/v1/documents/{self.id}",
        }


class DocumentVersion(db.Model):
    """Immutable file version for a generated maintenance document."""

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("generated_document.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    relative_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False, default="")
    content_type = db.Column(db.String(120), nullable=False, default="text/html")
    file_size = db.Column(db.Integer, nullable=False, default=0)
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    document = db.relationship(
        "GeneratedDocument",
        back_populates="versions",
        foreign_keys=[document_id],
    )
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_version_document_number",
        ),
        db.Index("ix_document_version_document_created", "document_id", "created_at"),
    )

    def to_dict(self):
        """Return a JSON-serializable document version."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "version_number": self.version_number,
            "relative_path": self.relative_path,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat(),
            "download_url": f"/api/v1/documents/{self.document_id}/download",
        }


GeneratedDocument.current_version = db.relationship(
    "DocumentVersion",
    foreign_keys=[GeneratedDocument.current_version_id],
    post_update=True,
)


class DocumentApprovalEvent(db.Model):
    """Audit trail for document review, approval, and rejection actions."""

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("generated_document.id"), nullable=False)
    action = db.Column(db.String(40), nullable=False)
    comment = db.Column(db.Text, nullable=False, default="")
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    document = db.relationship("GeneratedDocument", back_populates="approval_events")
    user = db.relationship("User")

    def to_dict(self):
        """Return a JSON-serializable approval event."""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "action": self.action,
            "comment": self.comment,
            "user": self.user.username if self.user else None,
            "created_at": self.created_at.isoformat(),
        }


class MachineManual(db.Model):
    """Uploaded machine manual metadata for analysis and future RAG usage."""

    id = db.Column(db.Integer, primary_key=True)
    machine_id = db.Column(db.Integer, db.ForeignKey("machine.id"), nullable=True)
    department = db.Column(db.String(120), nullable=False, default="")
    title = db.Column(db.String(180), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    relative_path = db.Column(db.String(500), nullable=False)
    content_type = db.Column(db.String(120), nullable=False, default="")
    file_size = db.Column(db.Integer, nullable=False, default=0)
    analysis = db.Column(db.Text, nullable=False, default="")
    analysis_status = db.Column(db.String(40), nullable=False, default="not_started")
    summary = db.Column(db.Text, nullable=False, default="")
    summary_status = db.Column(db.String(40), nullable=False, default="not_started")
    current_version_id = db.Column(
        db.Integer,
        db.ForeignKey(
            "machine_manual_version.id",
            name="fk_machine_manual_current_version",
            use_alter=True,
        ),
    )
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)
    updated_at = db.Column(db.DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    machine = db.relationship("Machine", foreign_keys=[machine_id])
    creator = db.relationship("User", foreign_keys=[created_by])
    versions = db.relationship(
        "MachineManualVersion",
        back_populates="manual",
        cascade="all, delete-orphan",
        foreign_keys="MachineManualVersion.manual_id",
        order_by="MachineManualVersion.version_number.desc()",
    )

    __table_args__ = (
        db.Index("ix_machine_manual_department_created", "department", "created_at"),
        db.Index("ix_machine_manual_machine_created", "machine_id", "created_at"),
        db.Index("ix_machine_manual_created_at", "created_at"),
    )

    def to_dict(self):
        """Return a JSON-serializable machine manual."""
        return {
            "id": self.id,
            "machine_id": self.machine_id,
            "machine": self.machine.to_dict() if self.machine else None,
            "department": self.department,
            "title": self.title,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "analysis": self.analysis,
            "analysis_status": self.analysis_status,
            "summary": self.summary,
            "summary_status": self.summary_status,
            "version": self.current_version.version_number if self.current_version else None,
            "created_by": self.creator.username if self.creator else None,
            "created_by_id": self.created_by,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "download_url": f"/api/v1/documents/manuals/{self.id}/download",
        }


class MachineManualVersion(db.Model):
    """Immutable file version for an uploaded machine manual."""

    id = db.Column(db.Integer, primary_key=True)
    manual_id = db.Column(db.Integer, db.ForeignKey("machine_manual.id"), nullable=False)
    version_number = db.Column(db.Integer, nullable=False)
    relative_path = db.Column(db.String(500), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120), nullable=False, default="")
    file_size = db.Column(db.Integer, nullable=False, default=0)
    extracted_text = db.Column(db.Text, nullable=False, default="")
    extraction_status = db.Column(db.String(40), nullable=False, default="not_started")
    created_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    manual = db.relationship(
        "MachineManual",
        back_populates="versions",
        foreign_keys=[manual_id],
    )
    creator = db.relationship("User", foreign_keys=[created_by])

    __table_args__ = (
        db.UniqueConstraint(
            "manual_id",
            "version_number",
            name="uq_machine_manual_version_manual_number",
        ),
        db.Index("ix_machine_manual_version_manual_created", "manual_id", "created_at"),
    )

    def to_dict(self):
        """Return a JSON-serializable manual version."""
        return {
            "id": self.id,
            "manual_id": self.manual_id,
            "version_number": self.version_number,
            "relative_path": self.relative_path,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "file_size": self.file_size,
            "extraction_status": self.extraction_status,
            "created_by": self.creator.username if self.creator else None,
            "created_at": self.created_at.isoformat(),
        }


MachineManual.current_version = db.relationship(
    "MachineManualVersion",
    foreign_keys=[MachineManual.current_version_id],
    post_update=True,
)


class EmployeeDocument(db.Model):
    """File attachment stored on disk and associated with an employee record."""

    id = db.Column(db.Integer, primary_key=True)
    employee_id = db.Column(db.Integer, db.ForeignKey("employee.id"), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    content_type = db.Column(db.String(120), nullable=False, default="")
    uploaded_at = db.Column(db.DateTime, default=utc_now, nullable=False)

    employee = db.relationship("Employee", back_populates="documents")

    def to_dict(self):
        """Return a JSON-serializable representation of the employee document metadata."""
        return {
            "id": self.id,
            "employee_id": self.employee_id,
            "original_filename": self.original_filename,
            "content_type": self.content_type,
            "uploaded_at": self.uploaded_at.isoformat(),
            "download_url": f"/api/employees/{self.employee_id}/documents/{self.id}",
        }
