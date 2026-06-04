"""Handler package for chat answer routing."""

from app.ai.handlers.rag_handler import answer_with_rag, try_general_hybrid_answer
from app.ai.handlers.structured_handler import (
    try_domain_structured_answers,
    try_local_structured_routes,
)

__all__ = [
    "answer_with_rag",
    "try_domain_structured_answers",
    "try_general_hybrid_answer",
    "try_local_structured_routes",
]
