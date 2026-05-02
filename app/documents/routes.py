import logging
from datetime import date

from flask import Blueprint, jsonify, request, send_file

from app.models import GeneratedDocument
from app.responses import error_response, service_error_response, success_response
from app.security import current_user, dashboard_permission_required
from app.services.document_service import (
    document_path,
    review_document_quality,
    review_uploaded_document,
    visible_documents_query,
)


logger = logging.getLogger(__name__)

documents_bp = Blueprint("documents", __name__)


@documents_bp.get("")
@dashboard_permission_required("documents", "view")
def list_documents():
    """Return generated documents visible to the current user with optional filters."""
    user = current_user()
    query = visible_documents_query(user)

    task_id = request.args.get("task_id", type=int)
    if task_id is not None:
        query = query.filter(GeneratedDocument.task_id == task_id)

    department = request.args.get("department", "").strip()
    if department:
        query = query.filter(GeneratedDocument.department.ilike(f"%{department}%"))

    machine = request.args.get("machine", "").strip()
    if machine:
        query = query.filter(GeneratedDocument.machine.ilike(f"%{machine}%"))

    date_from_raw = request.args.get("date_from", "").strip()
    if date_from_raw:
        try:
            date_from = date.fromisoformat(date_from_raw)
            query = query.filter(GeneratedDocument.created_at >= date_from)
        except ValueError:
            return error_response("date_from must be ISO format (YYYY-MM-DD)", 400)

    date_to_raw = request.args.get("date_to", "").strip()
    if date_to_raw:
        try:
            date_to = date.fromisoformat(date_to_raw)
            query = query.filter(GeneratedDocument.created_at <= date_to)
        except ValueError:
            return error_response("date_to must be ISO format (YYYY-MM-DD)", 400)

    documents = query.order_by(GeneratedDocument.created_at.desc()).all()
    return jsonify([doc.to_dict() for doc in documents])


@documents_bp.get("/<int:document_id>/download")
@dashboard_permission_required("documents", "view")
def download_document(document_id):
    """Serve the generated HTML file for a document."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()

    try:
        path = document_path(document)
    except ValueError:
        logger.warning(
            "document_path_escape document_id=%s path=%s",
            document_id,
            document.relative_path,
        )
        return error_response("Document path is invalid", 400)

    if not path.exists():
        logger.warning("document_file_missing document_id=%s path=%s", document_id, path)
        return error_response("Document file not found on disk", 404)

    download_name = f"maintenance_report_task_{document.task_id}.html"
    return send_file(
        path,
        mimetype="text/html",
        as_attachment=True,
        download_name=download_name,
    )


@documents_bp.post("/check")
@dashboard_permission_required("documents", "view")
def check_uploaded_document():
    """Review an uploaded document file without persisting it."""
    file = request.files.get("file")
    review, error, status = review_uploaded_document(file)
    if error:
        return service_error_response(error, status)
    return success_response(review, status, "Document review completed")


@documents_bp.post("/<int:document_id>/review")
@dashboard_permission_required("documents", "view")
def review_document(document_id):
    """Return a non-persisted quality review for a generated document."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()

    review, error, status = review_document_quality(document)
    if error:
        return service_error_response(error, status)

    return success_response(review, status, "Document review completed")
