"""Admin API route registrations."""

# ruff: noqa: F401, F403, F405

from app.admin.blueprint import admin_bp
from app.admin.route_helpers import *


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


@admin_bp.get("/ai/retrieval-telemetry")
@roles_required(Role.MASTER_ADMIN)
def ai_retrieval_telemetry():
    """Return retrieval telemetry and quality analytics for administrators."""
    try:
        days, limit = parse_retrieval_telemetry_args(request.args)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(
        retrieval_quality_analytics(days=days, limit=limit),
        message="Retrieval telemetry loaded",
    )


@admin_bp.get("/ai/retrieval-evaluations")
@roles_required(Role.MASTER_ADMIN)
def ai_retrieval_evaluations():
    """Return prompt-safe golden retrieval evaluation history."""
    try:
        limit = parse_retrieval_evaluation_history_args(request.args)
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(
        retrieval_evaluation_history(limit=limit),
        message="Retrieval evaluation history loaded",
    )


@admin_bp.post("/ai/retrieval-evaluations/run")
@roles_required(Role.MASTER_ADMIN)
def ai_run_retrieval_evaluation():
    """Run a bounded prompt-safe golden retrieval evaluation."""
    try:
        payload = request.get_json(silent=True) or {}
        limit = int(payload.get("limit", 20))
    except (TypeError, ValueError):
        return error_response("limit must be an integer between 1 and 50", 400)
    if limit < 1 or limit > 50:
        return error_response("limit must be an integer between 1 and 50", 400)
    result = run_admin_golden_retrieval_evaluation(
        current_admin_user(),
        limit=limit,
    )
    return success_response(result, status_code=201, message="Retrieval evaluation run completed")


@admin_bp.get("/ai/retrieval-debug")
@roles_required(Role.MASTER_ADMIN)
def ai_retrieval_debug():
    """Return prompt-safe retrieval debug records for administrators."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    return success_response(
        retrieval_debug_items(request.args),
        message="Retrieval debug loaded",
    )


@admin_bp.get("/ai/observability")
@roles_required(Role.MASTER_ADMIN)
def ai_observability():
    """Return AI monitoring, quality, retrieval, and debug observability."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    return success_response(
        ai_observability_dashboard(request.args),
        message="AI observability loaded",
    )


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


@admin_bp.get("/ai/knowledge-gaps")
@roles_required(Role.MASTER_ADMIN)
def ai_knowledge_gaps():
    """Return open or historical AI knowledge gaps for administrators."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    try:
        limit, offset = parse_limit_offset(request.args, default_limit=20)
    except ValueError as exc:
        return error_response(str(exc), 400)
    query = list_knowledge_gaps(request.args)
    total = query.count()
    gaps = query.offset(offset).limit(limit).all()
    open_count = KnowledgeGap.query.filter_by(status="open").count()
    return success_response(
        {
            "items": [gap.to_dict() for gap in gaps],
            "open_count": open_count,
            "pagination": {"limit": limit, "offset": offset, "total": total},
        },
        message="Knowledge gaps loaded",
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


@admin_bp.get("/ai/knowledge-network")
@roles_required(Role.MASTER_ADMIN)
def ai_knowledge_network():
    """Return prompt-safe maintenance knowledge network data."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    try:
        result = knowledge_network(request.args, current_admin_user())
    except ValueError as exc:
        return error_response(str(exc), 400)
    return success_response(result, message="Knowledge network loaded")


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


@admin_bp.post("/ai/knowledge/aging/jobs")
@roles_required(Role.MASTER_ADMIN)
def queue_ai_knowledge_aging_job():
    """Queue a background job for knowledge aging review."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    actor = current_admin_user()
    data = request.get_json(silent=True) or {}
    try:
        job = enqueue_knowledge_aging_job(
            dry_run=data.get("dry_run", False),
            limit=data.get("limit"),
            user=actor,
        )
    except ValueError as exc:
        return error_response(str(exc), 400)
    record_event(
        "rag.knowledge_aging_queued",
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


@admin_bp.put("/ai/knowledge/<int:document_id>/quality-status")
@roles_required(Role.MASTER_ADMIN, Role.INSTANDHALTUNG)
def update_ai_knowledge_quality_status(document_id):
    """Update the editorial quality status for one knowledge document."""
    schema_status = database_schema_status()
    if not schema_status["ok"]:
        return jsonify(database_schema_error_payload(schema_status)), 503
    document = db.get_or_404(KnowledgeDocument, document_id)
    actor = current_admin_user()
    data = request.get_json(silent=True) or {}
    result, error, status = change_knowledge_quality_status(
        document,
        data.get("quality_status") or data.get("status"),
        actor,
    )
    if error:
        return service_error_response(error, status)
    record_event(
        "rag.knowledge_quality_status_updated",
        "ai",
        entity_type="knowledge_document",
        entity_id=document_id,
        user=actor,
        source="admin",
        metadata={
            "source_type": document.source_type,
            "quality_status": result.get("quality_status"),
        },
        commit=True,
    )
    return success_response(result, status, "Knowledge quality status updated")


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


__all__ = [
    "ai_summary",
    "ai_retrieval_telemetry",
    "ai_retrieval_evaluations",
    "ai_run_retrieval_evaluation",
    "ai_retrieval_debug",
    "ai_observability",
    "ai_chats",
    "ai_events",
    "ai_knowledge_gaps",
    "ai_training_entries",
    "create_ai_training_entry",
    "update_ai_training_entry",
    "delete_ai_training_entry",
    "upload_ai_knowledge",
    "ai_knowledge",
    "ai_knowledge_status",
    "ai_knowledge_network",
    "admin_background_jobs",
    "queue_ai_knowledge_reindex_job",
    "queue_ai_knowledge_aging_job",
    "reindex_ai_knowledge",
    "reindex_ai_knowledge_document",
    "update_ai_knowledge_quality_status",
    "delete_ai_knowledge",
]
