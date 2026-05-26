"""Compatibility facade for knowledge base services."""

from importlib import import_module

from app.services.chunking_service import chunk_text as _default_build_text_chunks

_MODULE_PATHS = (
    "app.services.knowledge_storage_service",
    "app.services.knowledge_indexing_service",
    "app.services.knowledge_metadata_service",
    "app.services.knowledge_retrieval_service",
    "app.services.knowledge_status_service",
    "app.services.knowledge_registry_service",
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


def _build_text_chunks_proxy(*args, **kwargs):
    """Build chunks while honoring facade-level monkeypatches in tests."""
    chunk_builder = globals().get("build_text_chunks", _default_build_text_chunks)
    if chunk_builder is _build_text_chunks_proxy:
        chunk_builder = _default_build_text_chunks
    return chunk_builder(*args, **kwargs)


build_text_chunks = _default_build_text_chunks
__all__.append("build_text_chunks")
for _module in _MODULES:
    _module.build_text_chunks = _build_text_chunks_proxy

if "ALLOWED_KNOWLEDGE_EXTENSIONS" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "ALLOWED_KNOWLEDGE_EXTENSIONS"):
            globals()["ALLOWED_KNOWLEDGE_EXTENSIONS"] = _module.ALLOWED_KNOWLEDGE_EXTENSIONS
            break
if "ALLOWED_KNOWLEDGE_EXTENSIONS" in globals():
    __all__.append("ALLOWED_KNOWLEDGE_EXTENSIONS")
if "MAX_UPLOAD_BYTES" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "MAX_UPLOAD_BYTES"):
            globals()["MAX_UPLOAD_BYTES"] = _module.MAX_UPLOAD_BYTES
            break
if "MAX_UPLOAD_BYTES" in globals():
    __all__.append("MAX_UPLOAD_BYTES")
if "MAX_RETRIEVAL_CHUNKS" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "MAX_RETRIEVAL_CHUNKS"):
            globals()["MAX_RETRIEVAL_CHUNKS"] = _module.MAX_RETRIEVAL_CHUNKS
            break
if "MAX_RETRIEVAL_CHUNKS" in globals():
    __all__.append("MAX_RETRIEVAL_CHUNKS")
if "STRUCTURED_SOURCE_TYPES" not in globals():
    for _module in _MODULES:
        if hasattr(_module, "STRUCTURED_SOURCE_TYPES"):
            globals()["STRUCTURED_SOURCE_TYPES"] = _module.STRUCTURED_SOURCE_TYPES
            break
if "STRUCTURED_SOURCE_TYPES" in globals():
    __all__.append("STRUCTURED_SOURCE_TYPES")

del import_module, _MODULE_PATHS, _MODULES, _module, _name
