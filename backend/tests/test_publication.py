"""Tests for invitation draft visibility and idempotent publication."""

import uuid
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from django.db import IntegrityError, transaction
from django.utils.timezone import now
from rest_framework import status
from rest_framework.test import APIClient

from apps.common.models import Invitation, InvitationPlanOption

pytestmark = pytest.mark.django_db


def extended_payload() -> dict[str, str]:
    """Build the smallest valid extended invitation request."""
    return {
        "author_name": "Алиса",
        "recipient_name": "Борис",
        "message": "Давай сходим на свидание?",
        "creation_mode": Invitation.CreationMode.EXTENDED,
    }


def create_draft(client: APIClient) -> tuple[Invitation, str]:
    """Create one API draft and return its persisted row and plaintext capability."""
    response = client.post("/api/v1/invitations/", extended_payload(), format="json")
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    return Invitation.objects.get(pk=body["id"]), body["management_token"]


def authorization(token: str) -> dict[str, str]:
    """Build the management Bearer header for the test client."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def publication_path(invitation_id: uuid.UUID) -> str:
    """Return the protected publication endpoint for one invitation."""
    return f"/api/v1/invitations/{invitation_id}/publish/"


def test_extended_creation_returns_private_draft() -> None:
    """Extended invitations are manageable immediately but invisible publicly."""
    client = APIClient()
    invitation, token = create_draft(client)

    assert invitation.publication_status == Invitation.PublicationStatus.DRAFT
    assert invitation.published_at is None

    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    management_response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        **authorization(token),
    )

    assert public_response.status_code == status.HTTP_404_NOT_FOUND
    assert management_response.status_code == status.HTTP_200_OK
    assert management_response.json()["publication_status"] == Invitation.PublicationStatus.DRAFT
    assert management_response.json()["published_at"] is None


def test_publish_draft_sets_timestamp_and_opens_recipient_access() -> None:
    """The author capability makes a draft public at one server-controlled time."""
    client = APIClient()
    invitation, token = create_draft(client)
    published_at = now()

    with patch("apps.common.publication_views.now", return_value=published_at):
        response = client.put(
            publication_path(invitation.pk),
            {},
            format="json",
            **authorization(token),
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["publication_status"] == Invitation.PublicationStatus.PUBLISHED
    assert response.json()["published_at"] == published_at.isoformat().replace("+00:00", "Z")
    assert "management_token" not in response.json()
    assert "management_token_hash" not in response.json()
    assert response["Cache-Control"] == "private, no-store"

    invitation.refresh_from_db()
    assert invitation.publication_status == Invitation.PublicationStatus.PUBLISHED
    assert invitation.published_at == published_at

    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    recipient_response = client.put(
        f"/api/v1/invitations/{invitation.pk}/response/",
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
    )

    assert public_response.status_code == status.HTTP_200_OK
    assert public_response.json()["publication_status"] == Invitation.PublicationStatus.PUBLISHED
    assert recipient_response.status_code == status.HTTP_200_OK
    assert recipient_response.json()["response_status"] == Invitation.ResponseStatus.ACCEPTED


def test_repeated_publish_is_idempotent() -> None:
    """Retrying publication preserves the original publication and update timestamps."""
    client = APIClient()
    invitation, token = create_draft(client)
    first_published_at = now()

    with patch("apps.common.publication_views.now", return_value=first_published_at):
        first_response = client.put(
            publication_path(invitation.pk),
            {},
            format="json",
            **authorization(token),
        )
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at

    with patch("apps.common.publication_views.now") as mocked_now:
        repeated_response = client.put(
            publication_path(invitation.pk),
            {},
            format="json",
            **authorization(token),
        )

    assert first_response.status_code == status.HTTP_200_OK
    assert repeated_response.status_code == status.HTTP_200_OK
    assert repeated_response.json()["published_at"] == first_response.json()["published_at"]
    mocked_now.assert_not_called()

    invitation.refresh_from_db()
    assert invitation.published_at == first_published_at
    assert invitation.updated_at == first_updated_at


def test_publish_requires_matching_management_capability() -> None:
    """Publication cannot be triggered anonymously or with another opaque token."""
    client = APIClient()
    invitation, _ = create_draft(client)

    missing_response = client.put(publication_path(invitation.pk), {}, format="json")
    invalid_response = client.put(
        publication_path(invitation.pk),
        {},
        format="json",
        **authorization("A" * 43),
    )

    assert missing_response.status_code == status.HTTP_401_UNAUTHORIZED
    assert invalid_response.status_code == status.HTTP_403_FORBIDDEN
    invitation.refresh_from_db()
    assert invitation.publication_status == Invitation.PublicationStatus.DRAFT
    assert invitation.published_at is None


def test_publish_unknown_invitation_returns_404() -> None:
    """A valid token cannot publish or reveal an unknown UUID."""
    client = APIClient()
    _, token = create_draft(client)

    response = client.put(
        publication_path(uuid.uuid4()),
        {},
        format="json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.parametrize(
    "payload",
    [
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        {},
    ],
)
def test_draft_recipient_response_endpoint_is_hidden(payload: dict[str, str]) -> None:
    """Draft visibility is checked before recipient-answer payload validation."""
    client = APIClient()
    invitation, _ = create_draft(client)

    response = client.put(
        f"/api/v1/invitations/{invitation.pk}/response/",
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert invitation.author_name not in response.content.decode()
    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.PENDING
    assert invitation.responded_at is None


@pytest.mark.parametrize("use_valid_option", [True, False])
def test_draft_plan_selection_endpoint_is_hidden(use_valid_option: bool) -> None:
    """Draft visibility is checked before recipient-selection payload validation."""
    client = APIClient()
    invitation, _ = create_draft(client)
    responded_at = now()
    Invitation.objects.filter(pk=invitation.pk).update(
        response_status=Invitation.ResponseStatus.ACCEPTED,
        responded_at=responded_at,
    )
    option = InvitationPlanOption.objects.create(
        invitation=invitation,
        starts_at=responded_at + timedelta(days=2),
        place="Кофейня у парка",
        position=0,
    )

    payload = {"option_id": str(option.pk)} if use_valid_option else {}
    response = client.put(
        f"/api/v1/invitations/{invitation.pk}/selection/",
        payload,
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    option.refresh_from_db()
    assert option.selected_at is None


@pytest.mark.parametrize(
    ("publication_status", "published_at"),
    [
        (Invitation.PublicationStatus.DRAFT, now()),
        (Invitation.PublicationStatus.PUBLISHED, None),
    ],
)
def test_database_rejects_inconsistent_publication_state(
    publication_status: str,
    published_at: datetime | None,
) -> None:
    """The database keeps status and publication time in one valid state."""
    with pytest.raises(IntegrityError), transaction.atomic():
        Invitation.objects.create(
            author_name="Алиса",
            recipient_name="Борис",
            publication_status=publication_status,
            published_at=published_at,
        )


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_publication_endpoint_rejects_non_put_methods(method: str) -> None:
    """The publication transition exposes only idempotent PUT and OPTIONS."""
    client = APIClient()
    invitation, token = create_draft(client)

    response = client.generic(
        method,
        publication_path(invitation.pk),
        content_type="application/json",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    invitation.refresh_from_db()
    assert invitation.publication_status == Invitation.PublicationStatus.DRAFT


def test_publication_endpoint_options_advertises_only_put() -> None:
    """Endpoint metadata does not advertise accidental mutation methods."""
    client = APIClient()
    invitation, token = create_draft(client)

    response = client.options(publication_path(invitation.pk), **authorization(token))

    assert response.status_code == status.HTTP_200_OK
    assert {method.strip() for method in response["Allow"].split(",")} == {
        "PUT",
        "OPTIONS",
    }


def test_openapi_documents_protected_bodyless_publication() -> None:
    """The schema publishes the lifecycle endpoint with management security."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    operation = response.json()["paths"]["/api/v1/invitations/{id}/publish/"]["put"]
    assert operation["security"] == [{"managementToken": []}]
    assert "requestBody" not in operation
    assert "200" in operation["responses"]
