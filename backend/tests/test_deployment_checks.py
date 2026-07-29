"""Tests for project-specific production configuration checks."""

from django.test import override_settings

from apps.common.checks import check_date_planner_deployment

SECURE_SETTINGS = {
    "SECRET_KEY": "production-test-secret-that-is-not-a-checked-placeholder",
    "ALLOWED_HOSTS": ["api.example.com"],
    "CORS_ALLOWED_ORIGINS": ["https://example.com"],
    "CSRF_TRUSTED_ORIGINS": ["https://example.com"],
    "REST_FRAMEWORK": {"NUM_PROXIES": 0},
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


@override_settings(
    **(
        SECURE_SETTINGS
        | {
            "REST_FRAMEWORK": {"NUM_PROXIES": 1},
            "SECURE_PROXY_SSL_HEADER": None,
        }
    )
)
def test_deployment_check_warns_when_proxy_https_is_not_trusted() -> None:
    assert "date_planner.W001" in message_ids()
