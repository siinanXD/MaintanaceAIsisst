"""Compatibility exports for shift planning rules."""

from app.shiftplans.rules import (
    RuleViolation as ShiftRuleViolation,
)
from app.shiftplans.rules import (
    is_work_entry as is_planned_work,
)
from app.shiftplans.rules import (
    parse_shift_time,
    shift_hours,
    validate_candidate_assignment,
    validate_duplicate_assignment,
    validate_machine_qualification,
    validate_max_daily_hours,
    validate_rest_time,
    validate_shift_model_rules,
    validate_vacation_conflict,
    validate_weekly_hours,
)
from app.shiftplans.rules import (
    shift_datetimes as shift_datetimes_for_rule,
)

__all__ = [
    "ShiftRuleViolation",
    "is_planned_work",
    "parse_shift_time",
    "shift_datetimes_for_rule",
    "shift_hours",
    "validate_candidate_assignment",
    "validate_duplicate_assignment",
    "validate_machine_qualification",
    "validate_max_daily_hours",
    "validate_rest_time",
    "validate_shift_model_rules",
    "validate_vacation_conflict",
    "validate_weekly_hours",
]
