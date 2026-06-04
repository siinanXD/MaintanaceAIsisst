"""Notification workflows for tasks, AI alerts, and daily briefings."""

import hashlib
from collections import Counter
from datetime import UTC, date, datetime, timedelta

from flask import current_app

from app.ai.briefings import daily_briefing
from app.extensions import db
from app.models import AIAuditEvent, NotificationDelivery, Priority, Role, Task, TaskStatus, User
from app.permissions import has_permission
from app.services.mail_service import send_email

AI_ALERT_CATEGORIES = {
    "authentication_error",
    "connection_error",
    "model_not_found",
    "permission_denied",
    "rate_limit",
    "timeout",
}
TERMINAL_TASK_STATUSES = {TaskStatus.DONE, TaskStatus.CANCELLED}


def send_task_alerts(today=None):
    """Send deduplicated alerts for urgent open or in-progress tasks."""
    today = today or date.today()
    tasks = (
        Task.query.filter(
            Task.priority == Priority.URGENT,
            Task.status.in_([TaskStatus.OPEN, TaskStatus.IN_PROGRESS]),
        )
        .order_by(Task.due_date.asc(), Task.id.asc())
        .all()
    )
    return _send_task_notifications("task_urgent", tasks, today)


def send_overdue_reminders(today=None):
    """Send deduplicated reminders for overdue unfinished tasks."""
    today = today or date.today()
    tasks = (
        Task.query.filter(
            Task.due_date < today,
            Task.status.notin_(list(TERMINAL_TASK_STATUSES)),
        )
        .order_by(Task.due_date.asc(), Task.id.asc())
        .all()
    )
    return _send_task_notifications("task_overdue", tasks, today)


def send_ai_alerts(now=None):
    """Send aggregated AI error alerts to active master administrators."""
    now = now or datetime.now(UTC)
    lookback_minutes = int(current_app.config.get("AI_ALERT_LOOKBACK_MINUTES", 60))
    since = now - timedelta(minutes=lookback_minutes)
    events = (
        AIAuditEvent.query.filter(
            AIAuditEvent.created_at >= since,
            AIAuditEvent.error_category.in_(AI_ALERT_CATEGORIES),
        )
        .order_by(AIAuditEvent.created_at.asc())
        .all()
    )
    if not events:
        return _summary("ai_alert", 0, 0)

    recipients = active_master_admins()
    fingerprint = _hash_text(",".join(str(event.id) for event in events))
    subject = f"Maintenance AI Warnung: {len(events)} Fehler"
    body = _ai_alert_body(events, since, now)
    deliveries = []
    for recipient in recipients:
        deliveries.append(
            send_email(
                recipient_email=recipient.email,
                subject=subject,
                body=body,
                notification_type="ai_alert",
                dedupe_key=f"ai_alert:{recipient.id}:{fingerprint}",
                recipient_user=recipient,
                payload={"event_count": len(events), "since": since.isoformat()},
            )
        )
    return _summary("ai_alert", len(events), _count_created(deliveries))


def send_daily_briefings(today=None):
    """Send one daily briefing email to each active user with visible briefing content."""
    today = today or date.today()
    deliveries = []
    users = User.query.filter_by(is_active=True).order_by(User.id.asc()).all()
    for user in users:
        if not _wants_daily_briefing(user):
            continue
        briefing = daily_briefing(user)
        if not briefing.get("sections"):
            continue
        deliveries.append(
            send_email(
                recipient_email=user.email,
                subject=f"Maintenance Tagesbriefing {today.isoformat()}",
                body=_daily_briefing_body(user, briefing),
                notification_type="daily_briefing",
                dedupe_key=f"daily_briefing:{today.isoformat()}:{user.id}",
                recipient_user=user,
                payload={"date": today.isoformat(), "section_count": len(briefing["sections"])},
            )
        )
    return _summary("daily_briefing", len(users), _count_created(deliveries))


def delivery_query(filters):
    """Return notification delivery records filtered for the admin API."""
    query = NotificationDelivery.query
    notification_type = str(filters.get("type") or "").strip()
    status = str(filters.get("status") or "").strip()
    q = str(filters.get("q") or "").strip()
    if notification_type:
        query = query.filter(NotificationDelivery.notification_type == notification_type)
    if status:
        query = query.filter(NotificationDelivery.status == status)
    if q:
        needle = f"%{q}%"
        query = query.filter(
            db.or_(
                NotificationDelivery.recipient_email.ilike(needle),
                NotificationDelivery.subject.ilike(needle),
                NotificationDelivery.dedupe_key.ilike(needle),
            )
        )
    return query.order_by(NotificationDelivery.created_at.desc(), NotificationDelivery.id.desc())


def send_test_email(recipient_email, actor=None):
    """Send a test email to verify SMTP configuration."""
    recipient = actor if actor and actor.email == recipient_email else None
    return send_email(
        recipient_email=recipient_email,
        subject="Maintenance Assistant Test-Mail",
        body="Diese Test-Mail prueft die SMTP-Konfiguration.",
        notification_type="test_email",
        dedupe_key=f"test_email:{datetime.now(UTC).isoformat()}:{recipient_email}",
        recipient_user=recipient,
        payload={"requested_by": getattr(actor, "username", None)},
    )


def _send_task_notifications(notification_type, tasks, today):
    """Send one task notification per recipient and task."""
    deliveries = []
    for task in tasks:
        recipients = task_recipients(task)
        for recipient in recipients:
            deliveries.append(
                send_email(
                    recipient_email=recipient.email,
                    subject=_task_subject(notification_type, task),
                    body=_task_body(notification_type, task),
                    notification_type=notification_type,
                    dedupe_key=f"{notification_type}:{today.isoformat()}:{task.id}:{recipient.id}",
                    recipient_user=recipient,
                    payload={"task_id": task.id, "due_date": task.due_date.isoformat()},
                )
            )
    return _summary(notification_type, len(tasks), _count_created(deliveries))


def task_recipients(task):
    """Return active users who should receive a task notification."""
    recipients = []
    for user in (task.current_worker, task.creator):
        if _can_receive_task_mail(user, task):
            recipients.append(user)
    for admin in active_master_admins():
        if _can_receive_task_mail(admin, task):
            recipients.append(admin)
    return _unique_users(recipients)


def active_master_admins():
    """Return active master administrators with email addresses."""
    return (
        User.query.filter(
            User.is_active.is_(True),
            User.role == Role.MASTER_ADMIN,
            User.email != "",
        )
        .order_by(User.id.asc())
        .all()
    )


def _can_receive_task_mail(user, task):
    """Return whether a user can receive a task notification."""
    if not user or not user.is_active or not user.email:
        return False
    if not has_permission(user, "tasks", "view"):
        return False
    return bool(user.is_admin or user.department_id == task.department_id)


def _wants_daily_briefing(user):
    """Return whether a user has at least one briefing-relevant permission."""
    if not user or not user.is_active or not user.email:
        return False
    return any(
        has_permission(user, dashboard, "view")
        for dashboard in ("tasks", "inventory", "errors", "documents")
    )


def _task_subject(notification_type, task):
    """Return a concise subject for one task notification."""
    prefix = "Dringender Task" if notification_type == "task_urgent" else "Ueberfaelliger Task"
    return f"{prefix}: {task.title}"


def _task_body(notification_type, task):
    """Return a plain-text task notification body."""
    heading = "Dringender Task" if notification_type == "task_urgent" else "Ueberfaellige Aufgabe"
    department = task.department.name if task.department else "-"
    worker = task.current_worker.username if task.current_worker else "nicht zugewiesen"
    return "\n".join(
        [
            heading,
            "",
            f"Titel: {task.title}",
            f"Status: {task.status.value}",
            f"Prioritaet: {task.priority.value}",
            f"Faellig: {task.due_date.isoformat()}",
            f"Bereich: {department}",
            f"Bearbeiter: {worker}",
            "",
            "Bitte im Maintenance Assistant pruefen.",
        ]
    )


def _ai_alert_body(events, since, now):
    """Return an aggregated AI alert body without prompts, answers, or secrets."""
    category_counts = Counter(event.error_category for event in events)
    workflow_counts = Counter(event.workflow for event in events)
    models = sorted({event.model for event in events if event.model})
    lines = [
        "AI-Admin-Warnung",
        "",
        f"Zeitraum: {since.isoformat()} bis {now.isoformat()}",
        f"Fehler gesamt: {len(events)}",
        "",
        "Fehlerkategorien:",
    ]
    lines.extend(f"- {name}: {count}" for name, count in category_counts.most_common())
    lines.append("")
    lines.append("Workflows:")
    lines.extend(f"- {name}: {count}" for name, count in workflow_counts.most_common())
    lines.append("")
    lines.append("Modelle: " + (", ".join(models) if models else "-"))
    lines.append("")
    lines.append("Diese Mail enthaelt nur Nutzungsmetadaten, keine Prompts oder Antworten.")
    return "\n".join(lines)


def _daily_briefing_body(user, briefing):
    """Return a plain-text daily briefing body."""
    lines = [
        f"Hallo {user.username},",
        "",
        briefing.get("summary", "Tagesbriefing"),
        "",
    ]
    for section in briefing.get("sections", []):
        lines.append(f"{section['title']} ({section['count']})")
        for item in section.get("items", []):
            lines.append(f"- {item['title']}: {item['summary']}")
        lines.append("")
    lines.append("Quelle: Maintenance Assistant")
    return "\n".join(lines)


def _unique_users(users):
    """Return users deduplicated by id while preserving order."""
    seen = set()
    result = []
    for user in users:
        if user.id in seen:
            continue
        seen.add(user.id)
        result.append(user)
    return result


def _count_created(deliveries):
    """Return how many delivery calls created a record instead of being deduped."""
    return sum(1 for delivery in deliveries if delivery is not None)


def _summary(notification_type, scanned, created):
    """Return a compact job summary."""
    return {
        "notification_type": notification_type,
        "scanned": scanned,
        "deliveries_created": created,
    }


def _hash_text(value):
    """Return a short stable hash for dedupe fingerprints."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]
