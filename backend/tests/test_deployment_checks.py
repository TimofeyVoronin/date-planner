"""Tests for project-specific production configuration checks."""

from django.test import override_settings

from apps.common.checks import check_date_planner_deployment

SECURE_SETTINGS = {
    "SECRET_KEY": "production-test-secret-that-is-not-a-checked-placeholder",
    "DEBUG": False,
    "ALLOWED_HOSTS": ["api.example.com"],
    "CORS_ALLOWED_ORIGINS": ["https://example.com"],
    "CSRF_TRUSTED_ORIGINS": ["https://example.com"],
    "SECURE_SSL_REDIRECT": True,
    "SESSION_COOKIE_SECURE": True,
    "CSRF_COOKIE_SECURE": True,
    "SECURE_HSTS_SECONDS": 3600,
    "REST_FRAMEWORK": {"NUM_PROXIES": 0},
    "SECURE_PROXY_SSL_HEADER": None,
}


def message_ids() -> list[str]:
    """Return identifiers emitted by the Date Planner deployment check."""
    return [message.id for message in check_date_planner_deployment(None)]


@override_settings(**SECURE_SETTINGS)
def test_secure_deployment_configuration_passes_project_checks() -> None:
    assert message_ids() == []


@override_settings(**(SECURE_SETTINGS | {"SECRET_KEY": "dev-only-change-me-before-deploying"}))
def test_deployment_check_rejects_development_secret() -> None:
    assert "date_planner.E001" in message_ids()


@override_settings(**(SECURE_SETTINGS | {"SECRET_KEY": "replace-with-a-long-random-django-secret"}))
def test_deployment_check_rejects_production_example_secret() -> None:
    assert "date_planner.E001" in message_ids()


@override_settings(**(SECURE_SETTINGS | {"ALLOWED_HOSTS": ["*"]}))
def test_deployment_check_rejects_wildcard_host() -> None:
    assert "date_planner.E002" in message_ids()


@override_settings(
    **(
        SECURE_SETTINGS
        | {
            "CORS_ALLOWED_ORIGINS": ["http://example.com"],
            "CSRF_TRUSTED_ORIGINS": ["https://example.com"],
        }
    )
)
def test_deployment_check_rejects_insecure_browser_origin() -> None:
    assert "date_planner.E003" in message_ids()


@override_settings(**(SECURE_SETTINGS | {"DEBUG": True}))
def test_deployment_check_rejects_debug_mode() -> None:
    assert "date_planner.E004" in message_ids()


@override_settings(**(SECURE_SETTINGS | {"SECURE_SSL_REDIRECT": False}))
def test_deployment_check_requires_https_redirect() -> None:
    assert "date_planner.E005" in message_ids()


@override_settings(**(SECURE_SETTINGS | {"SESSION_COOKIE_SECURE": False}))
def test_deployment_check_requires_secure_cookies() -> None:
    assert "date_planner.E006" in message_ids()


@override_settings(**(SECURE_SETTINGS | {"SECURE_HSTS_SECONDS": 0}))
def test_deployment_check_requires_initial_hsts() -> None:
    assert "date_planner.E007" in message_ids()


@override_settings(
    **(
        SECURE_SETTINGS
        | {
            "REST_FRAMEWORK": {"NUM_PROXIES": 1},
            "SECURE_PROXY_SSL_HEADER": None,
        }
    )
)
def test_deployment_check_rejects_inconsistent_proxy_trust() -> None:
    assert "date_planner.E008" in message_ids()


@override_settings(
    **(
        SECURE_SETTINGS
        | {
            "REST_FRAMEWORK": {"NUM_PROXIES": 0},
            "SECURE_PROXY_SSL_HEADER": ("HTTP_X_FORWARDED_PROTO", "https"),
        }
    )
)
def test_deployment_check_requires_drf_to_trust_the_same_proxy_chain() -> None:
    assert "date_planner.E008" in message_ids()
