"""Project-specific deployment checks."""

from urllib.parse import urlsplit

from django.conf import settings
from django.core.checks import Error, Tags, Warning, register

INSECURE_SECRET_KEYS = {
    "dev-only-change-me-before-deploying",
    "django-insecure-local-development-only-change-me",
}


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
) -> list[Error | Warning]:
    """Reject known unsafe production placeholders and transport settings."""
    del app_configs, kwargs
    messages: list[Error | Warning] = []

    if settings.SECRET_KEY in INSECURE_SECRET_KEYS:
        messages.append(
            Error(
                "DJANGO_SECRET_KEY still uses a development placeholder.",
                hint="Generate a long random secret and keep it outside the repository.",
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

    num_proxies = settings.REST_FRAMEWORK.get("NUM_PROXIES", 0)
    if num_proxies > 0 and not getattr(settings, "SECURE_PROXY_SSL_HEADER", None):
        messages.append(
            Warning(
                "DRF trusts proxy forwarding but Django is not configured to detect proxy HTTPS.",
                hint=(
                    "Set DJANGO_TRUST_PROXY_HEADERS=True only when the trusted reverse proxy "
                    "overwrites X-Forwarded-Proto."
                ),
                id="date_planner.W001",
            )
        )

    return messages
