"""
Error assistant service.

Provides structured cause-and-fix lookup from the error catalog based
on free-text machine fault descriptions.

Local implementation
    Uses token-similarity ranking plus exact error-code fallback.
    No external AI call is made in this mode.

Future AI integration hook
    When a non-mock AI provider is configured, ``_try_ai_enhance()``
    calls ``BaseAIProvider.error_assistant_query()``, which can return
    richer causes, fixes, and a plain-language summary.  The service
    merges those into the response and sets ``diagnostics.ai_enhanced``
    to ``True``.  No code change is needed in this file to activate it —
    just configure a real provider via ``OPENAI_API_KEY`` in ``.env``.
"""

import logging
import re

from app.services.error_service import (
    parse_similarity_limit,
    search_errors,
    suggest_similar_errors,
)

logger = logging.getLogger(__name__)

_MAX_QUERY_LENGTH = 1000
_DEFAULT_LIMIT = 5
_MAX_AGGREGATION = 5


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _extract_error_code(text):
    """Return the first probable error code (e.g. E42, F001, 4711) from text."""
    match = re.search(r"\b([A-Z]{0,2}\d{2,5})\b", text.upper())
    return match.group(1) if match else None


def _extract_machine_name(text):
    """Return a machine or plant label extracted from text, or empty string."""
    match = re.search(
        r"(maschine|anlage|machine|unit|linie|presse)\s+[\w-]+",
        text,
        re.IGNORECASE,
    )
    return match.group(0).strip() if match else ""


# ---------------------------------------------------------------------------
# Result aggregation
# ---------------------------------------------------------------------------


def _aggregate_causes_and_fixes(matches):
    """Return deduplicated causes and fixes from a list of scored match dicts."""
    causes = []
    fixes = []
    seen_causes = set()
    seen_fixes = set()

    for match in matches:
        entry = match["entry"]

        cause = (entry.get("possible_causes") or "").strip()
        if cause and cause not in seen_causes:
            causes.append(cause)
            seen_causes.add(cause)

        fix = (entry.get("solution") or "").strip()
        if fix and fix not in seen_fixes:
            fixes.append(fix)
            seen_fixes.add(fix)

    return causes[:_MAX_AGGREGATION], fixes[:_MAX_AGGREGATION]


def _exact_code_fallback(error_code, user, limit):
    """Return scored match dicts from a direct error-code catalog search."""
    if not error_code:
        return []
    entries = search_errors(error_code, user)
    return [
        {
            "entry": entry.to_dict(),
            "score": 50,
            "reason": "Fehlercode direkt gefunden",
        }
        for entry in entries[:limit]
    ]


# ---------------------------------------------------------------------------
# AI enhancement hook
# ---------------------------------------------------------------------------


def _try_ai_enhance(query, matches):
    """Call the configured AI provider for enhanced results, or return None.

    The mock provider always returns None.  A real OpenAI provider returns a
    dict with keys ``causes``, ``fixes``, and optionally ``summary``.
    Any exception from the provider is caught so local results remain valid.
    """
    from app.services.ai_service import get_ai_provider

    try:
        provider = get_ai_provider()
        result = provider.error_assistant_query(query, matches)
        if result and isinstance(result, dict):
            return {
                "causes": result.get("causes", []),
                "fixes": result.get("fixes", []),
                "summary": result.get("summary", ""),
                "provider": provider.name,
            }
        return None
    except Exception:
        logger.debug("error_assistant ai_enhance skipped — provider not available")
        return None


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_error_assistant(data, user):
    """Return cause-and-fix suggestions for a free-text fault query.

    Steps:
      1. Validate and sanitize the query string.
      2. Extract error-code and machine-name signals.
      3. Run similarity-ranked catalog search (department-scoped).
      4. Fall back to exact code search when similarity yields nothing.
      5. Attempt AI enhancement (no-op when mock provider is active).
      6. Aggregate unique causes and fixes from top matches.

    Returns:
        (result_dict, None, 200)              on success
        (None, {"error": "..."}, 400)         on validation failure
    """
    query = str(data.get("query") or "").strip()
    if not query:
        return None, {"error": "query is required"}, 400
    if len(query) > _MAX_QUERY_LENGTH:
        return (
            None,
            {"error": f"query must not exceed {_MAX_QUERY_LENGTH} characters"},
            400,
        )

    try:
        limit = parse_similarity_limit(data.get("limit", _DEFAULT_LIMIT))
    except ValueError as exc:
        return None, {"error": str(exc)}, 400

    error_code = _extract_error_code(query)
    machine_name = _extract_machine_name(query)

    # Primary: token-similarity search across the visible error catalog
    similarity_result, error, status = suggest_similar_errors(
        {"text": query, "machine": machine_name, "limit": limit},
        user,
    )
    if error:
        return None, error, status

    matches = similarity_result["results"]

    # Fallback: exact error-code lookup when similarity returns nothing
    if not matches:
        matches = _exact_code_fallback(error_code, user, limit)

    causes, fixes = _aggregate_causes_and_fixes(matches)

    # AI enhancement path — activated automatically when a real provider is configured
    ai_enhanced = False
    ai_provider_name = "local_similarity"
    ai_result = _try_ai_enhance(query, matches)
    if ai_result:
        causes = ai_result["causes"] or causes
        fixes = ai_result["fixes"] or fixes
        ai_enhanced = True
        ai_provider_name = ai_result.get("provider", "openai")

    diagnostics = {
        "status": "local_search" if not ai_enhanced else "ai_enhanced",
        "provider": ai_provider_name,
        "match_count": len(matches),
        "extracted_error_code": error_code,
        "extracted_machine": machine_name or None,
        "ai_enhanced": ai_enhanced,
    }

    logger.info(
        "error_assistant query_len=%s matches=%s ai_enhanced=%s user_id=%s",
        len(query),
        len(matches),
        ai_enhanced,
        getattr(user, "id", "?"),
    )

    return {
        "query": query,
        "matches": matches,
        "causes": causes,
        "fixes": fixes,
        "diagnostics": diagnostics,
    }, None, 200
