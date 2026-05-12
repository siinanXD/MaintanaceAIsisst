"""In-app notification service for user-facing workflow updates."""

from datetime import UTC, datetime

from app.extensions import db
from app.models import DashboardPermission, Notification, Role, User


def unread_notifications_for_user(user, limit=50):
    """Return recent notifications and unread count for a user."""
    query = Notification.query.filter_by(recipient_user_id=user.id)
    notifications = (
        query.order_by(Notification.created_at.desc(), Notification.id.desc())
        .limit(max(1, min(int(limit or 50), 100)))
        .all()
    )
    unread_count = query.filter_by(is_read=False).count()
    return {
        "items": [notification.to_dict() for notification in notifications],
        "unread_count": unread_count,
    }


def mark_notification_read(notification, commit=True):
    """Mark one notification as read."""
    notification.is_read = True
    notification.read_at = datetime.now(UTC)
    if commit:
        db.session.commit()
    return notification


def mark_all_notifications_read(user):
    """Mark all unread notifications for a user as read."""
    now = datetime.now(UTC)
    notifications = Notification.query.filter_by(
        recipient_user_id=user.id,
        is_read=False,
    ).all()
    for notification in notifications:
        notification.is_read = True
        notification.read_at = now
    db.session.commit()
    return len(notifications)


def create_notification(recipient, notification_type, title, body, link_url=""):
    """Create one in-app notification for a user."""
    if not recipient or not recipient.is_active:
        return None
    notification = Notification(
        recipient_user_id=recipient.id,
        notification_type=str(notification_type)[:80],
        title=str(title)[:180],
        body=str(body or ""),
        link_url=str(link_url or "")[:500],
    )
    db.session.add(notification)
    return notification


def notify_shiftplan_change(plan, actor, action, entry=None):
    """Notify affected employees and plan admins about a shift plan change."""
    recipients = shiftplan_notification_recipients(plan, entry)
    action_label = {
        "publish": "veroeffentlicht",
        "unpublish": "zurueck auf Entwurf gesetzt",
        "update": "aktualisiert",
        "move": "verschoben",
        "swap": "getauscht",
        "delete": "geloescht",
    }.get(action, "geaendert")
    title = f"Schichtplan {action_label}"
    body = (
        f"{actor.username if actor else 'System'} hat den Plan " f"'{plan.title}' {action_label}."
    )
    if entry and entry.employee:
        body += f" Betroffen: {entry.employee.name} am {entry.work_date.isoformat()}."
    for recipient in recipients:
        if actor and recipient.id == actor.id:
            continue
        create_notification(
            recipient,
            f"shiftplan_{action}",
            title,
            body,
            link_url="/shiftplans",
        )


def shiftplan_notification_recipients(plan, entry=None):
    """Return users who should receive notifications for a shift plan change."""
    users_by_id = {}
    employee_ids = set()
    if entry and entry.employee_id:
        employee_ids.add(entry.employee_id)
    else:
        employee_ids.update(plan_entry.employee_id for plan_entry in plan.entries)

    for user in User.query.filter(User.employee_id.in_(employee_ids), User.is_active.is_(True)):
        users_by_id[user.id] = user

    admin_query = User.query.outerjoin(DashboardPermission).filter(User.is_active.is_(True))
    admin_query = admin_query.filter(
        (User.role == Role.MASTER_ADMIN)
        | (
            (DashboardPermission.dashboard == "shiftplans")
            & (DashboardPermission.can_write.is_(True))
        )
    )
    for user in admin_query.all():
        users_by_id[user.id] = user
    return list(users_by_id.values())
