"""Tests for the fail-closed production environment preflight."""

from collections.abc import Mapping

import pytest

from config.production_environment import (
    collect_production_environment_errors,
    main,
)


def secure_environment() -> dict[str, str]:
    """Return a complete environment containing only non-placeholder values."""
    return {
        "DJANGO_SECRET_KEY": "8p!K4z@W7r#N2v$Q9x%M5c&L1s*J6d-H3f_G0y+T8u=E4a?B7nR5",
        "POSTGRES_PASSWORD": "j6!Fv9@pQ2#zL8$wM4^sX7&k",
        "POSTGRES_DB": "date_planner",
        "POSTGRES_ADMIN_USER": "date_planner_admin",
        "POSTGRES_APP_USER": "date_planner_app",
        "DJANGO_LOG_LEVEL": "INFO",
        "APP_DOMAIN": "dates.company.dev",
        "API_DOMAIN": "api.dates.company.dev",
        "ACME_EMAIL": "operations@company.dev",
        "DJANGO_SECURE_HSTS_SECONDS": "3600",
        "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "False",
        "DJANGO_SECURE_HSTS_PRELOAD": "False",
        "CADDY_HSTS": "max-age=3600",
    }


def errors_for(overrides: Mapping[str, str | None]) -> list[str]:
    """Validate a secure baseline after applying environment overrides."""
    environ = secure_environment()
    for name, value in overrides.items():
        if value is None:
            environ.pop(name, None)
        else:
            environ[name] = value
    return collect_production_environment_errors(environ)


def test_secure_production_environment_passes() -> None:
    """A complete production environment passes without warnings."""
    assert collect_production_environment_errors(secure_environment()) == []


def test_database_admin_and_application_passwords_must_differ() -> None:
    """A leaked runtime credential must not grant administrative access."""
    shared_password = "different-roles-must-not-share-this-password-42!"

    errors = errors_for(
        {
            "POSTGRES_ADMIN_PASSWORD": shared_password,
            "POSTGRES_APP_PASSWORD": shared_password,
        }
    )

    assert "POSTGRES_ADMIN_PASSWORD and POSTGRES_APP_PASSWORD must be different." in errors


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("POSTGRES_DB", "Date-Planner"),
        ("POSTGRES_ADMIN_USER", "admin user"),
        ("POSTGRES_APP_USER", "9runtime"),
    ],
)
def test_postgres_identifiers_use_a_safe_portable_form(name: str, value: str) -> None:
    errors = errors_for({name: value})

    assert any(name in error for error in errors)


def test_database_admin_and_application_users_must_differ() -> None:
    errors = errors_for({"POSTGRES_APP_USER": "date_planner_admin"})

    assert "POSTGRES_ADMIN_USER and POSTGRES_APP_USER must be different." in errors


def test_debug_log_level_is_rejected_in_production() -> None:
    errors = errors_for({"DJANGO_LOG_LEVEL": "DEBUG"})

    assert "DJANGO_LOG_LEVEL must be INFO, WARNING, ERROR, or CRITICAL." in errors


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DJANGO_SECRET_KEY", None),
        ("DJANGO_SECRET_KEY", "django-insecure-placeholder"),
        ("POSTGRES_PASSWORD", None),
        ("POSTGRES_PASSWORD", "replace-with-a-long-random-password"),
        ("POSTGRES_ADMIN_PASSWORD", "short"),
        ("POSTGRES_APP_PASSWORD", "date_planner_dev"),
    ],
)
def test_missing_or_weak_secrets_are_rejected(name: str, value: str | None) -> None:
    """Required and configured optional secrets must be strong."""
    errors = errors_for({name: value})

    assert any(name in error for error in errors)


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("APP_DOMAIN", "https://dates.company.dev"),
        ("APP_DOMAIN", "example.com"),
        ("APP_DOMAIN", "127.0.0.1"),
        ("API_DOMAIN", "api.localhost"),
        ("API_DOMAIN", "api_domain.company.dev"),
    ],
)
def test_non_public_domains_are_rejected(name: str, value: str) -> None:
    """Domains must be plain, non-reserved public DNS host names."""
    errors = errors_for({name: value})

    assert any(name in error for error in errors)


def test_app_and_api_domains_must_be_distinct() -> None:
    """Caddy needs independent host names for its two public sites."""
    errors = errors_for({"API_DOMAIN": "dates.company.dev"})

    assert "APP_DOMAIN and API_DOMAIN must be different DNS host names." in errors


@pytest.mark.parametrize(
    "value",
    [
        "admin@example.com",
        "not-an-email",
        ".admin@company.dev",
        "admin..ops@company.dev",
    ],
)
def test_invalid_or_placeholder_acme_email_is_rejected(value: str) -> None:
    """The certificate contact must be a usable non-placeholder address."""
    errors = errors_for({"ACME_EMAIL": value})

    assert "ACME_EMAIL must be a valid non-placeholder email address." in errors


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("DJANGO_SECURE_HSTS_SECONDS", "0"),
        ("DJANGO_SECURE_HSTS_SECONDS", "03600"),
        ("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", "sometimes"),
        ("DJANGO_SECURE_HSTS_PRELOAD", "sometimes"),
        ("CADDY_HSTS", "max-age=0"),
        ("CADDY_HSTS", "max-age=3600; report-uri=https://logs.company.dev"),
        ("CADDY_HSTS", "max-age=3600;"),
    ],
)
def test_invalid_hsts_configuration_is_rejected(name: str, value: str) -> None:
    """Malformed or unsafe HSTS values fail before Caddy and Django start."""
    errors = errors_for({name: value})

    assert any(name.split("_SECURE_")[0] in error or "HSTS" in error for error in errors)


def test_django_and_caddy_hsts_policies_must_match() -> None:
    """Both public layers must emit the same gradual HSTS policy."""
    errors = errors_for(
        {
            "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
            "CADDY_HSTS": "max-age=3600",
        }
    )

    assert "Django and Caddy HSTS policies must match exactly." in errors


def test_matching_expanded_hsts_policy_passes() -> None:
    """Subdomains and preload can be enabled only when both layers agree."""
    errors = errors_for(
        {
            "DJANGO_SECURE_HSTS_SECONDS": "31536000",
            "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS": "True",
            "DJANGO_SECURE_HSTS_PRELOAD": "True",
            "CADDY_HSTS": "max-age=31536000; includeSubDomains; preload",
        }
    )

    assert errors == []


def test_preflight_output_never_contains_secret_values(capsys: pytest.CaptureFixture[str]) -> None:
    """Failure output names invalid variables without echoing their values."""
    leaked_value = "replace-with-secret-that-must-not-be-printed"
    environ = secure_environment() | {
        "DJANGO_SECRET_KEY": leaked_value,
        "POSTGRES_PASSWORD": leaked_value,
    }

    exit_code = main(environ)

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "DJANGO_SECRET_KEY" in captured.err
    assert "POSTGRES_PASSWORD" in captured.err
    assert leaked_value not in captured.out
    assert leaked_value not in captured.err
