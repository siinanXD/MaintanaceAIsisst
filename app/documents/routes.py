"""Document API routes."""

import logging
from io import BytesIO
from datetime import date

from flask import Blueprint, jsonify, request, send_file

from app.models import GeneratedDocument, MachineManual
from app.responses import error_response, service_error_response, success_response
from app.security import current_user, dashboard_permission_required
from app.services.document_service import (
    analyze_machine_manual,
    approve_document,
    delete_machine_manual,
    document_versions,
    document_path,
    manual_path,
    reject_document,
    render_document_pdf,
    review_document_quality,
    review_uploaded_document,
    submit_document_review,
    summarize_generated_document,
    summarize_machine_manual,
    upload_machine_manual,
    visible_documents_query,
    visible_manuals_query,
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


@documents_bp.get("/<int:document_id>/download.pdf")
@dashboard_permission_required("documents", "view")
def download_document_pdf(document_id):
    """Render and serve a generated maintenance report as a PDF."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()

    pdf_bytes, error, status = render_document_pdf(document)
    if error:
        return service_error_response(error, status)

    return send_file(
        BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"maintenance_report_task_{document.task_id}.pdf",
    )


@documents_bp.get("/<int:document_id>/versions")
@dashboard_permission_required("documents", "view")
def list_document_versions(document_id):
    """Return immutable versions for a generated document."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()
    return success_response(
        [version.to_dict() for version in document_versions(document)],
        message="Document versions loaded",
    )


@documents_bp.post("/<int:document_id>/summarize")
@dashboard_permission_required("documents", "view")
def summarize_document(document_id):
    """Create or update a stored summary for a generated document."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()
    summary, error, status = summarize_generated_document(document)
    if error:
        return service_error_response(error, status)
    return success_response(summary, status, "Document summarized")


@documents_bp.post("/<int:document_id>/submit-review")
@dashboard_permission_required("documents", "write")
def submit_document_review_route(document_id):
    """Submit a generated document for approval."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()
    data = request.get_json(silent=True) or {}
    return success_response(
        submit_document_review(document, user, data.get("comment")).to_dict(),
        message="Document submitted for review",
    )


@documents_bp.post("/<int:document_id>/approve")
@dashboard_permission_required("documents", "write")
def approve_document_route(document_id):
    """Approve a generated document."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()
    data = request.get_json(silent=True) or {}
    return success_response(
        approve_document(document, user, data.get("comment")).to_dict(),
        message="Document approved",
    )


@documents_bp.post("/<int:document_id>/reject")
@dashboard_permission_required("documents", "write")
def reject_document_route(document_id):
    """Reject a generated document."""
    user = current_user()
    document = visible_documents_query(user).filter(
        GeneratedDocument.id == document_id
    ).first_or_404()
    data = request.get_json(silent=True) or {}
    return success_response(
        reject_document(document, user, data.get("comment")).to_dict(),
        message="Document rejected",
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


@documents_bp.post("/manuals")
@dashboard_permission_required("documents", "write")
def upload_manual():
    """Upload and persist a machine manual."""
    data = request.form
    result, error, status = upload_machine_manual(
        request.files.get("file"),
        current_user(),
        machine_id=data.get("machine_id"),
        department=data.get("department"),
    )
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Manual uploaded")


@documents_bp.get("/manuals")
@dashboard_permission_required("documents", "view")
def list_manuals():
    """Return machine manuals visible to the current user."""
    user = current_user()
    query = visible_manuals_query(user)
    machine_id = request.args.get("machine_id", type=int)
    if machine_id is not None:
        query = query.filter(MachineManual.machine_id == machine_id)
    q = request.args.get("q", "").strip()
    if q:
        query = query.filter(
            (MachineManual.title.ilike(f"%{q}%"))
            | (MachineManual.original_filename.ilike(f"%{q}%"))
            | (MachineManual.analysis.ilike(f"%{q}%"))
        )
    manuals = query.order_by(MachineManual.created_at.desc()).all()
    return jsonify([manual.to_dict() for manual in manuals])


@documents_bp.get("/manuals/<int:manual_id>/download")
@dashboard_permission_required("documents", "view")
def download_manual(manual_id):
    """Download a stored machine manual."""
    user = current_user()
    manual = visible_manuals_query(user).filter(MachineManual.id == manual_id).first_or_404()
    try:
        path = manual_path(manual)
    except ValueError:
        return error_response("Manual path is invalid", 400)
    if not path.exists():
        return error_response("Manual file not found on disk", 404)
    return send_file(
        path,
        mimetype=manual.content_type or "application/octet-stream",
        as_attachment=True,
        download_name=manual.original_filename,
    )


@documents_bp.post("/manuals/<int:manual_id>/analyze")
@dashboard_permission_required("documents", "write")
def analyze_manual(manual_id):
    """Analyze a machine manual and persist the result."""
    user = current_user()
    manual = visible_manuals_query(user).filter(MachineManual.id == manual_id).first_or_404()
    result, error, status = analyze_machine_manual(manual)
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Manual analyzed")


@documents_bp.post("/manuals/<int:manual_id>/summarize")
@dashboard_permission_required("documents", "write")
def summarize_manual(manual_id):
    """Summarize a machine manual and persist the result."""
    user = current_user()
    manual = visible_manuals_query(user).filter(MachineManual.id == manual_id).first_or_404()
    result, error, status = summarize_machine_manual(manual)
    if error:
        return service_error_response(error, status)
    return success_response(result, status, "Manual summarized")


@documents_bp.delete("/manuals/<int:manual_id>")
@dashboard_permission_required("documents", "write")
def delete_manual(manual_id):
    """Delete a machine manual when the user is admin or creator."""
    user = current_user()
    manual = visible_manuals_query(user).filter(MachineManual.id == manual_id).first_or_404()
    if not user.is_admin and manual.created_by != user.id:
        return error_response("Forbidden", 403)
    delete_machine_manual(manual)
    return "", 204
