"""Application configuration for common endpoints."""

from django.apps import AppConfig


class CommonConfig(AppConfig):
    """Configure the common application."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.common"
    verbose_name = "Common"

    def ready(self) -> None:
        """Register project-specific deployment checks."""
        from apps.common import checks  # noqa: F401
