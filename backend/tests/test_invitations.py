"""Tests for creating and retrieving personal invitations."""

import uuid

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation

pytestmark = pytest.mark.django_db


def invitation_payload(
    *,
    author_name: str = "Алиса",
    recipient_name: str = "Борис",
    message: str = "Давай сходим на свидание?",
) -> dict[str, str]:
    """Build a valid request body with optional field overrides."""
    return {
        "author_name": author_name,
        "recipient_name": recipient_name,
        "message": message,
    }


def test_create_invitation_persists_and_returns_public_fields() -> None:
    """A valid POST creates one invitation with a generated UUID."""
    response = APIClient().post(
        "/api/v1/invitations/",
        invitation_payload(),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    invitation_id = uuid.UUID(body["id"])
    invitation = Invitation.objects.get(pk=invitation_id)
    assert body["author_name"] == invitation.author_name == "Алиса"
    assert body["recipient_name"] == invitation.recipient_name == "Борис"
    assert body["message"] == invitation.message == "Давай сходим на свидание?"
    assert body["created_at"]
    assert body["updated_at"]


def test_read_invitation_by_uuid() -> None:
    """A public UUID resolves only its matching invitation."""
    invitation = Invitation.objects.create(**invitation_payload())

    response = APIClient().get(f"/api/v1/invitations/{invitation.pk}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": str(invitation.pk),
        **invitation_payload(),
        "created_at": invitation.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": invitation.updated_at.isoformat().replace("+00:00", "Z"),
    }


@pytest.mark.parametrize("field", ["author_name", "recipient_name", "message"])
def test_create_invitation_rejects_blank_required_fields(field: str) -> None:
    """Whitespace-only personal fields are rejected with a useful field error."""
    payload = invitation_payload()
    payload[field] = "   "

    response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    assert Invitation.objects.count() == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("author_name", "A" * 101),
        ("recipient_name", "R" * 101),
        ("message", "M" * 1001),
    ],
)
def test_create_invitation_rejects_fields_over_maximum_length(
    field: str,
    value: str,
) -> None:
    """Names and messages cannot exceed their documented storage limits."""
    payload = invitation_payload()
    payload[field] = value

    response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    assert Invitation.objects.count() == 0


def test_read_unknown_invitation_returns_404() -> None:
    """An unknown but valid UUID does not expose another invitation."""
    response = APIClient().get(f"/api/v1/invitations/{uuid.uuid4()}/")

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_anonymous_collection_get_does_not_expose_invitation_list() -> None:
    """The collection route supports creation only, not anonymous listing."""
    Invitation.objects.create(**invitation_payload())

    response = APIClient().get("/api/v1/invitations/")

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert "Алиса" not in response.content.decode()


def test_multiple_people_receive_independent_invitation_records() -> None:
    """Invitations for different author-recipient pairs never overwrite each other."""
    client = APIClient()
    first_response = client.post(
        "/api/v1/invitations/",
        invitation_payload(),
        format="json",
    )
    second_payload = invitation_payload(
        author_name="Виктор",
        recipient_name="Галина",
        message="Пойдём в театр?",
    )
    second_response = client.post(
        "/api/v1/invitations/",
        second_payload,
        format="json",
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    assert first_response.json()["id"] != second_response.json()["id"]
    assert Invitation.objects.count() == 2
    assert Invitation.objects.get(pk=first_response.json()["id"]).recipient_name == "Борис"
    assert Invitation.objects.get(pk=second_response.json()["id"]).recipient_name == "Галина"
