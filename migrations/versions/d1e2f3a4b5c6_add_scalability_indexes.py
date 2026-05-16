"""Add scalability indexes for multi-site operations.

Revision ID: d1e2f3a4b5c6
Revises: c0d1e2f3a4b5
Create Date: 2026-05-16 00:00:00.000000

"""

from alembic import op
from sqlalchemy import inspect

revision = "d1e2f3a4b5c6"
down_revision = "c0d1e2f3a4b5"
branch_labels = None
depends_on = None


INDEXES = (
    ("task", "ix_task_department_status_due", ("department_id", "status", "due_date")),
    ("task", "ix_task_status_due_id", ("status", "due_date", "id")),
    ("task", "ix_task_created_at", ("created_at",)),
    ("task", "ix_task_updated_at", ("updated_at",)),
    ("error_entry", "ix_error_entry_department_code", ("department_id", "error_code")),
    ("error_entry", "ix_error_entry_department_created", ("department_id", "created_at")),
    ("error_entry", "ix_error_entry_machine_id", ("machine_id",)),
    ("generated_document", "ix_generated_document_task_id", ("task_id",)),
    (
        "generated_document",
        "ix_generated_document_department_created",
        ("department", "created_at"),
    ),
    (
        "generated_document",
        "ix_generated_document_machine_created",
        ("machine_id", "created_at"),
    ),
    (
        "generated_document",
        "ix_generated_document_status_created",
        ("status", "created_at"),
    ),
    ("generated_document", "ix_generated_document_created_at", ("created_at",)),
    (
        "document_version",
        "ix_document_version_document_created",
        ("document_id", "created_at"),
    ),
    (
        "machine_manual",
        "ix_machine_manual_department_created",
        ("department", "created_at"),
    ),
    (
        "machine_manual",
        "ix_machine_manual_machine_created",
        ("machine_id", "created_at"),
    ),
    ("machine_manual", "ix_machine_manual_created_at", ("created_at",)),
    (
        "machine_manual_version",
        "ix_machine_manual_version_manual_created",
        ("manual_id", "created_at"),
    ),
    ("inventory_material", "ix_inventory_material_machine_id", ("machine_id",)),
    ("inventory_material", "ix_inventory_material_name", ("name",)),
    (
        "maintenance_plan",
        "ix_maintenance_plan_department_active_due",
        ("department_id", "is_active", "next_due_date"),
    ),
    ("maintenance_plan", "ix_maintenance_plan_machine_due", ("machine_id", "next_due_date")),
    ("employee", "ix_employee_department_name", ("department", "name")),
    ("employee", "ix_employee_favorite_machine", ("favorite_machine_id",)),
    (
        "employee_machine_qualification",
        "ix_employee_machine_qualification_machine",
        ("machine_id",),
    ),
    (
        "employee_machine_qualification",
        "ix_employee_machine_qualification_valid_until",
        ("valid_until",),
    ),
    ("shift_plan", "ix_shift_plan_department_start", ("department", "start_date")),
    ("shift_plan", "ix_shift_plan_status_start", ("status", "start_date")),
    ("shift_plan_entry", "ix_shift_plan_entry_plan_date", ("plan_id", "work_date")),
    (
        "shift_plan_entry",
        "ix_shift_plan_entry_employee_date",
        ("employee_id", "work_date"),
    ),
    (
        "shift_plan_entry",
        "ix_shift_plan_entry_machine_date",
        ("machine_id", "work_date"),
    ),
    ("shift_handover", "ix_shift_handover_department_date", ("department", "shift_date")),
    ("shift_handover", "ix_shift_handover_status_date", ("status", "shift_date")),
    ("vacation_request", "ix_vacation_request_employee_status", ("employee_id", "status")),
    ("vacation_request", "ix_vacation_request_status_start", ("status", "start_date")),
    ("chat_message", "ix_chat_message_user_created", ("user_id", "created_at")),
    ("chat_message", "ix_chat_message_created", ("created_at",)),
    ("ai_audit_event", "ix_ai_audit_event_created", ("created_at",)),
    (
        "ai_audit_event",
        "ix_ai_audit_event_workflow_created",
        ("workflow", "created_at"),
    ),
    (
        "ai_audit_event",
        "ix_ai_audit_event_status_created",
        ("status", "created_at"),
    ),
    (
        "knowledge_document",
        "ix_knowledge_document_source_status",
        ("source_type", "status"),
    ),
    (
        "knowledge_document",
        "ix_knowledge_document_department_status",
        ("department", "status"),
    ),
    ("knowledge_document", "ix_knowledge_document_updated", ("updated_at",)),
    (
        "assistant_training_entry",
        "ix_assistant_training_active_department",
        ("is_active", "department"),
    ),
    (
        "assistant_training_entry",
        "ix_assistant_training_category_priority",
        ("category", "priority"),
    ),
    (
        "background_job",
        "ix_background_job_claim",
        ("status", "job_type", "created_at", "id"),
    ),
    ("background_job", "ix_background_job_locked_at", ("locked_at",)),
)


def _table_exists(table_name):
    """Return whether a table exists in the current migration connection."""
    return table_name in inspect(op.get_bind()).get_table_names()


def _index_names(table_name):
    """Return existing index names for a table."""
    if not _table_exists(table_name):
        return set()
    return {index["name"] for index in inspect(op.get_bind()).get_indexes(table_name)}


def _create_index_if_missing(table_name, index_name, columns):
    """Create one index when the table exists and the index is missing."""
    if _table_exists(table_name) and index_name not in _index_names(table_name):
        op.create_index(index_name, table_name, list(columns))


def _drop_index_if_exists(table_name, index_name):
    """Drop one index when it exists."""
    if _table_exists(table_name) and index_name in _index_names(table_name):
        op.drop_index(index_name, table_name=table_name)


def upgrade():
    """Create composite indexes used by high-volume filters and worker claims."""
    for table_name, index_name, columns in INDEXES:
        _create_index_if_missing(table_name, index_name, columns)


def downgrade():
    """Drop scalability indexes without touching application data."""
    for table_name, index_name, _columns in reversed(INDEXES):
        _drop_index_if_exists(table_name, index_name)
