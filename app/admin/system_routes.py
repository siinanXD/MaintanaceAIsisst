"""Admin API route registrations."""

# ruff: noqa: F401, F403, F405

from app.admin.blueprint import admin_bp
from app.admin.route_helpers import *


@admin_bp.get("/audit-log")
@roles_required(Role.MASTER_ADMIN)
def audit_log():
    """Return global security audit entries for administrators."""
    try:
        query = audit_log_query(request.args)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return paginated_audit_response(query)


@admin_bp.get("/backups")
@roles_required(Role.MASTER_ADMIN)
def backups():
    """Return available backup archives."""
    return jsonify({"success": True, "data": list_backups(), "message": "Backups loaded"})


@admin_bp.post("/backups")
@roles_required(Role.MASTER_ADMIN)
def create_backup_route():
    """Create a backup archive and audit the action."""
    user = current_admin_user()
    metadata = create_backup(actor=user, reason="api")
    create_audit_log(
        user,
        "backup.create",
        "backup",
        metadata["id"],
        after={"backup": metadata},
        commit=True,
    )
    return jsonify({"success": True, "data": metadata, "message": "Backup created"}), 201


@admin_bp.get("/backups/<path:backup_id>/download")
@roles_required(Role.MASTER_ADMIN)
def download_backup(backup_id):
    """Download a backup archive."""
    path = backup_path_for(backup_id)
    if not path:
        return error_response("Backup not found", 404)
    return send_file(path, mimetype="application/zip", as_attachment=True, download_name=path.name)


@admin_bp.post("/backups/<path:backup_id>/restore")
@roles_required(Role.MASTER_ADMIN)
def restore_backup_route(backup_id):
    """Restore a backup archive after explicit confirmation."""
    user = current_admin_user()
    data = request.get_json(silent=True) or {}
    create_audit_log(
        user,
        "backup.restore",
        "backup",
        backup_id,
        after={"requested_backup": backup_id, "confirmed": bool(data.get("confirm"))},
        commit=True,
    )
    result, error, status = restore_backup(backup_id, actor=user, confirm=bool(data.get("confirm")))
    if error:
        return error_response(error["error"], status)
    return jsonify({"success": True, "data": result, "message": "Backup restored"}), status


@admin_bp.get("/notifications/deliveries")
@roles_required(Role.MASTER_ADMIN)
def notification_deliveries():
    """Return notification delivery records for administrators."""
    return paginated_delivery_response(delivery_query(request.args))


@admin_bp.post("/notifications/test-email")
@roles_required(Role.MASTER_ADMIN)
def test_email():
    """Send a test email to the provided recipient or current admin."""
    actor = current_admin_user()
    data = request.get_json(silent=True) or {}
    recipient_email = str(data.get("recipient_email") or actor.email).strip()
    delivery = send_test_email(recipient_email, actor=actor)
    return (
        jsonify(
            {
                "success": True,
                "data": delivery.to_dict() if delivery else None,
                "mail": mail_config_status(),
                "message": "Test email recorded",
            }
        ),
        201,
    )


@admin_bp.get("/sites")
@roles_required(Role.MASTER_ADMIN)
def admin_sites():
    """Return all sites for master-admin maintenance."""
    include_inactive = str(request.args.get("include_inactive", "true")).lower() not in {
        "0",
        "false",
        "no",
    }
    return success_response(
        [site.to_dict() for site in list_sites(include_inactive=include_inactive)],
        message="Sites loaded",
    )


@admin_bp.post("/sites")
@roles_required(Role.MASTER_ADMIN)
def admin_create_site():
    """Create a site."""
    actor = current_admin_user()
    site, error, status = create_site(request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    record_event(
        "site.created",
        "operations",
        entity_type="site",
        entity_id=site.id,
        user=actor,
        site_id=site.id,
        source="admin",
        metadata={"code": site.code, "name": site.name},
        commit=True,
    )
    return success_response(site.to_dict(), status, "Site created")


@admin_bp.put("/sites/<int:site_id>")
@roles_required(Role.MASTER_ADMIN)
def admin_update_site(site_id):
    """Update a site."""
    actor = current_admin_user()
    site = db.get_or_404(Site, site_id)
    updated, error, status = update_site(site, request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    record_event(
        "site.updated",
        "operations",
        entity_type="site",
        entity_id=updated.id,
        user=actor,
        site_id=updated.id,
        source="admin",
        metadata={"code": updated.code, "name": updated.name, "is_active": updated.is_active},
        commit=True,
    )
    return success_response(updated.to_dict(), status, "Site updated")


@admin_bp.post("/operations/aggregate")
@roles_required(Role.MASTER_ADMIN)
def admin_aggregate_operations():
    """Rebuild persisted operations KPI aggregates."""
    actor = current_admin_user()
    payload = request.get_json(silent=True) or {}
    try:
        result = aggregate_operations(
            period_type=payload.get("period_type", "day"),
            args=payload,
            user=None,
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    record_event(
        "operations.aggregate",
        "operations",
        entity_type="operational_kpi_aggregate",
        user=actor,
        source="admin",
        metadata={
            "period_type": result["period_type"],
            "aggregates": result["aggregates"],
            "events": result["events"],
        },
        commit=True,
    )
    return success_response(result, message="Operations aggregates rebuilt")


__all__ = [
    "audit_log",
    "backups",
    "create_backup_route",
    "download_backup",
    "restore_backup_route",
    "notification_deliveries",
    "test_email",
    "admin_sites",
    "admin_create_site",
    "admin_update_site",
    "admin_aggregate_operations",
]
