"""Tests for author-only invitation management capabilities."""

import base64
import hashlib
import re
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
    """Build a valid invitation request."""
    return {
        "author_name": author_name,
        "recipient_name": recipient_name,
        "message": message,
    }


def create_invitation(client: APIClient) -> tuple[Invitation, str]:
    """Create an invitation and return its stored record and one-time capability."""
    response = client.post("/api/v1/invitations/", invitation_payload(), format="json")
    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    return Invitation.objects.get(pk=body["id"]), body["management_token"]


def authorization(token: str) -> dict[str, str]:
    """Build the test-client header for a management capability."""
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def test_create_returns_high_entropy_token_once_and_stores_only_its_hash() -> None:
    """Creation exposes a 256-bit token while persistence contains only its digest."""
    client = APIClient()

    response = client.post("/api/v1/invitations/", invitation_payload(), format="json")

    assert response.status_code == status.HTTP_201_CREATED
    body = response.json()
    token = body["management_token"]
    padding = "=" * (-len(token) % 4)
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert len(base64.urlsafe_b64decode(token + padding)) == 32

    invitation = Invitation.objects.get(pk=body["id"])
    assert invitation.management_token_hash == hashlib.sha256(token.encode()).hexdigest()
    assert invitation.management_token_hash != token
    assert "management_token_hash" not in body
    assert response["Cache-Control"] == "private, no-store"
    assert response["Pragma"] == "no-cache"

    public_response = client.get(f"/api/v1/invitations/{invitation.pk}/")
    assert public_response.status_code == status.HTTP_200_OK
    assert "management_token" not in public_response.json()
    assert "management_token_hash" not in public_response.json()
    assert public_response["Cache-Control"] == "private, no-store"
    assert public_response["Pragma"] == "no-cache"


def test_valid_management_token_returns_invitation_without_reexposing_token() -> None:
    """The matching Bearer capability can read its author management endpoint."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["id"] == str(invitation.pk)
    assert response.json()["author_name"] == invitation.author_name
    assert "management_token" not in response.json()
    assert "management_token_hash" not in response.json()
    assert response["Cache-Control"] == "private, no-store"
    assert response["Pragma"] == "no-cache"


def test_each_invitation_receives_a_distinct_token_and_hash() -> None:
    """Independent invitations never share their author management capability."""
    client = APIClient()

    first_invitation, first_token = create_invitation(client)
    second_invitation, second_token = create_invitation(client)

    assert first_token != second_token
    assert first_invitation.management_token_hash != second_invitation.management_token_hash


def test_management_endpoint_requires_authorization_header() -> None:
    """Omitting the management capability produces a challenge without data."""
    client = APIClient()
    invitation, _ = create_invitation(client)

    response = client.get(f"/api/v1/invitations/{invitation.pk}/manage/")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response["WWW-Authenticate"] == "Bearer"
    assert response["Cache-Control"] == "private, no-store"
    assert invitation.author_name not in response.content.decode()


@pytest.mark.parametrize(
    "header",
    [
        "Basic credentials",
        "Bearer",
        "Bearer token extra-part",
        "Bearer short",
        f"Bearer {'A' * 44}",
        f"Bearer {'A' * 42}!",
    ],
)
def test_management_endpoint_rejects_malformed_authorization_header(header: str) -> None:
    """Only one opaque value in an HTTP Bearer header is accepted."""
    client = APIClient()
    invitation, _ = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        HTTP_AUTHORIZATION=header,
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response["WWW-Authenticate"] == "Bearer"
    assert invitation.author_name not in response.content.decode()


def test_management_endpoint_rejects_invalid_token() -> None:
    """A well-formed but incorrect capability cannot access invitation data."""
    client = APIClient()
    invitation, _ = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        **authorization("A" * 43),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert invitation.author_name not in response.content.decode()


def test_management_endpoint_accepts_lowercase_bearer_scheme() -> None:
    """HTTP authentication scheme matching is case-insensitive."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        HTTP_AUTHORIZATION=f"bearer {token}",
    )

    assert response.status_code == status.HTTP_200_OK


def test_management_token_in_query_string_is_rejected() -> None:
    """Capabilities are accepted only in headers so URLs cannot leak them."""
    client = APIClient()
    invitation, token = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{invitation.pk}/manage/?management_token={token}",
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response["WWW-Authenticate"] == "Bearer"


def test_legacy_invitation_without_token_hash_cannot_be_managed() -> None:
    """An empty legacy digest must never match any syntactically valid token."""
    invitation = Invitation.objects.create(**invitation_payload())

    response = APIClient().get(
        f"/api/v1/invitations/{invitation.pk}/manage/",
        **authorization("A" * 43),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_management_endpoint_returns_404_for_unknown_uuid() -> None:
    """A valid capability cannot turn an unknown UUID into another record."""
    client = APIClient()
    _, token = create_invitation(client)

    response = client.get(
        f"/api/v1/invitations/{uuid.uuid4()}/manage/",
        **authorization(token),
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND


def test_management_token_cannot_be_used_for_another_invitation() -> None:
    """Capabilities are bound to one invitation and cannot cross record boundaries."""
    client = APIClient()
    _, first_token = create_invitation(client)
    second_response = client.post(
        "/api/v1/invitations/",
        invitation_payload(
            author_name="Виктор",
            recipient_name="Галина",
            message="Пойдём в театр?",
        ),
        format="json",
    )
    second_id = second_response.json()["id"]

    response = client.get(
        f"/api/v1/invitations/{second_id}/manage/",
        **authorization(first_token),
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Галина" not in response.content.decode()


def test_openapi_describes_one_time_response_and_management_bearer_security() -> None:
    """The schema distinguishes creation output and documents the Bearer header."""
    response = APIClient().get("/api/schema/?format=json")

    assert response.status_code == status.HTTP_200_OK
    schema = response.json()
    create_schema = schema["paths"]["/api/v1/invitations/"]["post"]["responses"]["201"]
    create_reference = create_schema["content"]["application/json"]["schema"]["$ref"]
    assert create_reference.endswith("/InvitationCreateResponse")
    assert (
        "management_token"
        in schema["components"]["schemas"]["InvitationCreateResponse"]["properties"]
    )

    manage_operation = schema["paths"]["/api/v1/invitations/{id}/manage/"]["get"]
    assert manage_operation["security"] == [{"managementToken": []}]
    assert schema["components"]["securitySchemes"]["managementToken"] == {
        "type": "http",
        "scheme": "bearer",
        "bearerFormat": "opaque management token",
        "description": "One-time-issued capability for managing one invitation.",
    }
