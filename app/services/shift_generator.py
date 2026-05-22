"""Compatibility exports for the rule-based shift generator."""

from app.shiftplans.generator import (
    backward_rotation_detected,
    build_local_shift_entries,
    forward_rotation_allowed,
    select_candidate_for_slot,
)

__all__ = [
    "backward_rotation_detected",
    "build_local_shift_entries",
    "forward_rotation_allowed",
    "select_candidate_for_slot",
]
