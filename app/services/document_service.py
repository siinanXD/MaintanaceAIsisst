"""Compatibility facade for document services."""

from importlib import import_module

_MODULE_PATHS = (
    "app.services.document_storage_service",
    "app.services.document_review_service",
    "app.services.document_text_service",
    "app.services.document_report_service",
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

del import_module, _MODULE_PATHS, _MODULES, _module, _name
