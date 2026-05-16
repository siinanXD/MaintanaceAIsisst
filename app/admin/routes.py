"""Admin API routes for user and audit management."""

from datetime import UTC, datetime, timedelta

from flask import Blueprint, jsonify, request, send_file

from app.auth.services import find_department, parse_role
from app.extensions import db
from app.models import (
    AIAuditEvent,
    AssistantTrainingEntry,
    Employee,
    KnowledgeDocument,
    Role,
    Site,
    User,
)
from app.permissions import (
    permission_schema,
    replace_user_permissions,
    serialize_permissions,
    upsert_default_permissions,
)
from app.responses import error_response, service_error_response, success_response
from app.security import roles_required
from app.services.ai_audit_service import ai_analytics_summary
from app.services.ai_history_service import paginated_chat_history, parse_limit_offset
from app.services.assistant_training_service import (
    create_training_entry,
    delete_training_entry,
    list_training_entries,
    update_training_entry,
)
from app.services.audit_service import audit_log_query, create_audit_log
from app.services.background_job_service import (
    enqueue_rag_reindex_job,
    list_background_jobs,
)
from app.services.backup_service import (
    backup_path_for,
    create_backup,
    list_backups,
    restore_backup,
)
from app.services.database_schema_service import (
    database_schema_error_payload,
    database_schema_status,
)
from app.services.knowledge_service import (
    delete_knowledge_document,
    knowledge_index_status,
    list_knowledge_documents,
    reindex_all_knowledge,
    reindex_knowledge_document,
    reindex_stale_knowledge,
    upload_knowledge_document,
)
from app.services.mail_service import mail_config_status
from app.services.notification_service import delivery_query, send_test_email
from app.services.operations_tracking_service import aggregate_operations, record_event
from app.services.site_service import create_site, list_sites, update_site

admin_bp = Blueprint("admin", __name__)


def parse_optional_bool(value, default=True):
    """Parse optional JSON booleans and common string values."""
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError("is_active must be a boolean")


def find_user_conflict(username=None, email=None, exclude_user_id=None):
    """Return an existing user with the same username or email, if any."""
    filters = []
    if username:
        filters.append(User.username == username)
    if email:
        filters.append(User.email == email)
    if not filters:
        return None

    query = User.query.filter(db.or_(*filters))
    if exclude_user_id is not None:
        query = query.filter(User.id != exclude_user_id)
    return query.first()


def validate_user_department(role, department):
    """Raise when a non-admin user has no department assignment."""
    if role != Role.MASTER_ADMIN and not department:
        raise ValueError("department_id or department is required")


def find_employee(employee_id):
    """Return an employee for an optional admin user payload value."""
    if employee_id in (None, ""):
        return None
    try:
        parsed_employee_id = int(employee_id)
    except (TypeError, ValueError) as exc:
        raise ValueError("employee_id must be a valid employee id") from exc
    employee = db.session.get(Employee, parsed_employee_id)
    if not employee:
        raise ValueError("employee_id does not reference an existing employee")
    return employee


def user_audit_payload(user):
    """Return a safe user snapshot for admin audit logs."""
    if not user:
        return {}
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "role": user.role.value,
        "department_id": user.department_id,
        "employee_id": user.employee_id,
        "is_active": user.is_active,
        "permissions": serialize_permissions(user),
    }


def paginated_audit_response(query):
    """Return a paginated audit log response."""
    try:
        limit = min(max(1, int(request.args.get("limit", 50))), 200)
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        return error_response("limit and offset must be integers", 400)
    total = query.count()
    entries = query.offset(offset).limit(limit).all()
    return jsonify(
        {
            "success": True,
            "data": [entry.to_dict() for entry in entries],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
            "message": "Audit log loaded",
        }
    )


def paginated_delivery_response(query):
    """Return a paginated notification delivery response."""
    try:
        limit = min(max(1, int(request.args.get("limit", 50))), 200)
        offset = max(0, int(request.args.get("offset", 0)))
    except (TypeError, ValueError):
        return error_response("limit and offset must be integers", 400)
    total = query.count()
    deliveries = query.offset(offset).limit(limit).all()
    return jsonify(
        {
            "success": True,
            "data": [delivery.to_dict() for delivery in deliveries],
            "pagination": {
                "limit": limit,
                "offset": offset,
                "total": total,
            },
            "mail": mail_config_status(),
            "message": "Notification deliveries loaded",
        }
    )


@admin_bp.get("/users")
@roles_required(Role.MASTER_ADMIN)
def list_users():
    """Return users filtered by optional query parameters: q, role, status."""
    q = request.args.get("q", "").strip()
    role_param = request.args.get("role", "").strip()
    status_param = request.args.get("status", "").strip()

    query = User.query
    if q:
        query = query.filter(db.or_(User.username.ilike(f"%{q}%"), User.email.ilike(f"%{q}%")))
    if role_param:
        try:
            query = query.filter(User.role == Role(role_param))
        except ValueError:
            return error_response(f"Invalid role: {role_param}", 400)
    if status_param == "active":
        query = query.filter(User.is_active.is_(True))
    elif status_param == "inactive":
        query = query.filter(User.is_active.is_(False))

    users = query.order_by(User.id.asc()).all()
    return jsonify([user.to_dict() for user in users])


@admin_bp.get("/permissions/schema")
@roles_required(Role.MASTER_ADMIN)
def permissions_schema():
    """Return labels, groups and role defaults for the permission editor."""
    return jsonify(permission_schema())


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


@admin_bp.get("/ai/summary")
@roles_required(Role.MASTER_ADMIN)
def ai_summary():
    """Return AI audit and feedback analytics for administrators."""
    try:
        days = int(request.args.get("days", 7))
    except (TypeError, ValueError):
        return error_response("days must be an integer between 1 and 90", 400)
    if days < 1 or days > 90:
        return error_response("days must be an integer between 1 and 90", 400)
    return jsonify(ai_analytics_summary(days))


@admin_bp.get("/ai/chats")
@roles_required(Role.MASTER_ADMIN)
def ai_chats():
    """Return searchable AI chat contents for master administrators."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    try:
        result = paginated_chat_history(current_admin_user(), request.args, include_all=True)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(result, message="AI chats loaded")


@admin_bp.get("/ai/events")
@roles_required(Role.MASTER_ADMIN)
def ai_events():
    """Return filtered metadata-only AI audit events."""
    try:
        query = filtered_ai_event_query(request.args)
        limit, offset = parse_limit_offset(request.args, default_limit=50)
    except ValueError as exc:
        return error_response(str(exc), 400)
    total = query.count()
    events = query.offset(offset).limit(limit).all()
    return success_response(
        {
            "items": [event.to_dict() for event in events],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
        message="AI events loaded",
    )


@admin_bp.get("/ai/training")
@roles_required(Role.MASTER_ADMIN)
def ai_training_entries():
    """Return filtered manual assistant training entries."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    try:
        limit, offset = parse_limit_offset(request.args, default_limit=50)
    except ValueError as exc:
        return error_response(str(exc), 400)
    query = list_training_entries(request.args)
    total = query.count()
    entries = query.offset(offset).limit(limit).all()
    return success_response(
        {
            "items": [entry.to_dict() for entry in entries],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
        message="Training entries loaded",
    )


@admin_bp.post("/ai/training")
@roles_required(Role.MASTER_ADMIN)
def create_ai_training_entry():
    """Create a manual assistant training entry."""
    actor = current_admin_user()
    result, error, status = create_training_entry(
        request.get_json(silent=True) or {},
        actor,
    )
    if error:
        return service_error_response(error, status)
    record_event(
        "ai.training_created",
        "ai",
        entity_type="assistant_training_entry",
        entity_id=result["id"],
        user=actor,
        source="admin",
        metadata={
            "category": result.get("category"),
            "department": result.get("department"),
            "priority": result.get("priority"),
            "is_active": result.get("is_active"),
        },
        commit=True,
    )
    return success_response(result, status, "Training entry created")


@admin_bp.put("/ai/training/<int:entry_id>")
@roles_required(Role.MASTER_ADMIN)
def update_ai_training_entry(entry_id):
    """Update a manual assistant training entry."""
    actor = current_admin_user()
    entry = db.get_or_404(AssistantTrainingEntry, entry_id)
    result, error, status = update_training_entry(entry, request.get_json(silent=True) or {})
    if error:
        return service_error_response(error, status)
    record_event(
        "ai.training_updated",
        "ai",
        entity_type="assistant_training_entry",
        entity_id=entry_id,
        user=actor,
        source="admin",
        metadata={
            "category": result.get("category"),
            "department": result.get("department"),
            "priority": result.get("priority"),
            "is_active": result.get("is_active"),
        },
        commit=True,
    )
    return success_response(result, status, "Training entry updated")


@admin_bp.delete("/ai/training/<int:entry_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_ai_training_entry(entry_id):
    """Delete a manual assistant training entry."""
    actor = current_admin_user()
    entry = db.get_or_404(AssistantTrainingEntry, entry_id)
    metadata = {
        "title": entry.title,
        "category": entry.category,
        "department": entry.department,
        "priority": entry.priority,
    }
    result, error, status = delete_training_entry(entry)
    if error:
        return service_error_response(error, status)
    record_event(
        "ai.training_deleted",
        "ai",
        entity_type="assistant_training_entry",
        entity_id=entry_id,
        user=actor,
        source="admin",
        metadata=metadata,
        commit=True,
    )
    return success_response(result, status, "Training entry deleted")


@admin_bp.post("/ai/knowledge/upload")
@roles_required(Role.MASTER_ADMIN)
def upload_ai_knowledge():
    """Upload and index a local knowledge document."""
    actor = current_admin_user()
    result, error, status = upload_knowledge_document(
        request.files.get("file"),
        actor,
        department=request.form.get("department", ""),
    )
    if error:
        return service_error_response(error, status)
    record_event(
        "rag.knowledge_uploaded",
        "ai",
        entity_type="knowledge_document",
        entity_id=result.get("id"),
        user=actor,
        source="admin",
        metadata={
            "source_type": result.get("source_type"),
            "department": result.get("department"),
            "status": result.get("status"),
        },
        commit=True,
    )
    return success_response(result, status, "Knowledge document uploaded")


@admin_bp.get("/ai/knowledge")
@roles_required(Role.MASTER_ADMIN)
def ai_knowledge():
    """Return filtered local knowledge documents."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    try:
        limit, offset = parse_limit_offset(request.args, default_limit=50)
    except ValueError as exc:
        return error_response(str(exc), 400)
    query = list_knowledge_documents(request.args)
    total = query.count()
    documents = query.offset(offset).limit(limit).all()
    return success_response(
        {
            "items": [document.to_dict() for document in documents],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
        message="Knowledge documents loaded",
    )


@admin_bp.get("/ai/knowledge/status")
@roles_required(Role.MASTER_ADMIN)
def ai_knowledge_status():
    """Return RAG index status and searchable source diagnostics."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    return success_response(knowledge_index_status(), message="Knowledge status loaded")


@admin_bp.get("/jobs")
@roles_required(Role.MASTER_ADMIN)
def admin_background_jobs():
    """Return background jobs for admin observability."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    try:
        limit, offset = parse_limit_offset(request.args, default_limit=20)
    except ValueError as exc:
        return error_response(str(exc), 400)
    query = list_background_jobs(request.args)
    total = query.count()
    jobs = query.offset(offset).limit(limit).all()
    return success_response(
        {
            "items": [job.to_dict() for job in jobs],
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
        message="Background jobs loaded",
    )


@admin_bp.post("/ai/knowledge/reindex/jobs")
@roles_required(Role.MASTER_ADMIN)
def queue_ai_knowledge_reindex_job():
    """Queue a background job for a RAG reindex workflow."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    actor = current_admin_user()
    data = request.get_json(silent=True) or {}
    try:
        job = enqueue_rag_reindex_job(
            mode=data.get("mode", "stale"),
            document_id=data.get("document_id"),
            user=actor,
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    record_event(
        "rag.reindex_queued",
        "ai",
        entity_type="background_job",
        entity_id=job.id,
        user=actor,
        source="admin",
        metadata={"job_type": job.job_type, "status": job.status},
        commit=True,
    )
    return success_response(job.to_dict(), 202, "Background job queued")


@admin_bp.post("/ai/knowledge/reindex")
@roles_required(Role.MASTER_ADMIN)
def reindex_ai_knowledge():
    """Rebuild the local knowledge index."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    mode = str(request.args.get("mode") or "all").strip().lower()
    if mode == "stale":
        result = reindex_stale_knowledge()
    elif mode == "all":
        result = reindex_all_knowledge()
    else:
        return error_response("mode must be 'all' or 'stale'", 400)
    record_event(
        "rag.reindexed",
        "ai",
        entity_type="knowledge_document",
        user=current_admin_user(),
        source="admin",
        metadata={"mode": mode, "result": result},
        commit=True,
    )
    return success_response(result, message="Knowledge reindexed")


@admin_bp.post("/ai/knowledge/<int:document_id>/reindex")
@roles_required(Role.MASTER_ADMIN)
def reindex_ai_knowledge_document(document_id):
    """Reindex one local knowledge document."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    document = db.get_or_404(KnowledgeDocument, document_id)
    result = reindex_knowledge_document(document)
    record_event(
        "rag.document_reindexed",
        "ai",
        entity_type="knowledge_document",
        entity_id=document_id,
        user=current_admin_user(),
        source="admin",
        metadata={"source_type": document.source_type, "status": document.status},
        commit=True,
    )
    return success_response(result, message="Knowledge document reindexed")


@admin_bp.delete("/ai/knowledge/<int:document_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_ai_knowledge(document_id):
    """Delete a knowledge document and its chunks."""
    document = db.get_or_404(KnowledgeDocument, document_id)
    metadata = {"source_type": document.source_type, "department": document.department}
    delete_knowledge_document(document)
    record_event(
        "rag.knowledge_deleted",
        "ai",
        entity_type="knowledge_document",
        entity_id=document_id,
        user=current_admin_user(),
        source="admin",
        metadata=metadata,
        commit=True,
    )
    return success_response({"id": document_id}, message="Knowledge document deleted")


def filtered_ai_event_query(args):
    """Return an AI audit event query filtered from request arguments."""
    query = AIAuditEvent.query
    workflow = str(args.get("workflow") or "").strip()
    status = str(args.get("status") or "").strip()
    error = str(args.get("error") or "").strip()
    if workflow:
        query = query.filter(AIAuditEvent.workflow == workflow)
    if status:
        query = query.filter(AIAuditEvent.status == status)
    if error:
        query = query.filter(AIAuditEvent.error_category == error)
    days = args.get("days")
    if days not in (None, ""):
        try:
            days_value = int(days)
        except (TypeError, ValueError) as exc:
            raise ValueError("days must be an integer between 1 and 90") from exc
        if days_value < 1 or days_value > 90:
            raise ValueError("days must be an integer between 1 and 90")
        query = query.filter(
            AIAuditEvent.created_at >= datetime.now(UTC) - timedelta(days=days_value)
        )
    return query.order_by(AIAuditEvent.created_at.desc(), AIAuditEvent.id.desc())


def current_admin_user():
    """Return the current authenticated master admin."""
    from app.security import current_user

    return current_user()


@admin_bp.post("/users")
@roles_required(Role.MASTER_ADMIN)
def create_user():
    """Create a user and assign default permissions for the selected role."""
    actor = current_admin_user()
    data = request.get_json(silent=True) or {}
    required = ["username", "email", "password", "role"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return error_response(f"Missing fields: {', '.join(missing)}", 400)

    if find_user_conflict(data["username"], data["email"]):
        return error_response("Username or email already exists", 409)

    try:
        role = parse_role(data.get("role"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    department = find_department(data.get("department_id"), data.get("department"))
    try:
        validate_user_department(role, department)
        is_active = parse_optional_bool(data.get("is_active"), default=True)
        employee = find_employee(data.get("employee_id"))
    except ValueError as exc:
        return error_response(str(exc), 400)

    user = User(
        username=data["username"],
        email=data["email"],
        role=role,
        department=department,
        is_active=is_active,
    )
    user.employee = employee
    user.set_password(data["password"])
    db.session.add(user)
    db.session.flush()
    upsert_default_permissions(user)
    db.session.commit()
    create_audit_log(
        actor,
        "user.create",
        "user",
        user.id,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict()), 201


@admin_bp.put("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def update_user(user_id):
    """Update a user account and fill missing default permissions."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    data = request.get_json(silent=True) or {}

    username = data.get("username", user.username)
    email = data.get("email", user.email)
    if find_user_conflict(username, email, exclude_user_id=user.id):
        return error_response("Username or email already exists", 409)

    role = user.role
    if "role" in data:
        try:
            role = parse_role(data["role"])
        except ValueError as exc:
            return error_response(str(exc), 400)
    department = user.department
    if "department_id" in data or "department" in data:
        department = find_department(data.get("department_id"), data.get("department"))
    is_active = user.is_active
    if "is_active" in data:
        try:
            is_active = parse_optional_bool(data["is_active"])
        except ValueError as exc:
            return error_response(str(exc), 400)
    employee = user.employee
    if "employee_id" in data:
        try:
            employee = find_employee(data.get("employee_id"))
        except ValueError as exc:
            return error_response(str(exc), 400)
    try:
        validate_user_department(role, department)
    except ValueError as exc:
        return error_response(str(exc), 400)

    user.username = username
    user.email = email
    user.role = role
    user.department = department
    user.employee = employee
    user.is_active = is_active

    upsert_default_permissions(user)
    db.session.commit()
    create_audit_log(
        actor,
        "user.update",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.get("/users/<int:user_id>/permissions")
@roles_required(Role.MASTER_ADMIN)
def get_user_permissions(user_id):
    """Return effective dashboard permissions for a user."""
    user = db.get_or_404(User, user_id)
    return jsonify(serialize_permissions(user))


@admin_bp.put("/users/<int:user_id>/permissions")
@roles_required(Role.MASTER_ADMIN)
def update_user_permissions(user_id):
    """Replace dashboard permissions for a user."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    data = request.get_json(silent=True) or {}
    try:
        replace_user_permissions(user, data)
    except ValueError as exc:
        return error_response(str(exc), 400)
    db.session.commit()
    create_audit_log(
        actor,
        "permissions.update",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/reset-password")
@roles_required(Role.MASTER_ADMIN)
def reset_password(user_id):
    """Reset a user's password."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    password = (request.get_json(silent=True) or {}).get("password")
    if not password:
        return error_response("password is required", 400)
    user.set_password(password)
    db.session.commit()
    create_audit_log(
        actor,
        "user.reset_password",
        "user",
        user.id,
        before={"id": user.id, "username": user.username},
        after={"password_reset": True},
        commit=True,
    )
    return jsonify({"message": "Password reset successful"})


@admin_bp.post("/users/<int:user_id>/lock")
@roles_required(Role.MASTER_ADMIN)
def lock_user(user_id):
    """Lock a user account."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    user.is_active = False
    db.session.commit()
    create_audit_log(
        actor,
        "user.lock",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.post("/users/<int:user_id>/unlock")
@roles_required(Role.MASTER_ADMIN)
def unlock_user(user_id):
    """Unlock a user account."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    user.is_active = True
    db.session.commit()
    create_audit_log(
        actor,
        "user.unlock",
        "user",
        user.id,
        before=before,
        after=user_audit_payload(user),
        commit=True,
    )
    return jsonify(user.to_dict())


@admin_bp.delete("/users/<int:user_id>")
@roles_required(Role.MASTER_ADMIN)
def delete_user(user_id):
    """Delete a user account."""
    actor = current_admin_user()
    user = db.get_or_404(User, user_id)
    before = user_audit_payload(user)
    db.session.delete(user)
    db.session.commit()
    create_audit_log(
        actor,
        "user.delete",
        "user",
        user_id,
        before=before,
        commit=True,
    )
    return "", 204
