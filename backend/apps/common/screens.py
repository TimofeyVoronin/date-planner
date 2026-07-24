"""Default configuration and ordering helpers for extended invitation screens."""

from collections.abc import Iterable
from typing import Final, TypedDict

from apps.common.models import Invitation, InvitationScreen


class InvitationScreenDefaults(TypedDict):
    """Fields used when creating one default screen configuration."""

    title: str
    subtitle: str
    button_text: str
    image_key: str


INVITATION_SCREEN_TYPE_ORDER: Final[tuple[str, ...]] = (
    InvitationScreen.ScreenType.INVITATION,
    InvitationScreen.ScreenType.ACCEPTANCE,
    InvitationScreen.ScreenType.DATE_SELECTION,
    InvitationScreen.ScreenType.ACTIVITY_SELECTION,
    InvitationScreen.ScreenType.FINAL,
)

DEFAULT_INVITATION_SCREEN_CONFIGS: Final[dict[str, InvitationScreenDefaults]] = {
    InvitationScreen.ScreenType.INVITATION: {
        "title": "Ты пойдёшь со мной на свидание?",
        "subtitle": "Для тебя приготовили особенное приглашение 💌",
        "button_text": "Да! 😍",
        "image_key": "invitation-default",
    },
    InvitationScreen.ScreenType.ACCEPTANCE: {
        "title": "Ура! 💘",
        "subtitle": "Теперь давай выберем, когда увидимся.",
        "button_text": "Выбрать дату",
        "image_key": "acceptance-default",
    },
    InvitationScreen.ScreenType.DATE_SELECTION: {
        "title": "Когда тебе удобно?",
        "subtitle": "Выбери один из предложенных вариантов даты и времени.",
        "button_text": "Продолжить",
        "image_key": "date-selection-default",
    },
    InvitationScreen.ScreenType.ACTIVITY_SELECTION: {
        "title": "Чем займёмся?",
        "subtitle": "Выбери вариант, который нравится больше всего.",
        "button_text": "Продолжить",
        "image_key": "activity-selection-default",
    },
    InvitationScreen.ScreenType.FINAL: {
        "title": "Договорились 💞",
        "subtitle": "Осталось дождаться итогового подтверждения плана.",
        "button_text": "Посмотреть план",
        "image_key": "final-default",
    },
}


def ensure_default_invitation_screens(invitation: Invitation) -> list[InvitationScreen]:
    """Create only missing defaults for an extended invitation and return all screens."""
    if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
        return []

    screen_queryset = InvitationScreen.objects.filter(invitation_id=invitation.pk)
    existing_types = set(screen_queryset.values_list("screen_type", flat=True))
    missing_screens = [
        InvitationScreen(
            invitation=invitation,
            screen_type=screen_type,
            **DEFAULT_INVITATION_SCREEN_CONFIGS[screen_type],
        )
        for screen_type in INVITATION_SCREEN_TYPE_ORDER
        if screen_type not in existing_types
    ]
    if missing_screens:
        InvitationScreen.objects.bulk_create(missing_screens, ignore_conflicts=True)

    return order_invitation_screens(
        InvitationScreen.objects.filter(invitation_id=invitation.pk),
    )


def order_invitation_screens(
    screens: Iterable[InvitationScreen],
) -> list[InvitationScreen]:
    """Return screen configurations in the stable recipient-flow order."""
    order = {
        screen_type: position for position, screen_type in enumerate(INVITATION_SCREEN_TYPE_ORDER)
    }
    return sorted(screens, key=lambda screen: order[screen.screen_type])
