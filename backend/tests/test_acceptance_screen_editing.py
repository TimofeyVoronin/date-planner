"""Tests for protected editing of the post-acceptance invitation screen."""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation, InvitationScreen

pytestmark = pytest.mark.django_db

EDITABLE_SCREEN_FIELDS = {
    "title",
    "subtitle",
    "button_text",
    "image_key",
}
SCREEN_RESPONSE_FIELDS = {
    "screen_type",
    "title",
    "subtitle",
    "button_text",
    "secondary_button_text",
    "image_key",
}


def authorization(token: str) -> dict[str, str]:
    """Build a Bearer authorization header for the management capability."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def create_invitation(
    client: APIClient,
    *,
    creation_mode: str = Invitation.CreationMode.EXTENDED,
) -> tuple[Invitation, str]:
    """Create an invitation through the public endpoint and return its token."""
    response = client.post(
        "/api/v1/invitations/",
        {
            "author_name": "Алиса",
            "recipient_name": "Борис",
            "message": "Давай сходим на свидание?",
            "creation_mode": creation_mode,
        },
        format="json",
    )
    assert response.status_code == status.HTTP_201_CREATED
    return (
        Invitation.objects.get(pk=response.json()["id"]),
        response.json()["management_token"],
    )


def update_url(invitation: Invitation) -> str:
    """Return the acceptance-screen PATCH endpoint for one invitation."""
    return f"/api/v1/invitations/{invitation.pk}/screens/acceptance/"


def test_author_can_update_acceptance_screen_fields() -> None:
    """A valid capability may customize the complete post-acceptance screen."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {
            "title": "  Ты правда согласился? 💘  ",
            "subtitle": "  Тогда осталось выбрать удобный вариант.  ",
            "button_text": "  Продолжить  ",
            "image_key": "acceptance-fireworks",
        },
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Cache-Control"] == "private, no-store"
    assert response.json() == {
        "screen_type": InvitationScreen.ScreenType.ACCEPTANCE,
        "title": "Ты правда согласился? 💘",
        "subtitle": "Тогда осталось выбрать удобный вариант.",
        "button_text": "Продолжить",
        "secondary_button_text": "",
        "image_key": "acceptance-fireworks",
    }


def test_partial_acceptance_update_keeps_omitted_fields() -> None:
    """PATCH changes only supplied values and preserves the remaining screen."""
    client = APIClient()
    invitation, token = create_invitation(client)
    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.ACCEPTANCE)
    original_values = {
        "subtitle": screen.subtitle,
        "button_text": screen.button_text,
        "secondary_button_text": screen.secondary_button_text,
        "image_key": screen.image_key,
    }

    response = client.patch(
        update_url(invitation),
        {"title": "Новый заголовок"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    screen.refresh_from_db()
    assert screen.title == "Новый заголовок"
    for field, value in original_values.items():
        assert getattr(screen, field) == value


@pytest.mark.parametrize(
    ("image_key", "message"),
    [
        ("unknown-image", "built-in image"),
        ("invitation-default", "belongs to this invitation screen"),
    ],
)
def test_acceptance_update_rejects_unknown_or_incompatible_image(
    image_key: str,
    message: str,
) -> None:
    """The backend accepts only image keys assigned to the acceptance screen."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {"image_key": image_key},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert message in response.json()["image_key"][0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("title", ""),
        ("title", "x" * 161),
        ("subtitle", "x" * 501),
        ("button_text", ""),
        ("button_text", "x" * 81),
        ("image_key", ""),
    ],
)
def test_acceptance_update_rejects_invalid_values(field: str, value: str) -> None:
    """Required actions and model length limits remain server-enforced."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {field: value},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()


@pytest.mark.parametrize(
    "field",
    [
        "secondary_button_text",
        "screen_type",
        "invitation",
        "created_at",
        "updated_at",
        "unknown",
    ],
)
def test_acceptance_update_rejects_noneditable_fields(field: str) -> None:
    """The second screen cannot receive a decline action or internal values."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {field: "forbidden"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()


def test_empty_and_identical_acceptance_patch_keep_timestamp_stable() -> None:
    """No-op retries do not update the screen timestamp."""
    client = APIClient()
    invitation, token = create_invitation(client)
    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.ACCEPTANCE)
    original_updated_at = screen.updated_at

    empty_response = client.patch(
        update_url(invitation),
        {},
        format="json",
        **authorization(token),
    )
    identical_response = client.patch(
        update_url(invitation),
        {"title": screen.title, "image_key": screen.image_key},
        format="json",
        **authorization(token),
    )

    assert empty_response.status_code == status.HTTP_200_OK
    assert identical_response.status_code == status.HTTP_200_OK
    screen.refresh_from_db()
    assert screen.updated_at == original_updated_at


def test_acceptance_update_requires_matching_management_token() -> None:
    """The UUID alone and a token for another invitation are insufficient."""
    client = APIClient()
    invitation, _ = create_invitation(client)
    _, another_token = create_invitation(client)

    missing_response = client.patch(
        update_url(invitation),
        {"title": "Новый заголовок"},
        format="json",
    )
    wrong_response = client.patch(
        update_url(invitation),
        {"title": "Новый заголовок"},
        format="json",
        **authorization(another_token),
    )

    assert missing_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_response.status_code == status.HTTP_403_FORBIDDEN


def test_acceptance_update_returns_404_for_unknown_invitation() -> None:
    """A valid token does not expose an unknown invitation UUID."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.patch(
        f"/api/v1/invitations/{uuid.uuid4()}/screens/acceptance/",
        {"title": "Новый заголовок"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_quick_and_published_invitations_reject_acceptance_editing() -> None:
    """Only an unpublished extended invitation can customize the second screen."""
    client = APIClient()
    quick_invitation, quick_token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.QUICK,
    )
    draft, draft_token = create_invitation(client)
    publish_response = client.put(
        f"/api/v1/invitations/{draft.pk}/publish/",
        **authorization(draft_token),
    )

    quick_response = client.patch(
        update_url(quick_invitation),
        {"title": "Новый заголовок"},
        format="json",
        **authorization(quick_token),
    )
    published_response = client.patch(
        update_url(draft),
        {"title": "Новый заголовок"},
        format="json",
        **authorization(draft_token),
    )

    assert publish_response.status_code == status.HTTP_200_OK
    assert quick_response.status_code == status.HTTP_409_CONFLICT
    assert published_response.status_code == status.HTTP_409_CONFLICT


def test_public_response_uses_customized_acceptance_screen_after_publication() -> None:
    """The recipient receives the second screen saved before publication."""
    client = APIClient()
    invitation, token = create_invitation(client)
    update_response = client.patch(
        update_url(invitation),
        {
            "title": "Ура, договорились!",
            "subtitle": "Теперь выберем подходящее время.",
            "button_text": "К вариантам",
            "image_key": "acceptance-together",
        },
        format="json",
        **authorization(token),
    )
    publish_response = client.put(
        f"/api/v1/invitations/{invitation.pk}/publish/",
        **authorization(token),
    )

    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")

    assert update_response.status_code == status.HTTP_200_OK
    assert publish_response.status_code == status.HTTP_200_OK
    assert public_response.status_code == status.HTTP_200_OK
    acceptance_screen = next(
        screen
        for screen in public_response.json()["screens"]
        if screen["screen_type"] == InvitationScreen.ScreenType.ACCEPTANCE
    )
    assert acceptance_screen == {
        "screen_type": "acceptance",
        "title": "Ура, договорились!",
        "subtitle": "Теперь выберем подходящее время.",
        "button_text": "К вариантам",
        "secondary_button_text": "",
        "image_key": "acceptance-together",
    }


@pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
def test_acceptance_update_endpoint_rejects_unsupported_methods(method: str) -> None:
    """The acceptance screen resource exposes only PATCH."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = getattr(client, method)(
        update_url(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_openapi_documents_acceptance_screen_patch_contract() -> None:
    """The schema excludes the decline button from the second-screen request."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    operation = schema["paths"]["/api/v1/invitations/{id}/screens/acceptance/"]["patch"]
    request_component = operation["requestBody"]["content"]["application/json"]["schema"][
        "$ref"
    ].rsplit("/", maxsplit=1)[-1]
    response_component = operation["responses"]["200"]["content"]["application/json"]["schema"][
        "$ref"
    ].rsplit("/", maxsplit=1)[-1]

    assert operation["security"] == [{"managementToken": []}]
    assert set(schema["components"]["schemas"][request_component]["properties"]) == (
        EDITABLE_SCREEN_FIELDS
    )
    assert set(schema["components"]["schemas"][response_component]["properties"]) == (
        SCREEN_RESPONSE_FIELDS
    )
