"""Tests for protected editing of the primary invitation screen."""

import importlib
import uuid

import pytest
from django.apps import apps as django_apps
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation, InvitationScreen

pytestmark = pytest.mark.django_db

EDITABLE_SCREEN_FIELDS = {
    "title",
    "subtitle",
    "button_text",
    "secondary_button_text",
    "image_key",
}
SCREEN_RESPONSE_FIELDS = {"screen_type", *EDITABLE_SCREEN_FIELDS}


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
    return Invitation.objects.get(pk=response.json()["id"]), response.json()["management_token"]


def update_url(invitation: Invitation) -> str:
    """Return the primary-screen PATCH endpoint for one invitation."""
    return f"/api/v1/invitations/{invitation.pk}/screens/invitation/"


def test_author_can_update_all_primary_screen_fields() -> None:
    """A valid capability may customize the complete first recipient screen."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        update_url(invitation),
        {
            "title": "  Пойдём гулять вечером?  ",
            "subtitle": "  У меня есть маленький сюрприз 💌  ",
            "button_text": "  Конечно  ",
            "secondary_button_text": "  Не сегодня  ",
            "image_key": "invitation-moon",
        },
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Cache-Control"] == "private, no-store"
    assert response.json() == {
        "screen_type": InvitationScreen.ScreenType.INVITATION,
        "title": "Пойдём гулять вечером?",
        "subtitle": "У меня есть маленький сюрприз 💌",
        "button_text": "Конечно",
        "secondary_button_text": "Не сегодня",
        "image_key": "invitation-moon",
    }

    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.INVITATION)
    assert screen.title == "Пойдём гулять вечером?"
    assert screen.secondary_button_text == "Не сегодня"
    assert screen.image_key == "invitation-moon"


def test_partial_screen_update_changes_only_supplied_field() -> None:
    """PATCH leaves omitted screen values untouched."""
    client = APIClient()
    invitation, token = create_invitation(client)
    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.INVITATION)
    original_values = {
        "subtitle": screen.subtitle,
        "button_text": screen.button_text,
        "secondary_button_text": screen.secondary_button_text,
        "image_key": screen.image_key,
    }

    response = client.patch(
        update_url(invitation),
        {"title": "Новый вопрос"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    screen.refresh_from_db()
    assert screen.title == "Новый вопрос"
    for field, value in original_values.items():
        assert getattr(screen, field) == value


@pytest.mark.parametrize(
    ("image_key", "message"),
    [
        ("unknown-image", "built-in image"),
        ("final-default", "belongs to this invitation screen"),
    ],
)
def test_screen_update_rejects_unknown_or_incompatible_image(
    image_key: str,
    message: str,
) -> None:
    """The backend enforces the same stable image catalog as the builder."""
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
        ("secondary_button_text", ""),
        ("secondary_button_text", "x" * 81),
        ("image_key", ""),
    ],
)
def test_screen_update_rejects_invalid_field_values(field: str, value: str) -> None:
    """Text length and required-action constraints are enforced server-side."""
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
    ["screen_type", "invitation", "created_at", "updated_at", "unknown"],
)
def test_screen_update_rejects_unknown_or_server_controlled_fields(field: str) -> None:
    """Ownership, type, timestamps, and unknown values cannot be changed."""
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


def test_empty_and_identical_patch_keep_screen_timestamp_stable() -> None:
    """No-op retries do not write the row or change its update timestamp."""
    client = APIClient()
    invitation, token = create_invitation(client)
    screen = invitation.screens.get(screen_type=InvitationScreen.ScreenType.INVITATION)
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


def test_screen_update_requires_matching_management_capability() -> None:
    """The public UUID alone and a token for another invitation are insufficient."""
    client = APIClient()
    invitation, _ = create_invitation(client)
    _, another_token = create_invitation(client)

    missing_response = client.patch(
        update_url(invitation),
        {"title": "Новый вопрос"},
        format="json",
    )
    wrong_response = client.patch(
        update_url(invitation),
        {"title": "Новый вопрос"},
        format="json",
        **authorization(another_token),
    )

    assert missing_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert wrong_response.status_code == status.HTTP_403_FORBIDDEN


def test_screen_update_returns_404_for_unknown_invitation() -> None:
    """A valid token does not make an unknown UUID discoverable."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.patch(
        f"/api/v1/invitations/{uuid.uuid4()}/screens/invitation/",
        {"title": "Новый вопрос"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_quick_and_published_invitations_are_closed_for_screen_editing() -> None:
    """Only an unpublished extended flow can be customized in the builder."""
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
        {"title": "Новый вопрос"},
        format="json",
        **authorization(quick_token),
    )
    published_response = client.patch(
        update_url(draft),
        {"title": "Новый вопрос"},
        format="json",
        **authorization(draft_token),
    )

    assert publish_response.status_code == status.HTTP_200_OK
    assert quick_response.status_code == status.HTTP_409_CONFLICT
    assert published_response.status_code == status.HTTP_409_CONFLICT


def test_published_public_response_uses_customized_primary_screen() -> None:
    """The recipient receives exactly the screen configuration saved before publication."""
    client = APIClient()
    invitation, token = create_invitation(client)
    update_response = client.patch(
        update_url(invitation),
        {
            "title": "Сходим вместе в кино?",
            "subtitle": "Я уже выбрал хороший фильм.",
            "button_text": "Идём!",
            "secondary_button_text": "Другой раз",
            "image_key": "invitation-starlight",
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
    primary_screen = public_response.json()["screens"][0]
    assert primary_screen == {
        "screen_type": "invitation",
        "title": "Сходим вместе в кино?",
        "subtitle": "Я уже выбрал хороший фильм.",
        "button_text": "Идём!",
        "secondary_button_text": "Другой раз",
        "image_key": "invitation-starlight",
    }


@pytest.mark.parametrize("method", ["get", "post", "put", "delete"])
def test_primary_screen_update_endpoint_rejects_unsupported_methods(method: str) -> None:
    """DPL-203 exposes only PATCH for the primary screen resource."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = getattr(client, method)(
        update_url(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_secondary_button_data_migration_backfills_existing_primary_screens() -> None:
    """The migration gives old primary screens the same default as new drafts."""
    migration = importlib.import_module(
        "apps.common.migrations.0009_invitation_screen_secondary_button_text"
    )
    invitation = Invitation.objects.create(
        author_name="Алиса",
        recipient_name="Борис",
        creation_mode=Invitation.CreationMode.EXTENDED,
        publication_status=Invitation.PublicationStatus.DRAFT,
        published_at=None,
    )
    screen = InvitationScreen.objects.create(
        invitation=invitation,
        screen_type=InvitationScreen.ScreenType.INVITATION,
        title="Вопрос",
        button_text="Да",
        secondary_button_text="",
        image_key="invitation-default",
    )

    migration.backfill_invitation_secondary_button(django_apps, None)
    migration.backfill_invitation_secondary_button(django_apps, None)

    screen.refresh_from_db()
    assert screen.secondary_button_text == "Нет"


def test_openapi_documents_primary_screen_patch_contract() -> None:
    """The schema exposes only editable fields and the full safe response."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    operation = schema["paths"]["/api/v1/invitations/{id}/screens/invitation/"]["patch"]
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
