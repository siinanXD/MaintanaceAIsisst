"""Compatibility exports for SQLAlchemy domain models."""

from app.domain_models.ai import AIAuditEvent, AIFeedback, ChatMessage
from app.domain_models.common import Priority, Role, TaskStatus, utc_now
from app.domain_models.documents import EmployeeDocument, GeneratedDocument
from app.domain_models.errors import ErrorEntry
from app.domain_models.machines import InventoryMaterial, Machine, MaintenancePlan
from app.domain_models.organization import AuditLogEntry, DashboardPermission, Department
from app.domain_models.tasks import Task
from app.domain_models.users import TokenBlocklist, User
from app.domain_models.workforce import (
    Employee,
    ShiftHandover,
    ShiftPlan,
    ShiftPlanChangeLog,
    ShiftPlanEntry,
    VacationRequest,
)

__all__ = [
    "AIAuditEvent",
    "AIFeedback",
    "AuditLogEntry",
    "ChatMessage",
    "DashboardPermission",
    "Department",
    "Employee",
    "EmployeeDocument",
    "ErrorEntry",
    "GeneratedDocument",
    "InventoryMaterial",
    "Machine",
    "MaintenancePlan",
    "Priority",
    "Role",
    "ShiftHandover",
    "ShiftPlan",
    "ShiftPlanChangeLog",
    "ShiftPlanEntry",
    "Task",
    "TaskStatus",
    "TokenBlocklist",
    "User",
    "VacationRequest",
    "utc_now",
]
