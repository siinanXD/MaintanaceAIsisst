import logging

from app.services.document_service import generate_maintenance_report
from app.services.task_service import complete_task


logger = logging.getLogger(__name__)


def complete_task_workflow(task, user, payload=None):
    """Complete a task and optionally generate a maintenance report."""
    payload = payload or {}
    updated, error, status = complete_task(task, user)
    if error:
        return None, None, error, status

    document = None
    if payload.get("generate_report"):
        try:
            document = generate_maintenance_report(updated, user, payload)
        except (OSError, ValueError) as exc:
            logger.exception(
                "maintenance_report_generation_failed task_id=%s user_id=%s",
                task.id,
                user.id,
            )
            return updated, None, {"error": str(exc)}, 500

    return updated, document, None, status
