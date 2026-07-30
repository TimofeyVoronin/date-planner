"""Project-specific deployment checks."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, Tags, register

INSECURE_SECRET_KEYS = {
    "dev-only-change-me-before-deploying",
    "django-insecure-local-development-only-change-me",
    "replace-with-a-long-random-django-secret",
}
INSECURE_SECRET_KEY_PREFIXES = ("django-insecure-", "replace-with-")
EXPECTED_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


def _secret_key_is_insecure(secret_key: object) -> bool:
    """Recognize placeholders and keys that are too weak for production."""
    if not isinstance(secret_key, str):
        return True
    return (
        secret_key in INSECURE_SECRET_KEYS
        or secret_key.startswith(INSECURE_SECRET_KEY_PREFIXES)
        or len(secret_key) < 50
        or len(set(secret_key)) < 5
    )


def _insecure_origins() -> list[str]:
    origins = [
        *getattr(settings, "CORS_ALLOWED_ORIGINS", []),
        *getattr(settings, "CSRF_TRUSTED_ORIGINS", []),
    ]
    return sorted({origin for origin in origins if urlsplit(origin).scheme.lower() != "https"})


@register(Tags.security, deploy=True)
def check_date_planner_deployment(
    app_configs: object,
    **kwargs: object,
) -> list[Error]:
    """Reject known unsafe production placeholders and transport settings."""
    del app_configs, kwargs
    messages: list[Error] = []

    if _secret_key_is_insecure(settings.SECRET_KEY):
        messages.append(
            Error(
                "DJANGO_SECRET_KEY is a placeholder or is not sufficiently strong.",
                hint="Generate at least 50 random characters and keep the value outside Git.",
                id="date_planner.E001",
            )
        )

    if not settings.ALLOWED_HOSTS or "*" in settings.ALLOWED_HOSTS:
        messages.append(
            Error(
                "DJANGO_ALLOWED_HOSTS must list explicit production host names.",
                hint="Remove '*' and configure every public backend host explicitly.",
                id="date_planner.E002",
            )
        )

    insecure_origins = _insecure_origins()
    if insecure_origins:
        messages.append(
            Error(
                "Production CORS and CSRF origins must use HTTPS.",
                hint=f"Replace insecure origins: {', '.join(insecure_origins)}",
                id="date_planner.E003",
            )
        )

    if settings.DEBUG:
        messages.append(
            Error(
                "DJANGO_DEBUG must be disabled in production.",
                hint="Set DJANGO_DEBUG=False.",
                id="date_planner.E004",
            )
        )

    if not settings.SECURE_SSL_REDIRECT:
        messages.append(
            Error(
                "Production requests must be redirected to HTTPS.",
                hint="Set DJANGO_SECURE_SSL_REDIRECT=True behind the trusted TLS proxy.",
                id="date_planner.E005",
            )
        )

    if not settings.SESSION_COOKIE_SECURE or not settings.CSRF_COOKIE_SECURE:
        messages.append(
            Error(
                "Django session and CSRF cookies must be HTTPS-only in production.",
                hint=("Set DJANGO_SESSION_COOKIE_SECURE=True and DJANGO_CSRF_COOKIE_SECURE=True."),
                id="date_planner.E006",
            )
        )

    if settings.SECURE_HSTS_SECONDS <= 0:
        messages.append(
            Error(
                "Production HSTS must start with a positive max-age.",
                hint=(
                    "Set DJANGO_SECURE_HSTS_SECONDS to a short positive value, verify HTTPS, "
                    "and increase it deliberately."
                ),
                id="date_planner.E007",
            )
        )

    num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES", 0)
    proxy_ssl_header = getattr(settings, "SECURE_PROXY_SSL_HEADER", None)
    if (num_proxies, proxy_ssl_header) not in (
        (0, None),
        (1, EXPECTED_PROXY_SSL_HEADER),
    ):
        messages.append(
            Error(
                "Django and DRF must agree on the trusted reverse-proxy chain.",
                hint=(
                    "For the production Compose topology, set DJANGO_TRUST_PROXY_HEADERS=True "
                    "and DRF_NUM_PROXIES=1 only behind Caddy, which overwrites "
                    "X-Forwarded-Proto and X-Forwarded-For."
                ),
                id="date_planner.E008",
            )
        )

    return messages
