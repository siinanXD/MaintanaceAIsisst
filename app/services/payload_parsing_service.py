"""Shared payload parsing helpers for service-layer validation."""


def parse_bool(value, default=True, field_name="is_active", empty_is_default=False):
    """Return a normalized boolean payload value or raise ValueError."""
    if value is None:
        return default
    if empty_is_default and value == "":
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    raise ValueError(f"{field_name} must be a boolean")
