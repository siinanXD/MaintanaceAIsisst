"""Central source visibility policy for AI knowledge retrieval."""

from dataclasses import dataclass

from app.extensions import db
from app.models import (
    AssistantTrainingEntry,
    ErrorEntry,
    GeneratedDocument,
    KnowledgeDocument,
    MaintenancePlan,
    Task,
)
from app.security import has_dashboard_permission
from app.services.document_service import visible_documents_query
from app.services.knowledge_quality_service import retrieval_quality_gate_for_document


@dataclass(frozen=True)
class SourceVisibilityRule:
    """Describe dashboard scopes required for one knowledge source type."""

    dashboards: tuple[str, ...]


DEFAULT_SOURCE_VISIBILITY_RULE = SourceVisibilityRule(dashboards=("documents",))
SOURCE_VISIBILITY_RULES = {
    "upload": SourceVisibilityRule(dashboards=("documents",)),
    "generated_document": SourceVisibilityRule(dashboards=("documents",)),
    "error_entry": SourceVisibilityRule(dashboards=("errors",)),
    "task": SourceVisibilityRule(dashboards=("tasks",)),
    "machine": SourceVisibilityRule(dashboards=("machines",)),
    "inventory_material": SourceVisibilityRule(dashboards=("inventory",)),
    "maintenance_plan": SourceVisibilityRule(dashboards=("machines",)),
    "machine_manual": SourceVisibilityRule(dashboards=("documents",)),
    "shift_handover": SourceVisibilityRule(dashboards=("shiftplans",)),
    "manual_training": SourceVisibilityRule(dashboards=("documents",)),
}


class SourceVisibilityPolicy:
    """Evaluate knowledge visibility by role, department and dashboard scope."""

    def can_read(self, user, document):
        """Return whether a user may consume a knowledge document in retrieval."""
        if not user or not document:
            return False
        if not self._passes_retrieval_quality_gate(document):
            return False
        if self._is_admin(user):
            return True
        if not getattr(document, "is_public", False):
            return False
        if not self._department_matches(user, getattr(document, "department", "")):
            return False

        source_type = self._source_type(document)
        if source_type == "generated_document":
            return self._can_read_generated_document(user, document)
        if source_type == "error_entry":
            return self._can_read_error_entry(user, document)
        if source_type == "task":
            return self._can_read_task(user, document)
        if source_type == "maintenance_plan":
            return self._can_read_maintenance_plan(user, document)
        if source_type == "manual_training":
            return self._can_read_manual_training(user, document)

        rule = SOURCE_VISIBILITY_RULES.get(source_type, DEFAULT_SOURCE_VISIBILITY_RULE)
        return self._has_any_dashboard(user, rule.dashboards)

    def _can_read_generated_document(self, user, document):
        """Return whether a generated document source is visible to the user."""
        if not self._has_any_dashboard(user, ("documents",)):
            return False
        if not document.source_id:
            return False
        return (
            visible_documents_query(user)
            .filter(GeneratedDocument.id == document.source_id)
            .first()
            is not None
        )

    def _can_read_error_entry(self, user, document):
        """Return whether an error-entry source is visible to the user."""
        if not self._has_any_dashboard(user, ("errors",)):
            return False
        if not document.source_id:
            return False
        from app.services.error_service import visible_errors_query

        return (
            visible_errors_query(user).filter(ErrorEntry.id == document.source_id).first()
            is not None
        )

    def _can_read_task(self, user, document):
        """Return whether a task source is visible to the user."""
        if not self._has_any_dashboard(user, ("tasks",)):
            return False
        if not document.source_id:
            return False
        from app.services.task_service import visible_tasks_query

        return visible_tasks_query(user).filter(Task.id == document.source_id).first() is not None

    def _can_read_maintenance_plan(self, user, document):
        """Return whether a maintenance-plan source is visible to the user."""
        if not self._has_any_dashboard(user, ("machines",)):
            return False
        if not document.source_id:
            return False
        from app.machines.maintenance_services import visible_maintenance_plans_query

        return (
            visible_maintenance_plans_query(user)
            .filter(MaintenancePlan.id == document.source_id)
            .first()
            is not None
        )

    def _can_read_manual_training(self, user, document):
        """Return whether a manual training source is visible to the user."""
        if not self._has_any_dashboard(user, ("documents",)):
            return False
        if not document.source_id:
            return False
        entry = db.session.get(AssistantTrainingEntry, document.source_id)
        if not entry or not entry.is_active:
            return False
        return self._department_matches(user, entry.department)

    def _has_any_dashboard(self, user, dashboards):
        """Return whether the user may view at least one dashboard scope."""
        return any(has_dashboard_permission(user, dashboard, "view") for dashboard in dashboards)

    def _department_matches(self, user, department):
        """Return whether a source department is unscoped or matches the user."""
        if not department:
            return True
        return bool(user.department and user.department.name == department)

    def _passes_retrieval_quality_gate(self, document):
        """Return whether quality status allows retrieval exposure."""
        return retrieval_quality_gate_for_document(document).allowed

    def _source_type(self, document):
        """Return a normalized source type for a knowledge document."""
        return str(getattr(document, "source_type", "") or "").strip()

    def _is_admin(self, user):
        """Return whether the user has master administrator access."""
        return bool(getattr(user, "is_admin", False))


SOURCE_VISIBILITY_POLICY = SourceVisibilityPolicy()


def can_user_read_source_document(user, document):
    """Return the central source visibility decision for a knowledge document."""
    if not isinstance(document, KnowledgeDocument):
        return False
    return SOURCE_VISIBILITY_POLICY.can_read(user, document)
