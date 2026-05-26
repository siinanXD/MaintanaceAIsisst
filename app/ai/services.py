"""Compatibility facade for AI orchestration services."""

from importlib import import_module

from app.services.ai_service import get_ai_provider as _default_get_ai_provider

_MODULE_PATHS = (
    "app.ai.intent",
    "app.ai.context",
    "app.ai.status",
    "app.ai.briefings",
    "app.ai.chat_answers",
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


def _get_ai_provider_proxy():
    """Return the active AI provider, honoring facade-level monkeypatches."""
    provider_factory = globals().get("get_ai_provider", _default_get_ai_provider)
    if provider_factory is _get_ai_provider_proxy:
        provider_factory = _default_get_ai_provider
    return provider_factory()


get_ai_provider = _default_get_ai_provider
__all__.append("get_ai_provider")
for _module in _MODULES:
    _module.get_ai_provider = _get_ai_provider_proxy

if "LAST_OPENAI_ERROR" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "LAST_OPENAI_ERROR"):
            globals()["LAST_OPENAI_ERROR"] = _module.LAST_OPENAI_ERROR
            break
if "LAST_OPENAI_ERROR" in globals():
    __all__.append("LAST_OPENAI_ERROR")
if "OPENAI_PROVIDER" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "OPENAI_PROVIDER"):
            globals()["OPENAI_PROVIDER"] = _module.OPENAI_PROVIDER
            break
if "OPENAI_PROVIDER" in globals():
    __all__.append("OPENAI_PROVIDER")

del import_module, _MODULE_PATHS, _MODULES, _module, _name
