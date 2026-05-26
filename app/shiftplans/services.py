"""Compatibility facade for shift planning services."""

from importlib import import_module

_MODULE_PATHS = (
    "app.shiftplans.input_service",
    "app.shiftplans.validation_service",
    "app.shiftplans.draft_service",
    "app.shiftplans.persistence_service",
    "app.shiftplans.conflict_service",
)
_MODULES = tuple(import_module(path) for path in _MODULE_PATHS)
__all__ = []

for _module in _MODULES:
    for _name in getattr(_module, "__all__", ()):
        globals()[_name] = getattr(_module, _name)
        __all__.append(_name)

for _module in _MODULES:
    for _name in __all__:
        setattr(_module, _name, globals()[_name])
if "SHIFT_WINDOWS" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "SHIFT_WINDOWS"):
            globals()["SHIFT_WINDOWS"] = _module.SHIFT_WINDOWS
            break
if "SHIFT_WINDOWS" in globals():
    __all__.append("SHIFT_WINDOWS")
if "SHIFT_LABELS" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "SHIFT_LABELS"):
            globals()["SHIFT_LABELS"] = _module.SHIFT_LABELS
            break
if "SHIFT_LABELS" in globals():
    __all__.append("SHIFT_LABELS")
if "hours_between" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "hours_between"):
            globals()["hours_between"] = _module.hours_between
            break
if "hours_between" in globals():
    __all__.append("hours_between")
if "parse_date" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "parse_date"):
            globals()["parse_date"] = _module.parse_date
            break
if "parse_date" in globals():
    __all__.append("parse_date")
if "parse_days" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "parse_days"):
            globals()["parse_days"] = _module.parse_days
            break
if "parse_days" in globals():
    __all__.append("parse_days")
if "shift_datetimes" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "shift_datetimes"):
            globals()["shift_datetimes"] = _module.shift_datetimes
            break
if "shift_datetimes" in globals():
    __all__.append("shift_datetimes")

del import_module, _MODULE_PATHS, _MODULES, _module, _name
