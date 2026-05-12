"""Compatibility exports for SQLAlchemy domain models."""

from app.domain_models.ai import AIAuditEvent, AIFeedback, ChatMessage
from app.domain_models.common import Priority, Role, TaskStatus, utc_now
from app.domain_models.documents import (
    DocumentApprovalEvent,
    DocumentVersion,
    EmployeeDocument,
    GeneratedDocument,
    MachineManual,
    MachineManualVersion,
)
from app.domain_models.errors import ErrorEntry
from app.domain_models.machines import InventoryMaterial, Machine, MaintenancePlan
from app.domain_models.notifications import Notification, NotificationDelivery
from app.domain_models.organization import AuditLogEntry, DashboardPermission, Department
from app.domain_models.tasks import Task
from app.domain_models.users import TokenBlocklist, User
from app.domain_models.workforce import (
    Employee,
    EmployeeMachineQualification,
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
    "DocumentApprovalEvent",
    "DocumentVersion",
    "Employee",
    "EmployeeDocument",
    "EmployeeMachineQualification",
    "ErrorEntry",
    "GeneratedDocument",
    "InventoryMaterial",
    "Machine",
    "MachineManual",
    "MachineManualVersion",
    "MaintenancePlan",
    "NotificationDelivery",
    "Notification",
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
