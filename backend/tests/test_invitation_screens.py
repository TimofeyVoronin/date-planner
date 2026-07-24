"""Tests for the protected extended-invitation screen configuration set."""

import importlib
import uuid

import pytest
from django.apps import apps as django_apps
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation, InvitationScreen
from apps.common.screens import (
    DEFAULT_INVITATION_SCREEN_CONFIGS,
    INVITATION_SCREEN_TYPE_ORDER,
    ensure_default_invitation_screens,
)

pytestmark = pytest.mark.django_db

SCREEN_RESPONSE_FIELDS = {
    "screen_type",
    "title",
    "subtitle",
    "button_text",
    "image_key",
}


def create_invitation(
    client: APIClient,
    *,
    creation_mode: str = Invitation.CreationMode.EXTENDED,
) -> tuple[Invitation, str]:
    """Create one invitation through the public API and return its capability."""
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


def screen_url(invitation: Invitation) -> str:
    """Return the protected screen collection URL."""
    return f"/api/v1/invitations/{invitation.pk}/screens/"


def authorization(token: str) -> dict[str, str]:
    """Build a valid Bearer authorization header for APIClient."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def test_extended_invitation_creation_builds_complete_default_screen_set() -> None:
    """Every new extended invitation starts with one configuration per flow screen."""
    invitation, _ = create_invitation(APIClient())

    screens = list(invitation.screens.order_by("created_at"))
    assert len(screens) == len(INVITATION_SCREEN_TYPE_ORDER)
    assert {screen.screen_type for screen in screens} == set(INVITATION_SCREEN_TYPE_ORDER)

    for screen in screens:
        defaults = DEFAULT_INVITATION_SCREEN_CONFIGS[screen.screen_type]
        assert screen.title == defaults["title"]
        assert screen.subtitle == defaults["subtitle"]
        assert screen.button_text == defaults["button_text"]
        assert screen.image_key == defaults["image_key"]


def test_quick_invitation_does_not_create_screen_configurations() -> None:
    """The compact flow does not allocate unused builder screen rows."""
    invitation, _ = create_invitation(
        APIClient(),
        creation_mode=Invitation.CreationMode.QUICK,
    )

    assert invitation.screens.count() == 0


def test_switching_to_extended_mode_creates_missing_screens_once() -> None:
    """A managed mode change initializes the builder without producing duplicates."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.QUICK,
    )

    first_response = client.patch(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        {"creation_mode": Invitation.CreationMode.EXTENDED},
        format="json",
        **authorization(token),
    )
    second_response = client.patch(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        {"creation_mode": Invitation.CreationMode.EXTENDED},
        format="json",
        **authorization(token),
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert invitation.screens.count() == len(INVITATION_SCREEN_TYPE_ORDER)


def test_ensure_defaults_restores_only_missing_screen_types() -> None:
    """The initializer is idempotent and preserves an existing customized record."""
    invitation, _ = create_invitation(APIClient())
    acceptance = invitation.screens.get(
        screen_type=InvitationScreen.ScreenType.ACCEPTANCE,
    )
    invitation_screen = invitation.screens.get(
        screen_type=InvitationScreen.ScreenType.INVITATION,
    )
    acceptance.delete()
    invitation_screen.title = "Мой собственный вопрос"
    invitation_screen.save(update_fields=("title", "updated_at"))

    first_result = ensure_default_invitation_screens(invitation)
    second_result = ensure_default_invitation_screens(invitation)

    assert [screen.screen_type for screen in first_result] == list(INVITATION_SCREEN_TYPE_ORDER)
    assert [screen.screen_type for screen in second_result] == list(INVITATION_SCREEN_TYPE_ORDER)
    assert invitation.screens.count() == len(INVITATION_SCREEN_TYPE_ORDER)
    assert (
        invitation.screens.get(
            screen_type=InvitationScreen.ScreenType.INVITATION,
        ).title
        == "Мой собственный вопрос"
    )


def test_database_rejects_duplicate_invitation_screen_type() -> None:
    """One invitation cannot own two configurations for the same screen."""
    invitation, _ = create_invitation(APIClient())

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationScreen.objects.create(
            invitation=invitation,
            screen_type=InvitationScreen.ScreenType.INVITATION,
            title="Дубликат",
        )


def test_database_rejects_unknown_screen_type() -> None:
    """The database protects records created outside the serializer choices."""
    invitation, _ = create_invitation(APIClient())

    with pytest.raises(IntegrityError), transaction.atomic():
        InvitationScreen.objects.create(
            invitation=invitation,
            screen_type="unknown_screen",
            title="Неизвестный экран",
        )


def test_screen_endpoint_returns_stable_order_and_safe_fields() -> None:
    """The builder receives all configurations in recipient-flow order."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.get(screen_url(invitation), **authorization(token))

    assert response.status_code == status.HTTP_200_OK
    assert response["Cache-Control"] == "private, no-store"
    body = response.json()
    assert [screen["screen_type"] for screen in body] == list(INVITATION_SCREEN_TYPE_ORDER)
    assert all(set(screen) == SCREEN_RESPONSE_FIELDS for screen in body)
    assert all("id" not in screen and "updated_at" not in screen for screen in body)


def test_published_extended_invitation_keeps_screen_configuration_readable() -> None:
    """Publication closes editing later but does not discard the configured flow."""
    client = APIClient()
    invitation, token = create_invitation(client)
    publication_response = client.put(
        f"/api/v1/invitations/{invitation.pk}/publish/",
        **authorization(token),
    )

    response = client.get(screen_url(invitation), **authorization(token))

    assert publication_response.status_code == status.HTTP_200_OK
    assert response.status_code == status.HTTP_200_OK
    assert len(response.json()) == len(INVITATION_SCREEN_TYPE_ORDER)


def test_screen_endpoint_rejects_quick_invitation() -> None:
    """A quick invitation has no screen configuration contract to return."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.QUICK,
    )

    response = client.get(screen_url(invitation), **authorization(token))

    assert response.status_code == status.HTTP_409_CONFLICT
    assert "extended" in response.json()["detail"]


def test_screen_endpoint_requires_management_token() -> None:
    """Screen configuration is not readable through the public UUID alone."""
    invitation, _ = create_invitation(APIClient())

    response = APIClient().get(screen_url(invitation))

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response["WWW-Authenticate"] == "Bearer"


def test_screen_endpoint_rejects_another_invitation_token() -> None:
    """A management capability remains scoped to its own screen set."""
    client = APIClient()
    _, first_token = create_invitation(client)
    second_invitation, _ = create_invitation(client)

    response = client.get(
        screen_url(second_invitation),
        **authorization(first_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_screen_endpoint_returns_404_for_unknown_uuid() -> None:
    """A valid capability does not disclose an unknown invitation."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{uuid.uuid4()}/screens/",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
def test_screen_endpoint_rejects_unsupported_methods(method: str) -> None:
    """DPL-201 exposes a protected read contract only."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = getattr(client, method)(
        screen_url(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_screen_data_migration_backfills_only_extended_invitations() -> None:
    """The data migration is safe for existing rows and exact retries."""
    migration = importlib.import_module("apps.common.migrations.0008_invitation_screen_config")
    extended_draft = Invitation.objects.create(
        author_name="Алиса",
        recipient_name="Борис",
        creation_mode=Invitation.CreationMode.EXTENDED,
        publication_status=Invitation.PublicationStatus.DRAFT,
        published_at=None,
    )
    quick_invitation = Invitation.objects.create(
        author_name="Виктор",
        recipient_name="Галина",
    )

    migration.create_missing_extended_invitation_screens(django_apps, None)
    migration.create_missing_extended_invitation_screens(django_apps, None)

    assert extended_draft.screens.count() == len(INVITATION_SCREEN_TYPE_ORDER)
    assert quick_invitation.screens.count() == 0


def test_openapi_documents_protected_screen_collection() -> None:
    """The generated contract describes a read-only management-token endpoint."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    operation = schema["paths"]["/api/v1/invitations/{id}/screens/"]["get"]
    response_schema = operation["responses"]["200"]["content"]["application/json"]["schema"]
    item_component = response_schema["items"]["$ref"].rsplit("/", maxsplit=1)[-1]
    properties = schema["components"]["schemas"][item_component]["properties"]

    assert operation["security"] == [{"managementToken": []}]
    assert response_schema["type"] == "array"
    assert set(properties) == SCREEN_RESPONSE_FIELDS
    assert "patch" not in schema["paths"]["/api/v1/invitations/{id}/screens/"]
