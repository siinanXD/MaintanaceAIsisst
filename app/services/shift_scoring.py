"""Compatibility exports for shift candidate scoring."""

from app.shiftplans.scoring import (
    CandidateScore,
    explain_selection,
    is_backward_rotation,
    is_forward_rotation,
    score_candidate,
)

__all__ = [
    "CandidateScore",
    "explain_selection",
    "is_backward_rotation",
    "is_forward_rotation",
    "score_candidate",
]
