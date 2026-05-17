"""Compatibility exports for SQLAlchemy domain models."""

from app.domain_models.ai import (
    AIAuditEvent,
    AIFeedback,
    AssistantTrainingEntry,
    BackgroundJob,
    ChatMessage,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeGap,
)
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
from app.domain_models.operations import OperationalEvent, OperationalKpiAggregate
from app.domain_models.organization import AuditLogEntry, DashboardPermission, Department, Site
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
    "AssistantTrainingEntry",
    "AuditLogEntry",
    "BackgroundJob",
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
    "KnowledgeChunk",
    "KnowledgeDocument",
    "KnowledgeGap",
    "Machine",
    "MachineManual",
    "MachineManualVersion",
    "MaintenancePlan",
    "NotificationDelivery",
    "Notification",
    "OperationalEvent",
    "OperationalKpiAggregate",
    "Priority",
    "Role",
    "ShiftHandover",
    "ShiftPlan",
    "ShiftPlanChangeLog",
    "ShiftPlanEntry",
    "Site",
    "Task",
    "TaskStatus",
    "TokenBlocklist",
    "User",
    "VacationRequest",
    "utc_now",
]
