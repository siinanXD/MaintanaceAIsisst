"""Compatibility exports for shift model templates."""

from app.shiftplans.templates import (
    ShiftTemplate as ShiftModelTemplate,
)
from app.shiftplans.templates import (
    ShiftWindow,
    get_shift_model_template,
    get_shift_template,
    list_shift_model_templates,
    list_shift_templates,
    resolve_shift_model_template,
    resolve_shift_template,
)

__all__ = [
    "ShiftModelTemplate",
    "ShiftWindow",
    "get_shift_model_template",
    "get_shift_template",
    "list_shift_model_templates",
    "list_shift_templates",
    "resolve_shift_model_template",
    "resolve_shift_template",
]
