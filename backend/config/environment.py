"""Strict environment parsing helpers for Django settings."""

import os

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


def env_bool(name: str, default: bool) -> bool:
    """Read one boolean environment variable with predictable validation."""
    value = os.getenv(name)
    if value is None:
        return default

    normalized = value.strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    raise ValueError(f"{name} must be a boolean value")


def env_int(name: str, default: int, *, minimum: int | None = None) -> int:
    """Read one integer environment variable and enforce an optional minimum."""
    raw_value = os.getenv(name)
    value = default if raw_value is None else int(raw_value.strip())
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be greater than or equal to {minimum}")
    return value


def env_list(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment variable without empty entries."""
    return [item.strip() for item in os.getenv(name, default).split(",") if item.strip()]
