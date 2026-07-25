"""Stable built-in image keys accepted for each invitation screen type."""

from typing import Final

from apps.common.models import InvitationScreen

INVITATION_SCREEN_IMAGE_KEYS: Final[dict[str, frozenset[str]]] = {
    InvitationScreen.ScreenType.INVITATION: frozenset(
        {
            "invitation-default",
            "invitation-starlight",
            "invitation-flowers",
            "invitation-moon",
        }
    ),
    InvitationScreen.ScreenType.ACCEPTANCE: frozenset(
        {
            "acceptance-default",
            "acceptance-balloons",
            "acceptance-fireworks",
            "acceptance-together",
        }
    ),
    InvitationScreen.ScreenType.DATE_SELECTION: frozenset(
        {
            "date-selection-default",
            "date-sunset",
            "date-weekend",
        }
    ),
    InvitationScreen.ScreenType.ACTIVITY_SELECTION: frozenset(
        {
            "activity-selection-default",
            "activity-coffee",
            "activity-movie",
        }
    ),
    InvitationScreen.ScreenType.FINAL: frozenset(
        {
            "final-default",
            "final-toast",
            "final-night",
            "final-route",
        }
    ),
}


def is_invitation_screen_image_compatible(screen_type: str, image_key: str) -> bool:
    """Return whether a stable local image key belongs to the requested screen."""
    return image_key in INVITATION_SCREEN_IMAGE_KEYS.get(screen_type, frozenset())
