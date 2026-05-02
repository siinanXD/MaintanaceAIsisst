import logging

from sqlalchemy import or_

from app.extensions import db
from app.models import Department, ErrorEntry, Machine, Role
from app.services.ai_service import AIServiceError, MockAIProvider, get_ai_provider


logger = logging.getLogger(__name__)


def _resolve_machine_id(name):
    """Return Machine.id for an exact case-insensitive name match, or None."""
    if not name:
        return None
    machine = Machine.query.filter(Machine.name.ilike(name)).first()
    return machine.id if machine else None


def visible_errors_query(user):
    """Return the query for error entries visible to the user."""
    query = ErrorEntry.query
    if user.role != Role.MASTER_ADMIN:
        query = query.filter(ErrorEntry.department_id == user.department_id)
    return query


def department_from_payload(data, user):
    """Resolve and authorize the department from request data."""
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


def create_error_entry(data, user):
    """Create an error catalog entry."""
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
    """Update an error catalog entry."""
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


def search_errors(query_text, user):
    """Search visible error catalog entries."""
    if not query_text:
        return []
    needle = f"%{query_text}%"
    return (
        visible_errors_query(user)
        .filter(
            or_(
                ErrorEntry.error_code.ilike(needle),
                ErrorEntry.machine.ilike(needle),
                ErrorEntry.title.ilike(needle),
                ErrorEntry.description.ilike(needle),
            )
        )
        .order_by(ErrorEntry.error_code.asc())
        .limit(10)
        .all()
    )


def suggest_similar_errors(data, user):
    """Return visible error entries similar to a free-text fault description."""
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
        scored.append(
            {
                "entry": entry.to_dict(),
                "score": score,
                "reason": "; ".join(reasons),
            }
        )

    scored.sort(key=lambda item: item["score"], reverse=True)
    return {
        "query": {"text": text, "machine": machine},
        "results": scored[:limit],
        "diagnostics": {"status": "local_answer", "provider": "local_similarity"},
    }, None, 200


def parse_similarity_limit(value):
    """Parse and validate a similar-error result limit."""
    try:
        limit = int(value if value not in (None, "") else 5)
    except (TypeError, ValueError) as exc:
        raise ValueError("limit must be an integer between 1 and 20") from exc
    if limit < 1 or limit > 20:
        raise ValueError("limit must be an integer between 1 and 20")
    return limit


def similarity_score(query_text, machine, entry):
    """Return a simple text similarity score and German reasons."""
    score = 0
    reasons = []
    query_tokens = tokenize_similarity_text(query_text)
    entry_tokens = tokenize_similarity_text(
        " ".join(
            [
                entry.machine,
                entry.error_code,
                entry.title,
                entry.description,
                entry.possible_causes,
                entry.solution,
            ]
        )
    )
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

    code_tokens = {
        token
        for token in query_tokens
        if any(character.isdigit() for character in token)
    }
    if code_tokens & entry_tokens:
        score += 25
        reasons.append("Fehlercode oder Nummer passt")

    return min(score, 100), reasons


def tokenize_similarity_text(value):
    """Return normalized content tokens for local similarity matching."""
    stopwords = {
        "der",
        "die",
        "das",
        "und",
        "oder",
        "mit",
        "ein",
        "eine",
        "ist",
        "an",
        "am",
        "im",
        "in",
        "zu",
        "auf",
        "von",
        "fehler",
        "maschine",
        "anlage",
    }
    tokens = set()
    for raw_token in str(value or "").lower().replace("-", " ").split():
        token = "".join(character for character in raw_token if character.isalnum())
        if len(token) < 3 or token in stopwords:
            continue
        tokens.add(token)
    return tokens


def analyze_error_description(data, user):
    """Build a non-persisted AI error analysis from free text."""
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
            user.id,
            len(description),
        )
        analysis = MockAIProvider().analyze_error(description, user_context)

    return normalize_error_analysis(analysis, description, user), None, 200


def normalize_error_analysis(analysis, description, user):
    """Validate and normalize an AI error analysis."""
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
