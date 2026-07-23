"""Tests for capability-protected invitation detail editing."""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation

pytestmark = pytest.mark.django_db


EDITABLE_FIELDS = {
    "author_name",
    "recipient_name",
    "message",
    "creation_mode",
}


def authorization(token: str) -> dict[str, str]:
    """Build the test-client header for a management capability."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def create_invitation(
    client: APIClient,
    *,
    creation_mode: str = Invitation.CreationMode.QUICK,
) -> tuple[Invitation, str]:
    """Create an invitation and return its stored record and management token."""
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
    body = response.json()
    return Invitation.objects.get(pk=body["id"]), body["management_token"]


def management_url(invitation: Invitation) -> str:
    """Return the author-only detail endpoint for one invitation."""
    return f"/api/v1/invitations/{invitation.pk}/manage/"


def test_author_can_partially_update_one_invitation_field() -> None:
    """PATCH changes only supplied editable fields and returns the full record."""
    client = APIClient()
    invitation, token = create_invitation(client)
    original_updated_at = invitation.updated_at

    response = client.patch(
        management_url(invitation),
        {"author_name": "  Анна  "},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["author_name"] == "Анна"
    assert response.json()["recipient_name"] == "Борис"
    assert "management_token" not in response.json()
    assert "management_token_hash" not in response.json()
    assert response["Cache-Control"] == "private, no-store"

    invitation.refresh_from_db()
    assert invitation.author_name == "Анна"
    assert invitation.updated_at > original_updated_at


def test_author_can_update_all_editable_fields_together() -> None:
    """The management endpoint accepts the complete safe edit set."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        management_url(invitation),
        {
            "author_name": "Виктор",
            "recipient_name": "Галина",
            "message": "  Пойдём в театр?  ",
            "creation_mode": Invitation.CreationMode.EXTENDED,
        },
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert {field: response.json()[field] for field in EDITABLE_FIELDS} == {
        "author_name": "Виктор",
        "recipient_name": "Галина",
        "message": "Пойдём в театр?",
        "creation_mode": Invitation.CreationMode.EXTENDED,
    }

    invitation.refresh_from_db()
    assert invitation.creation_mode == Invitation.CreationMode.EXTENDED


def test_empty_patch_is_successful_without_touching_updated_at() -> None:
    """An empty partial update is an idempotent read of the managed record."""
    client = APIClient()
    invitation, token = create_invitation(client)
    original_updated_at = invitation.updated_at

    response = client.patch(
        management_url(invitation),
        {},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    invitation.refresh_from_db()
    assert invitation.updated_at == original_updated_at


def test_repeating_equivalent_values_does_not_touch_updated_at() -> None:
    """Trimmed retries do not create a new database write or timestamp."""
    client = APIClient()
    invitation, token = create_invitation(client)
    original_updated_at = invitation.updated_at

    response = client.patch(
        management_url(invitation),
        {
            "author_name": "  Алиса  ",
            "recipient_name": "Борис",
            "message": "Давай сходим на свидание?",
            "creation_mode": Invitation.CreationMode.QUICK,
        },
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    invitation.refresh_from_db()
    assert invitation.updated_at == original_updated_at


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"author_name": ""}, "author_name"),
        ({"author_name": None}, "author_name"),
        ({"author_name": "A" * 101}, "author_name"),
        ({"recipient_name": " "}, "recipient_name"),
        ({"recipient_name": None}, "recipient_name"),
        ({"recipient_name": "R" * 101}, "recipient_name"),
        ({"message": None}, "message"),
        ({"message": "M" * 1001}, "message"),
        ({"creation_mode": "wizard"}, "creation_mode"),
        ({"creation_mode": None}, "creation_mode"),
    ],
)
def test_management_update_rejects_invalid_editable_values(
    payload: dict[str, object],
    field: str,
) -> None:
    """Management edits reuse the API's name, message and choice constraints."""
    client = APIClient()
    invitation, token = create_invitation(client)
    original_updated_at = invitation.updated_at

    response = client.patch(
        management_url(invitation),
        payload,
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    invitation.refresh_from_db()
    assert invitation.updated_at == original_updated_at


@pytest.mark.parametrize(
    "field",
    [
        "id",
        "publication_status",
        "published_at",
        "response_status",
        "responded_at",
        "management_token",
        "management_token_hash",
        "plan_options",
        "selected_option_id",
        "selected_at",
        "confirmed_at",
        "created_at",
        "updated_at",
        "unexpected_field",
    ],
)
def test_management_update_rejects_lifecycle_and_unknown_fields(field: str) -> None:
    """Fields outside the explicit edit allowlist produce a visible validation error."""
    client = APIClient()
    invitation, token = create_invitation(client)
    original_values = {
        "author_name": invitation.author_name,
        "publication_status": invitation.publication_status,
        "response_status": invitation.response_status,
        "updated_at": invitation.updated_at,
    }

    response = client.patch(
        management_url(invitation),
        {field: "forbidden", "author_name": "Не должно сохраниться"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    invitation.refresh_from_db()
    assert invitation.author_name == original_values["author_name"]
    assert invitation.publication_status == original_values["publication_status"]
    assert invitation.response_status == original_values["response_status"]
    assert invitation.updated_at == original_values["updated_at"]


def test_management_update_requires_authorization_header() -> None:
    """A missing capability cannot edit invitation data."""
    client = APIClient()
    invitation, _ = create_invitation(client)

    response = client.patch(
        management_url(invitation),
        {"author_name": "Новый автор"},
        format="json",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response["WWW-Authenticate"] == "Bearer"
    invitation.refresh_from_db()
    assert invitation.author_name == "Алиса"


def test_management_update_rejects_another_invitation_token() -> None:
    """A capability remains scoped to exactly one invitation."""
    client = APIClient()
    first_invitation, first_token = create_invitation(client)
    second_invitation, _ = create_invitation(client)

    response = client.patch(
        management_url(second_invitation),
        {"author_name": "Чужое изменение"},
        format="json",
        **authorization(first_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    first_invitation.refresh_from_db()
    second_invitation.refresh_from_db()
    assert first_invitation.author_name == "Алиса"
    assert second_invitation.author_name == "Алиса"


def test_management_update_returns_404_for_unknown_uuid() -> None:
    """A valid capability does not turn an unknown UUID into a writable record."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.patch(
        f"/api/v1/invitations/{uuid.uuid4()}/manage/",
        {"author_name": "Новый автор"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_draft_can_be_edited_without_becoming_public() -> None:
    """Editing an extended draft preserves its private publication boundary."""
    client = APIClient()
    invitation, token = create_invitation(
        client,
        creation_mode=Invitation.CreationMode.EXTENDED,
    )

    response = client.patch(
        management_url(invitation),
        {"message": "Настрою остальные экраны позже"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["publication_status"] == Invitation.PublicationStatus.DRAFT
    assert response.json()["published_at"] is None
    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    assert public_response.status_code == status.HTTP_404_NOT_FOUND


def test_published_invitation_exposes_updated_public_copy() -> None:
    """Safe edits to a published invitation are immediately visible to its recipient."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.patch(
        management_url(invitation),
        {
            "recipient_name": "Галина",
            "message": "Пойдём в театр?",
        },
        format="json",
        **authorization(token),
    )
    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")

    assert response.status_code == status.HTTP_200_OK
    assert public_response.status_code == status.HTTP_200_OK
    assert public_response.json()["recipient_name"] == "Галина"
    assert public_response.json()["message"] == "Пойдём в театр?"
    assert "management_token_hash" not in public_response.json()


@pytest.mark.parametrize("method", ["post", "put", "delete"])
def test_management_detail_rejects_unsupported_write_methods(method: str) -> None:
    """PATCH is the only supported write method for invitation details."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = getattr(client, method)(
        management_url(invitation),
        {"author_name": "Новый автор"},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED


def test_openapi_documents_only_the_editable_management_fields() -> None:
    """The PATCH contract is protected and does not advertise lifecycle fields."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    operation = schema["paths"]["/api/v1/invitations/{id}/manage/"]["patch"]
    request_schema = operation["requestBody"]["content"]["application/json"]["schema"]
    component_name = request_schema["$ref"].rsplit("/", maxsplit=1)[-1]
    properties = schema["components"]["schemas"][component_name]["properties"]

    assert operation["security"] == [{"managementToken": []}]
    assert set(properties) == EDITABLE_FIELDS
    assert operation["responses"]["200"]["content"]["application/json"]["schema"]["$ref"].endswith(
        "/Invitation"
    )
