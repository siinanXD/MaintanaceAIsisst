"""Local text knowledge base for AI retrieval."""

import logging
import re
import uuid
from pathlib import Path

from flask import current_app
from werkzeug.utils import secure_filename

from app.domain_models.common import utc_now
from app.extensions import db
from app.models import GeneratedDocument, KnowledgeChunk, KnowledgeDocument
from app.security import has_dashboard_permission
from app.services.document_service import (
    document_path,
    extract_manual_text,
    html_to_text,
    visible_documents_query,
)

logger = logging.getLogger(__name__)

ALLOWED_KNOWLEDGE_EXTENSIONS = {".pdf", ".txt", ".html", ".htm"}
MAX_UPLOAD_BYTES = 12 * 1024 * 1024
MAX_RETRIEVAL_CHUNKS = 4


def knowledge_folder():
    """Return the configured knowledge storage folder."""
    folder = Path(current_app.config["KNOWLEDGE_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def knowledge_path(document):
    """Return a safe absolute path for a stored knowledge document."""
    base = knowledge_folder().resolve()
    path = (base / document.relative_path).resolve()
    if base != path and base not in path.parents:
        raise ValueError("Knowledge path escapes configured folder")
    return path


def validate_knowledge_upload(file_storage):
    """Return an error tuple when a knowledge upload is invalid."""
    if not file_storage or not file_storage.filename:
        return {"error": "file is required"}, 400
    filename = secure_filename(file_storage.filename)
    if not filename:
        return {"error": "filename is invalid"}, 400
    if Path(filename).suffix.lower() not in ALLOWED_KNOWLEDGE_EXTENSIONS:
        return {"error": "file type is not supported"}, 400
    return None, None


def upload_knowledge_document(file_storage, user, department=""):
    """Persist, extract and index an uploaded knowledge document."""
    error, status = validate_knowledge_upload(file_storage)
    if error:
        return None, error, status

    filename = secure_filename(file_storage.filename)
    raw_content = file_storage.read()
    if not raw_content:
        return None, {"error": "file must not be empty"}, 400
    if len(raw_content) > MAX_UPLOAD_BYTES:
        return None, {"error": "file is too large"}, 400

    relative_path = f"uploads/{uuid.uuid4().hex}_{filename}"
    target_path = knowledge_folder() / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(raw_content)

    document = KnowledgeDocument(
        source_type="upload",
        title=Path(filename).stem[:220] or filename[:220],
        original_filename=filename,
        relative_path=relative_path,
        content_type=file_storage.mimetype or "",
        file_size=len(raw_content),
        department=str(department or "").strip()[:120],
        status="pending",
        is_public=True,
        created_by=user.id,
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.session.add(document)
    db.session.flush()
    index_knowledge_document(document, raw_content=raw_content, filename=filename)
    db.session.commit()
    return document.to_dict(), None, 201


def index_knowledge_document(document, raw_content=None, filename=None):
    """Extract text and rebuild chunks for one knowledge document."""
    try:
        text = extract_knowledge_text(document, raw_content=raw_content, filename=filename)
    except (OSError, ValueError) as exc:
        logger.warning("knowledge_extract_failed document_id=%s", document.id)
        document.status = "error"
        document.error_message = str(exc)[:1000]
        document.chunk_count = 0
        return document

    rebuild_chunks(document, text)
    document.status = "indexed" if document.chunk_count else "no_text"
    document.error_message = "" if document.chunk_count else "Keine Textschicht gefunden."
    document.updated_at = utc_now()
    return document


def extract_knowledge_text(document, raw_content=None, filename=None):
    """Extract searchable text from an uploaded or generated knowledge document."""
    if raw_content is not None:
        text, _status = extract_manual_text(filename or document.original_filename, raw_content)
        return text

    if document.source_type == "generated_document":
        source = db.session.get(GeneratedDocument, document.source_id)
        if not source:
            return ""
        path = document_path(source)
        if not path.exists():
            return ""
        return html_to_text(path.read_text(encoding="utf-8", errors="ignore"))

    path = knowledge_path(document)
    if not path.exists():
        return ""
    text, _status = extract_manual_text(
        document.original_filename or path.name,
        path.read_bytes(),
    )
    return text


def rebuild_chunks(document, text):
    """Replace all chunks for a knowledge document."""
    KnowledgeChunk.query.filter(KnowledgeChunk.document_id == document.id).delete()
    chunks = chunk_text(text)
    for index, chunk in enumerate(chunks):
        db.session.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=index,
                text=chunk,
                token_text=" ".join(sorted(tokens(chunk))),
                created_at=utc_now(),
            )
        )
    document.chunk_count = len(chunks)


def chunk_text(text, max_chars=1400, overlap=160):
    """Split text into stable overlapping chunks."""
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if not cleaned:
        return []
    chunks = []
    start = 0
    while start < len(cleaned):
        end = min(len(cleaned), start + max_chars)
        chunks.append(cleaned[start:end].strip())
        if end == len(cleaned):
            break
        start = max(0, end - overlap)
    return chunks[:80]


def tokens(value):
    """Return normalized searchable tokens."""
    return {
        token
        for token in re.sub(
            r"[^a-zA-Z0-9äöüÄÖÜß-]+",
            " ",
            str(value or "").lower(),
        ).split()
        if len(token) >= 3
    }


def search_knowledge_chunks(query_text, user, limit=MAX_RETRIEVAL_CHUNKS):
    """Return ranked knowledge chunks visible to the given user."""
    query_tokens = tokens(query_text)
    if not query_tokens or not has_dashboard_permission(user, "documents", "view"):
        return []

    chunks = (
        KnowledgeChunk.query.join(KnowledgeDocument)
        .filter(KnowledgeDocument.status == "indexed")
        .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeChunk.chunk_index.asc())
        .limit(300)
        .all()
    )
    ranked = []
    for chunk in chunks:
        document = chunk.document
        if not can_user_read_knowledge_document(user, document):
            continue
        overlap = query_tokens & tokens(chunk.token_text or chunk.text)
        if not overlap:
            continue
        score = len(overlap) * 25
        ranked.append((score, chunk))
    ranked.sort(key=lambda item: (item[0], item[1].document.updated_at), reverse=True)
    return [chunk_payload(chunk, score) for score, chunk in ranked[:limit]]


def can_user_read_knowledge_document(user, document):
    """Return whether a user may use a knowledge document as RAG context."""
    if user.is_admin:
        return True
    if not document.is_public:
        return False
    if document.department and (not user.department or user.department.name != document.department):
        return False
    if document.source_type == "generated_document" and document.source_id:
        return (
            visible_documents_query(user).filter(GeneratedDocument.id == document.source_id).first()
            is not None
        )
    return True


def chunk_payload(chunk, score):
    """Return an internal retrieval payload for one chunk."""
    document = chunk.document
    return {
        "type": "knowledge",
        "id": document.id,
        "chunk_id": chunk.id,
        "title": document.title,
        "module": "knowledge",
        "url": "/admin/ai" if document.source_type == "upload" else "/documents",
        "reason": f"{int(score)} lokale Wissens-Trefferpunkte",
        "score": int(score),
        "context": chunk.text,
    }


def knowledge_sources_for_chat(query_text, user):
    """Return context text and public source records for chat retrieval."""
    chunks = search_knowledge_chunks(query_text, user)
    if not chunks:
        return "", []
    context = "\n\n".join(
        f"Quelle: Wissen #{item['id']} - {item['title']}\n{item['context']}" for item in chunks
    )
    sources = [
        {
            "type": "knowledge",
            "id": item["id"],
            "chunk_id": item["chunk_id"],
            "title": item["title"],
            "module": item["module"],
            "url": item["url"],
            "reason": item["reason"],
            "score": item["score"],
        }
        for item in chunks
    ]
    return context, sources


def list_knowledge_documents(args):
    """Return filtered knowledge documents for admin views."""
    query = KnowledgeDocument.query
    q = str(args.get("q") or "").strip()
    status = str(args.get("status") or "").strip()
    if q:
        pattern = f"%{q}%"
        query = query.filter(
            (KnowledgeDocument.title.ilike(pattern))
            | (KnowledgeDocument.original_filename.ilike(pattern))
            | (KnowledgeDocument.department.ilike(pattern))
        )
    if status:
        query = query.filter(KnowledgeDocument.status == status)
    return query.order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())


def reindex_all_knowledge():
    """Reindex all knowledge documents and generated maintenance documents."""
    ensure_generated_documents_registered()
    documents = KnowledgeDocument.query.order_by(KnowledgeDocument.id.asc()).all()
    for document in documents:
        index_knowledge_document(document)
    db.session.commit()
    return {
        "documents": len(documents),
        "indexed": sum(1 for document in documents if document.status == "indexed"),
        "chunks": sum(document.chunk_count for document in documents),
    }


def ensure_generated_documents_registered():
    """Register generated documents in the knowledge base when missing."""
    documents = GeneratedDocument.query.order_by(GeneratedDocument.id.asc()).all()
    existing = {
        item.source_id
        for item in KnowledgeDocument.query.filter_by(source_type="generated_document").all()
    }
    for document in documents:
        if document.id in existing:
            continue
        db.session.add(
            KnowledgeDocument(
                source_type="generated_document",
                source_id=document.id,
                title=document.title,
                original_filename=Path(document.relative_path).name,
                relative_path=document.relative_path,
                content_type="text/html",
                department=document.department or "",
                status="pending",
                is_public=True,
                created_by=document.created_by,
                created_at=utc_now(),
                updated_at=utc_now(),
            )
        )
    db.session.flush()


def delete_knowledge_document(document):
    """Delete a knowledge document and its stored upload if applicable."""
    if document.source_type == "upload" and document.relative_path:
        try:
            path = knowledge_path(document)
            if path.exists():
                path.unlink()
        except (OSError, ValueError):
            logger.warning("knowledge_file_delete_failed document_id=%s", document.id)
    db.session.delete(document)
    db.session.commit()
