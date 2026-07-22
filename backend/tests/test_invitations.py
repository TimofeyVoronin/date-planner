"""Tests for creating and retrieving personal invitations."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation

pytestmark = pytest.mark.django_db


def invitation_payload(
    *,
    author_name: str = "Алиса",
    recipient_name: str = "Борис",
    message: str = "Давай сходим на свидание?",
    creation_mode: str | None = None,
) -> dict[str, str]:
    """Build a valid request body with optional field overrides."""
    payload = {
        "author_name": author_name,
        "recipient_name": recipient_name,
        "message": message,
    }
    if creation_mode is not None:
        payload["creation_mode"] = creation_mode
    return payload


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
    assert body["creation_mode"] == invitation.creation_mode == Invitation.CreationMode.QUICK
    assert body["created_at"]
    assert body["updated_at"]
    assert body["response_status"] == Invitation.ResponseStatus.PENDING
    assert body["responded_at"] is None
    assert body["plan_options"] == []
    assert body["selected_option_id"] is None
    assert body["selected_at"] is None
    assert body["confirmed_at"] is None
    assert body["server_now"]
    assert body["management_token"]
    assert "management_token_hash" not in body


def test_create_invitation_persists_explicit_extended_mode() -> None:
    """The extended choice is validated, persisted, and returned by every representation."""
    response = APIClient().post(
        "/api/v1/invitations/",
        invitation_payload(creation_mode=Invitation.CreationMode.EXTENDED),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    invitation = Invitation.objects.get(pk=body["id"])
    assert body["creation_mode"] == Invitation.CreationMode.EXTENDED
    assert invitation.creation_mode == Invitation.CreationMode.EXTENDED

    public_response = APIClient().get(f"/api/v1/invitations/{invitation.pk}/")
    assert public_response.status_code == status.HTTP_200_OK
    assert public_response.json()["creation_mode"] == Invitation.CreationMode.EXTENDED


@pytest.mark.parametrize("creation_mode", ["", "wizard", None])
def test_create_invitation_rejects_invalid_creation_mode(
    creation_mode: str | None,
) -> None:
    """Only the documented quick and extended mode values are accepted."""
    payload: dict[str, object] = invitation_payload()
    payload["creation_mode"] = creation_mode

    response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "creation_mode" in response.json()
    assert Invitation.objects.count() == 0


def test_database_rejects_unknown_creation_mode() -> None:
    """The database constraint protects records created outside the API serializer."""
    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(
            **invitation_payload(),
            creation_mode="wizard",
        )


def test_read_invitation_by_uuid() -> None:
    """A public UUID resolves only its matching invitation."""
    invitation = Invitation.objects.create(**invitation_payload())
    server_now = datetime(2026, 7, 22, 16, 30, tzinfo=UTC)

    with patch("apps.common.serializers.now", return_value=server_now):
        response = APIClient().get(f"/api/v1/invitations/{invitation.pk}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "id": str(invitation.pk),
        **invitation_payload(),
        "creation_mode": Invitation.CreationMode.QUICK,
        "response_status": Invitation.ResponseStatus.PENDING,
        "responded_at": None,
        "plan_options": [],
        "selected_option_id": None,
        "selected_at": None,
        "confirmed_at": None,
        "server_now": server_now.isoformat().replace("+00:00", "Z"),
        "created_at": invitation.created_at.isoformat().replace("+00:00", "Z"),
        "updated_at": invitation.updated_at.isoformat().replace("+00:00", "Z"),
    }


def test_server_now_input_is_ignored_and_never_persisted() -> None:
    """A caller cannot choose the server snapshot or create a model attribute for it."""
    supplied_server_now = "2000-01-01T00:00:00Z"
    actual_server_now = datetime(2026, 7, 22, 16, 45, tzinfo=UTC)
    payload = {
        **invitation_payload(),
        "server_now": supplied_server_now,
    }

    with patch("apps.common.serializers.now", return_value=actual_server_now):
        response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["server_now"] == actual_server_now.isoformat().replace("+00:00", "Z")
    assert response.json()["server_now"] != supplied_server_now
    invitation = Invitation.objects.get(pk=response.json()["id"])
    assert not hasattr(invitation, "server_now")
    assert "server_now" not in {field.name for field in Invitation._meta.get_fields()}


@pytest.mark.parametrize("field", ["author_name", "recipient_name"])
def test_create_invitation_rejects_blank_required_fields(field: str) -> None:
    """Whitespace-only personal fields are rejected with a useful field error."""
    payload = invitation_payload()
    payload[field] = "   "

    response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert field in response.json()
    assert Invitation.objects.count() == 0


@pytest.mark.parametrize("payload_message", [None, "", "   "])
def test_create_invitation_allows_optional_message(payload_message: str | None) -> None:
    """An omitted or blank personal message is normalized to an empty string."""
    payload = invitation_payload()
    if payload_message is None:
        payload.pop("message")
    else:
        payload["message"] = payload_message

    response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_201_CREATED
    assert response.json()["message"] == ""
    assert Invitation.objects.get(pk=response.json()["id"]).message == ""


def test_create_invitation_rejects_null_message() -> None:
    """Optional means omitted or blank, not a database NULL value."""
    payload = invitation_payload()
    payload["message"] = None

    response = APIClient().post("/api/v1/invitations/", payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "message" in response.json()


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
