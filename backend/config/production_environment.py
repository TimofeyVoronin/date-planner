"""Fail-closed validation for the production environment.

This module intentionally depends only on the Python standard library so it can
run before Django starts and before any database service is initialized.
"""

from __future__ import annotations

import ipaddress
import os
import re
import sys
from collections.abc import Mapping

MINIMUM_DJANGO_SECRET_LENGTH = 50
MINIMUM_DATABASE_PASSWORD_LENGTH = 24
MINIMUM_SECRET_UNIQUE_CHARACTERS = 5

REQUIRED_PASSWORD_VARIABLES = ("POSTGRES_PASSWORD",)
OPTIONAL_PASSWORD_VARIABLES = (
    "POSTGRES_ADMIN_PASSWORD",
    "POSTGRES_APP_PASSWORD",
)
PLACEHOLDER_PREFIXES = (
    "change-me",
    "django-insecure-",
    "example",
    "replace-with-",
)
PLACEHOLDER_VALUES = frozenset(
    {
        "date_planner",
        "date_planner_dev",
        "password",
        "postgres",
        "secret",
    }
)
RESERVED_DOMAINS = frozenset(
    {
        "example.com",
        "example.net",
        "example.org",
        "localhost",
    }
)
RESERVED_DOMAIN_SUFFIXES = (
    ".example",
    ".example.com",
    ".example.net",
    ".example.org",
    ".invalid",
    ".local",
    ".localhost",
    ".test",
)

DNS_LABEL_PATTERN = re.compile(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", re.IGNORECASE)
EMAIL_LOCAL_PATTERN = re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]+", re.IGNORECASE)
POSTGRES_IDENTIFIER_PATTERN = re.compile(r"[a-z_][a-z0-9_]{0,62}")
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})
PRODUCTION_LOG_LEVELS = frozenset({"INFO", "WARNING", "ERROR", "CRITICAL"})


def _required_value(environ: Mapping[str, str], name: str, errors: list[str]) -> str | None:
    value = environ.get(name)
    if value is None or not value.strip():
        errors.append(f"{name} must be set.")
        return None
    if value != value.strip():
        errors.append(f"{name} must not start or end with whitespace.")
        return None
    return value


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.casefold()
    return (
        normalized in PLACEHOLDER_VALUES
        or normalized.startswith(PLACEHOLDER_PREFIXES)
        or "change-me" in normalized
    )


def _secret_is_weak(value: str, minimum_length: int) -> bool:
    return (
        len(value) < minimum_length
        or len(set(value)) < MINIMUM_SECRET_UNIQUE_CHARACTERS
        or _looks_like_placeholder(value)
    )


def _validate_secret(
    environ: Mapping[str, str],
    name: str,
    *,
    minimum_length: int,
    required: bool,
    errors: list[str],
) -> None:
    value = environ.get(name)
    if value is None or not value.strip():
        if required:
            errors.append(f"{name} must be set.")
        return
    if value != value.strip() or _secret_is_weak(value, minimum_length):
        errors.append(
            f"{name} must be a non-placeholder secret of at least {minimum_length} characters."
        )


def _is_public_dns_name(value: str) -> bool:
    if len(value) > 253 or value.endswith(".") or "://" in value:
        return False
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        return False

    labels = value.split(".")
    if len(labels) < 2 or any(not DNS_LABEL_PATTERN.fullmatch(label) for label in labels):
        return False

    normalized = value.casefold()
    return normalized not in RESERVED_DOMAINS and not normalized.endswith(RESERVED_DOMAIN_SUFFIXES)


def _validate_domain(
    environ: Mapping[str, str],
    name: str,
    errors: list[str],
) -> str | None:
    value = _required_value(environ, name, errors)
    if value is None:
        return None
    if not _is_public_dns_name(value):
        errors.append(f"{name} must be a non-placeholder public DNS host name.")
        return None
    return value.casefold()


def _validate_postgres_identifiers(
    environ: Mapping[str, str],
    errors: list[str],
) -> None:
    values: dict[str, str] = {}
    for name in ("POSTGRES_DB", "POSTGRES_ADMIN_USER", "POSTGRES_APP_USER"):
        value = _required_value(environ, name, errors)
        if value is None:
            continue
        if POSTGRES_IDENTIFIER_PATTERN.fullmatch(value) is None:
            errors.append(
                f"{name} must be a lowercase PostgreSQL identifier of at most 63 characters."
            )
            continue
        values[name] = value

    admin_user = values.get("POSTGRES_ADMIN_USER")
    app_user = values.get("POSTGRES_APP_USER")
    if admin_user is not None and admin_user == app_user:
        errors.append("POSTGRES_ADMIN_USER and POSTGRES_APP_USER must be different.")


def _validate_log_level(environ: Mapping[str, str], errors: list[str]) -> None:
    value = environ.get("DJANGO_LOG_LEVEL", "INFO")
    if value not in PRODUCTION_LOG_LEVELS:
        errors.append("DJANGO_LOG_LEVEL must be INFO, WARNING, ERROR, or CRITICAL.")


def _validate_email(environ: Mapping[str, str], errors: list[str]) -> None:
    value = _required_value(environ, "ACME_EMAIL", errors)
    if value is None:
        return
    if len(value) > 254 or value.count("@") != 1:
        errors.append("ACME_EMAIL must be a valid non-placeholder email address.")
        return

    local_part, domain = value.rsplit("@", maxsplit=1)
    local_part_is_valid = (
        0 < len(local_part) <= 64
        and EMAIL_LOCAL_PATTERN.fullmatch(local_part) is not None
        and not local_part.startswith(".")
        and not local_part.endswith(".")
        and ".." not in local_part
    )
    if not local_part_is_valid or not _is_public_dns_name(domain):
        errors.append("ACME_EMAIL must be a valid non-placeholder email address.")


def _parse_positive_integer(
    environ: Mapping[str, str],
    name: str,
    errors: list[str],
) -> int | None:
    value = _required_value(environ, name, errors)
    if value is None:
        return None
    try:
        parsed = int(value, 10)
    except ValueError:
        parsed = 0
    if parsed <= 0 or str(parsed) != value:
        errors.append(f"{name} must be a positive base-10 integer.")
        return None
    return parsed


def _parse_boolean(
    environ: Mapping[str, str],
    name: str,
    errors: list[str],
) -> bool | None:
    value = environ.get(name, "False")
    normalized = value.strip().casefold()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    errors.append(f"{name} must be an explicit boolean value.")
    return None


def _parse_caddy_hsts(
    environ: Mapping[str, str],
    errors: list[str],
) -> tuple[int, bool, bool] | None:
    value = _required_value(environ, "CADDY_HSTS", errors)
    if value is None:
        return None

    max_age: int | None = None
    include_subdomains = False
    preload = False
    seen_directives: set[str] = set()

    for raw_directive in value.split(";"):
        directive = raw_directive.strip()
        if not directive:
            errors.append("CADDY_HSTS must contain only valid HSTS directives.")
            return None

        name, separator, raw_argument = directive.partition("=")
        normalized_name = name.strip().casefold()
        if normalized_name in seen_directives:
            errors.append("CADDY_HSTS must not contain duplicate directives.")
            return None
        seen_directives.add(normalized_name)

        if normalized_name == "max-age":
            if separator != "=" or not raw_argument.isascii() or not raw_argument.isdecimal():
                errors.append("CADDY_HSTS max-age must be a positive base-10 integer.")
                return None
            max_age = int(raw_argument, 10)
            if max_age <= 0 or str(max_age) != raw_argument:
                errors.append("CADDY_HSTS max-age must be a positive base-10 integer.")
                return None
        elif normalized_name == "includesubdomains" and not separator:
            include_subdomains = True
        elif normalized_name == "preload" and not separator:
            preload = True
        else:
            errors.append("CADDY_HSTS must contain only valid HSTS directives.")
            return None

    if max_age is None:
        errors.append("CADDY_HSTS must include a positive max-age directive.")
        return None
    return max_age, include_subdomains, preload


def _validate_hsts(environ: Mapping[str, str], errors: list[str]) -> None:
    django_max_age = _parse_positive_integer(
        environ,
        "DJANGO_SECURE_HSTS_SECONDS",
        errors,
    )
    django_include_subdomains = _parse_boolean(
        environ,
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
        errors,
    )
    django_preload = _parse_boolean(
        environ,
        "DJANGO_SECURE_HSTS_PRELOAD",
        errors,
    )
    caddy_hsts = _parse_caddy_hsts(environ, errors)

    if (
        django_max_age is None
        or django_include_subdomains is None
        or django_preload is None
        or caddy_hsts is None
    ):
        return

    caddy_max_age, caddy_include_subdomains, caddy_preload = caddy_hsts
    if (
        django_max_age != caddy_max_age
        or django_include_subdomains != caddy_include_subdomains
        or django_preload != caddy_preload
    ):
        errors.append("Django and Caddy HSTS policies must match exactly.")


def collect_production_environment_errors(environ: Mapping[str, str]) -> list[str]:
    """Return privacy-safe validation errors for one production environment."""
    errors: list[str] = []

    _validate_secret(
        environ,
        "DJANGO_SECRET_KEY",
        minimum_length=MINIMUM_DJANGO_SECRET_LENGTH,
        required=True,
        errors=errors,
    )
    for name in REQUIRED_PASSWORD_VARIABLES:
        _validate_secret(
            environ,
            name,
            minimum_length=MINIMUM_DATABASE_PASSWORD_LENGTH,
            required=True,
            errors=errors,
        )
    for name in OPTIONAL_PASSWORD_VARIABLES:
        _validate_secret(
            environ,
            name,
            minimum_length=MINIMUM_DATABASE_PASSWORD_LENGTH,
            required=False,
            errors=errors,
        )
    admin_password = environ.get("POSTGRES_ADMIN_PASSWORD")
    app_password = environ.get("POSTGRES_APP_PASSWORD")
    if admin_password and app_password and admin_password == app_password:
        errors.append("POSTGRES_ADMIN_PASSWORD and POSTGRES_APP_PASSWORD must be different.")

    _validate_postgres_identifiers(environ, errors)
    _validate_log_level(environ, errors)
    app_domain = _validate_domain(environ, "APP_DOMAIN", errors)
    api_domain = _validate_domain(environ, "API_DOMAIN", errors)
    if app_domain is not None and app_domain == api_domain:
        errors.append("APP_DOMAIN and API_DOMAIN must be different DNS host names.")

    _validate_email(environ, errors)
    _validate_hsts(environ, errors)
    return errors


def main(environ: Mapping[str, str] | None = None) -> int:
    """Validate the process environment without printing any configured values."""
    errors = collect_production_environment_errors(os.environ if environ is None else environ)
    if errors:
        print("Production environment validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("Production environment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
