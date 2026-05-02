"""
Backward-compatible re-exports.

Business logic has moved to app.services.error_service.
Import directly from there in new code.
"""
from app.services.error_service import (  # noqa: F401
    analyze_error_description,
    create_error_entry,
    department_from_payload,
    normalize_error_analysis,
    parse_similarity_limit,
    search_errors,
    similarity_score,
    suggest_similar_errors,
    tokenize_similarity_text,
    update_error_entry,
    visible_errors_query,
)
