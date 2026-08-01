"""Reusable validators for recipient-facing invitation data."""

import unicodedata

from django.core.exceptions import ValidationError


def validate_invitation_name(value: str) -> None:
    """Reject Unicode number characters while preserving international names."""
    if any(unicodedata.category(character).startswith("N") for character in value):
        raise ValidationError(
            "Имя не должно содержать цифры.",
            code="name_contains_digits",
        )
