"""
Error-catalog service layer.

All error-entry business logic lives here. Routes should call these functions
and do nothing more than validate input, call the service, and return a response.
"""

import logging

from sqlalchemy import or_

from app.extensions import db
from app.models import Department, ErrorEntry, Machine, Role
from app.services.ai_service import AIServiceError, MockAIProvider, get_ai_provider


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _resolve_machine_id(name):
    """Return the Machine.id for an exact case-insensitive name match, or None."""
    if not name:
        return None
    machine = Machine.query.filter(Machine.name.ilike(name)).first()
    return machine.id if machine else None


# ---------------------------------------------------------------------------
# Visibility / authorization
# ---------------------------------------------------------------------------


def visible_errors_query(user):
    """Return a SQLAlchemy query scoped to error entries visible to the given user.

    MASTER_ADMIN sees all entries. Other roles see only their department.
    """
    query = ErrorEntry.query
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(ErrorEntry.department_id == user.department_id)
    return query


def department_from_payload(data, user):
    """Resolve the target department from request data and enforce ownership.

    Raises PermissionError if a non-admin targets another department.
    Raises ValueError if no valid department can be determined.
    """
    department = None
    if data.get("department_id"):
        department = Department.query.get(data["department_id"])
    elif data.get("department"):
        department = Department.query.filter_by(name=data["department"]).first()
    elif user.department_id:
        department = user.department

    if not department:
        raise ValueError("Valid department_id or department is required")
    if user.role != Role.MASTER_ADMIN and department.id != user.department_id:
        raise PermissionError("Users may only write errors for their own department")
    return department


# ---------------------------------------------------------------------------
# Error-entry CRUD
# ---------------------------------------------------------------------------


def create_error_entry(data, user):
    """Create and persist a new error catalog entry.

    Returns:
        (entry, None, 201)                     on success
        (None, {"error": "..."}, 400/403/500)  on failure
    """
    required = ["machine", "error_code", "title"]
    missing = [field for field in required if not data.get(field)]
    if missing:
        return None, {"error": f"Missing fields: {', '.join(missing)}"}, 400

    try:
        department = department_from_payload(data, user)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    entry = ErrorEntry(
        machine=data["machine"],
        machine_id=_resolve_machine_id(data["machine"]),
        error_code=data["error_code"].upper(),
        title=data["title"],
        description=data.get("description", ""),
        possible_causes=data.get("possible_causes", ""),
        solution=data.get("solution", ""),
        department=department,
    )
    db.session.add(entry)
    db.session.commit()
    return entry, None, 201


def update_error_entry(entry, data, user):
    """Apply a partial update to an error catalog entry.

    Only fields present in *data* are modified; absent keys are left unchanged.

    Returns:
        (entry, None, 200)                     on success
        (None, {"error": "..."}, 400/403/500)  on failure
    """
    try:
        if "department_id" in data or "department" in data:
            entry.department = department_from_payload(data, user)
    except PermissionError as exc:
        return None, {"error": str(exc)}, 403
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    for field in ["machine", "title", "description", "possible_causes", "solution"]:
        if field in data:
            setattr(entry, field, data[field])
    if "machine" in data:
        entry.machine_id = _resolve_machine_id(data["machine"])
    if "error_code" in data:
        entry.error_code = data["error_code"].upper()

    db.session.commit()
    return entry, None, 200


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


def search_errors(query_text, user):
    """Return up to 10 visible error entries matching *query_text*.

    Searches across error_code, machine, title, and description fields.
    Returns an empty list when *query_text* is blank.
    """
    if not query_text:
        return []
    needle = f"%{query_text}%"
    return (
        visible_errors_query(user)
        .filter(or_(
            ErrorEntry.error_code.ilike(needle),
            ErrorEntry.machine.ilike(needle),
            ErrorEntry.title.ilike(needle),
            ErrorEntry.description.ilike(needle),
        ))
        .order_by(ErrorEntry.error_code.asc())
        .limit(10)
        .all()
    )


# ---------------------------------------------------------------------------
# AI features
# ---------------------------------------------------------------------------


def suggest_similar_errors(data, user):
    """Return visible error entries ranked by similarity to a fault description.

    Uses a local token-overlap algorithm — no external AI call required.

    Returns:
        (result_dict, None, 200)               on success
        (None, {"error": "..."}, 400)          on failure
    """
    text = str(data.get("text") or "").strip()
    machine = str(data.get("machine") or "").strip()
    if not text and not machine:
        return None, {"error": "text or machine is required"}, 400
    try:
        limit = parse_similarity_limit(data.get("limit", 5))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    query_text = " ".join([machine, text]).strip()
    candidates = visible_errors_query(user).order_by(ErrorEntry.created_at.desc()).all()
    scored = []
    for entry in candidates:
        score, reasons = similarity_score(query_text, machine, entry)
        if score <= 0:
            continue
        scored.append({
            "entry": entry.to_dict(),
            "score": score,
            "reason": "; ".join(reasons),
        })

    scored.sort(key=lambda item: item["score"], reverse=True)
    return {
        "query": {"text": text, "machine": machine},
        "results": scored[:limit],
        "diagnostics": {"status": "local_answer", "provider": "local_similarity"},
    }, None, 200


def analyze_error_description(data, user):
    """Return a non-persisted AI analysis for a free-text fault description.

    Falls back to the MockAIProvider when the configured provider is unavailable.

    Returns:
        (analysis_dict, None, 200)             on success
        (None, {"error": "..."}, 400)          on failure
    """
    description = str(data.get("description") or "").strip()
    if not description:
        return None, {"error": "description is required"}, 400
    if len(description) > 2000:
        return None, {"error": "description must not exceed 2000 characters"}, 400

    user_context = {
        "role": user.role.value,
        "department": user.department.name if user.department else "",
    }
    try:
        analysis = get_ai_provider().analyze_error(description, user_context)
    except AIServiceError:
        logger.warning(
            "ai_fallback workflow=error_analysis user_id=%s text_length=%s",
            user.id, len(description),
        )
        analysis = MockAIProvider().analyze_error(description, user_context)

    return normalize_error_analysis(analysis, description, user), None, 200


# ---------------------------------------------------------------------------
# Normalization helpers (AI output → stable shape)
# ---------------------------------------------------------------------------


def normalize_error_analysis(analysis, description, user):
    """Validate and normalize an AI error analysis into a stable dict."""
    analysis = analysis or {}
    department_name = analysis.get("department")
    if user.role != Role.MASTER_ADMIN and user.department:
        department_name = user.department.name
    if not Department.query.filter_by(name=department_name).first():
        department_name = user.department.name if user.department else "Instandhaltung"

    return {
        "machine": str(analysis.get("machine") or "Unbekannte Maschine").strip(),
        "title": str(analysis.get("title") or description[:120]).strip()[:160],
        "description": str(analysis.get("description") or description).strip(),
        "possible_causes": str(analysis.get("possible_causes") or "").strip(),
        "solution": str(analysis.get("solution") or "").strip(),
        "department": department_name,
    }


def parse_similarity_limit(value):
    """Parse and validate a similar-error result limit (1–20)."""
    try:
        limit = int(value if value not in (None, "") else 5)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer between 1 and 20") from exc
    if limit < 1 or limit > 20:
        raise ValueError("limit must be an integer between 1 and 20")
    return limit


def similarity_score(query_text, machine, entry):
    """Return a local text similarity score (0–100) and German reason phrases."""
    score = 0
    reasons = []
    query_tokens = tokenize_similarity_text(query_text)
    entry_tokens = tokenize_similarity_text(" ".join([
        entry.machine, entry.error_code, entry.title,
        entry.description, entry.possible_causes, entry.solution,
    ]))
    shared_tokens = query_tokens & entry_tokens
    if shared_tokens:
        token_score = min(60, len(shared_tokens) * 12)
        score += token_score
        reasons.append(f"{len(shared_tokens)} gemeinsame Begriffe")

    if machine and machine.lower() in entry.machine.lower():
        score += 30
        reasons.append("Maschine stimmt ueberein")
    elif machine and entry.machine.lower() in machine.lower():
        score += 20
        reasons.append("Maschine ist aehnlich")

    code_tokens = {t for t in query_tokens if any(c.isdigit() for c in t)}
    if code_tokens & entry_tokens:
        score += 25
        reasons.append("Fehlercode oder Nummer passt")

    return min(score, 100), reasons


def tokenize_similarity_text(value):
    """Return a set of normalized content tokens for local similarity matching.

    Strips German stop-words and tokens shorter than 3 characters.
    """
    stopwords = {
        "der", "die", "das", "und", "oder", "mit", "ein", "eine",
        "ist", "an", "am", "im", "in", "zu", "auf", "von",
        "fehler", "maschine", "anlage",
    }
    tokens = set()
    for raw_token in str(value or "").lower().replace("-", " ").split():
        token = "".join(c for c in raw_token if c.isalnum())
        if len(token) < 3 or token in stopwords:
            continue
        tokens.add(token)
    return tokens
