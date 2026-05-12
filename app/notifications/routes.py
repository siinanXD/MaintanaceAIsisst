"""In-app notification API routes."""

from flask import Blueprint, request
from flask_jwt_extended import verify_jwt_in_request

from app.extensions import db
from app.models import Notification
from app.responses import error_response, success_response
from app.security import current_user
from app.services.in_app_notification_service import (
    mark_all_notifications_read,
    mark_notification_read,
    unread_notifications_for_user,
)

notifications_bp = Blueprint("notifications", __name__)


@notifications_bp.get("")
def list_notifications():
    """Return notifications for the current user."""
    verify_jwt_in_request()
    user = current_user()
    payload = unread_notifications_for_user(user, request.args.get("limit", 50))
    return success_response(payload, message="Notifications loaded")


@notifications_bp.patch("/<int:notification_id>/read")
def read_notification(notification_id):
    """Mark one notification as read for the current user."""
    verify_jwt_in_request()
    user = current_user()
    notification = db.session.get(Notification, notification_id)
    if not notification or notification.recipient_user_id != user.id:
        return error_response("Notification not found", 404)
    mark_notification_read(notification)
    return success_response(notification.to_dict(), message="Notification marked read")


@notifications_bp.patch("/read-all")
def read_all_notifications():
    """Mark all notifications as read for the current user."""
    verify_jwt_in_request()
    user = current_user()
    count = mark_all_notifications_read(user)
    return success_response({"updated": count}, message="Notifications marked read")
