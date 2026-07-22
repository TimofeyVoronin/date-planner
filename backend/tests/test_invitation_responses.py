"""Tests for storing and replacing public invitation responses."""

import uuid
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import ScopedRateThrottle

from apps.common.models import Invitation

pytestmark = pytest.mark.django_db


def invitation_payload(
    *,
    author_name: str = "Алиса",
    recipient_name: str = "Борис",
) -> dict[str, str]:
    """Build data for an independent invitation record."""
    return {
        "author_name": author_name,
        "recipient_name": recipient_name,
        "message": "Давай сходим на свидание?",
    }


def response_path(invitation: Invitation) -> str:
    """Return the public answer endpoint for an invitation."""
    return f"/api/v1/invitations/{invitation.pk}/response/"


def api_timestamp(value: datetime) -> str:
    """Format an aware datetime like the DRF JSON renderer."""
    return value.isoformat().replace("+00:00", "Z")


def test_new_invitation_response_is_pending_without_timestamp() -> None:
    """A newly created invitation has not received an answer yet."""
    invitation = Invitation.objects.create(**invitation_payload())

    response = APIClient().get(f"/api/v1/invitations/{invitation.pk}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["response_status"] == Invitation.ResponseStatus.PENDING
    assert response.json()["responded_at"] is None


def test_put_accepts_invitation_and_sets_response_timestamp() -> None:
    """The first explicit answer is persisted and returned publicly."""
    invitation = Invitation.objects.create(**invitation_payload())
    responded_at = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)

    with patch("apps.common.views.now", return_value=responded_at):
        response = APIClient().put(
            response_path(invitation),
            {"response_status": Invitation.ResponseStatus.ACCEPTED},
            format="json",
        )

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["response_status"] == Invitation.ResponseStatus.ACCEPTED
    assert response.json()["responded_at"] == api_timestamp(responded_at)
    assert "management_token" not in response.json()
    assert "management_token_hash" not in response.json()
    assert response["Cache-Control"] == "private, no-store"
    assert response["Pragma"] == "no-cache"

    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.ACCEPTED
    assert invitation.responded_at == responded_at


def test_put_can_change_accepted_response_to_declined() -> None:
    """A recipient can replace an earlier answer and update its timestamp."""
    invitation = Invitation.objects.create(**invitation_payload())
    accepted_at = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    declined_at = datetime(2026, 7, 22, 12, 5, tzinfo=UTC)
    client = APIClient()

    with patch(
        "apps.common.views.now",
        side_effect=(accepted_at, declined_at),
    ):
        accepted_response = client.put(
            response_path(invitation),
            {"response_status": Invitation.ResponseStatus.ACCEPTED},
            format="json",
        )
        declined_response = client.put(
            response_path(invitation),
            {"response_status": Invitation.ResponseStatus.DECLINED},
            format="json",
        )

    assert accepted_response.status_code == status.HTTP_200_OK
    assert declined_response.status_code == status.HTTP_200_OK
    assert declined_response.json()["response_status"] == Invitation.ResponseStatus.DECLINED
    assert declined_response.json()["responded_at"] == api_timestamp(declined_at)

    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.DECLINED
    assert invitation.responded_at == declined_at


def test_repeating_same_put_is_idempotent() -> None:
    """Retrying an identical answer does not change timestamps or write the row."""
    invitation = Invitation.objects.create(**invitation_payload())
    accepted_at = datetime(2026, 7, 22, 12, 0, tzinfo=UTC)
    client = APIClient()

    with patch("apps.common.views.now", return_value=accepted_at):
        first_response = client.put(
            response_path(invitation),
            {"response_status": Invitation.ResponseStatus.ACCEPTED},
            format="json",
        )
    invitation.refresh_from_db()
    first_updated_at = invitation.updated_at

    with patch("apps.common.views.now") as mocked_now:
        repeated_response = client.put(
            response_path(invitation),
            {"response_status": Invitation.ResponseStatus.ACCEPTED},
            format="json",
        )

    assert first_response.status_code == status.HTTP_200_OK
    assert repeated_response.status_code == status.HTTP_200_OK
    assert repeated_response.json()["responded_at"] == api_timestamp(accepted_at)
    mocked_now.assert_not_called()

    invitation.refresh_from_db()
    assert invitation.responded_at == accepted_at
    assert invitation.updated_at == first_updated_at


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"response_status": None},
        {"response_status": "pending"},
        {"response_status": "ACCEPTED"},
        {"response_status": "maybe"},
        {"status": "accepted"},
    ],
)
def test_put_rejects_invalid_response_without_mutation(payload: dict[str, object]) -> None:
    """Only explicit accepted or declined values can leave the pending state."""
    invitation = Invitation.objects.create(**invitation_payload())

    response = APIClient().put(response_path(invitation), payload, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "response_status" in response.json()
    assert response["Cache-Control"] == "private, no-store"
    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.PENDING
    assert invitation.responded_at is None


def test_put_unknown_invitation_returns_404() -> None:
    """A valid answer cannot create or reveal an unknown invitation."""
    response = APIClient().put(
        f"/api/v1/invitations/{uuid.uuid4()}/response/",
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response["Cache-Control"] == "private, no-store"
    assert Invitation.objects.count() == 0


def test_response_updates_only_the_addressed_invitation() -> None:
    """Responses for different people remain isolated database records."""
    first = Invitation.objects.create(**invitation_payload())
    second = Invitation.objects.create(
        **invitation_payload(author_name="Виктор", recipient_name="Галина")
    )

    response = APIClient().put(
        response_path(first),
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    first.refresh_from_db()
    second.refresh_from_db()
    assert first.response_status == Invitation.ResponseStatus.DECLINED
    assert first.responded_at is not None
    assert second.response_status == Invitation.ResponseStatus.PENDING
    assert second.responded_at is None


def test_public_and_management_reads_show_saved_response_without_secrets() -> None:
    """Both reads expose the answer while neither re-exposes its management secret."""
    client = APIClient()
    create_response = client.post(
        "/api/v1/invitations/",
        invitation_payload(),
        format="json",
    )
    invitation_id = create_response.json()["id"]
    management_token = create_response.json()["management_token"]
    put_response = client.put(
        f"/api/v1/invitations/{invitation_id}/response/",
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
    )
    assert put_response.status_code == status.HTTP_200_OK

    public_response = client.get(f"/api/v1/invitations/{invitation_id}/")
    management_response = client.get(
        f"/api/v1/invitations/{invitation_id}/manage/",
        HTTP_AUTHORIZATION=f"Bearer {management_token}",
    )

    for response in (public_response, management_response):
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["response_status"] == Invitation.ResponseStatus.ACCEPTED
        assert response.json()["responded_at"] is not None
        assert "management_token" not in response.json()
        assert "management_token_hash" not in response.json()


@pytest.mark.parametrize("method", ["GET", "POST", "PATCH", "DELETE"])
def test_response_endpoint_rejects_unsupported_methods(method: str) -> None:
    """The response resource exposes only idempotent PUT and metadata OPTIONS."""
    invitation = Invitation.objects.create(**invitation_payload())

    response = APIClient().generic(
        method,
        response_path(invitation),
        data={"response_status": Invitation.ResponseStatus.ACCEPTED},
        content_type="application/json",
    )

    assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
    assert response["Cache-Control"] == "private, no-store"
    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.PENDING


def test_response_endpoint_options_advertises_only_put() -> None:
    """Endpoint metadata lists PUT without accidental mutation methods."""
    invitation = Invitation.objects.create(**invitation_payload())

    response = APIClient().options(response_path(invitation))

    assert response.status_code == status.HTTP_200_OK
    allowed_methods = {method.strip() for method in response["Allow"].split(",")}
    assert allowed_methods == {"PUT", "OPTIONS"}
    assert response["Cache-Control"] == "private, no-store"


def test_response_throttle_returns_retry_after_without_third_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The response-specific limit rejects excess writes with retry guidance."""
    monkeypatch.setitem(
        ScopedRateThrottle.THROTTLE_RATES,
        "invitation_response",
        "2/min",
    )
    invitation = Invitation.objects.create(**invitation_payload())
    client = APIClient()
    client_address = {"REMOTE_ADDR": "192.0.2.30"}

    first_response = client.put(
        response_path(invitation),
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
        **client_address,
    )
    second_response = client.put(
        response_path(invitation),
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
        **client_address,
    )
    throttled_response = client.put(
        response_path(invitation),
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
        **client_address,
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert throttled_response["Cache-Control"] == "private, no-store"
    retry_after = throttled_response.headers.get("Retry-After")
    assert retry_after is not None
    assert 1 <= int(retry_after) <= 60

    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.DECLINED


def test_spoofed_forwarded_for_cannot_bypass_response_throttle(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Untrusted forwarding headers cannot create a new response-limit identity."""
    monkeypatch.setitem(
        ScopedRateThrottle.THROTTLE_RATES,
        "invitation_response",
        "1/min",
    )
    invitation = Invitation.objects.create(**invitation_payload())
    client = APIClient()

    first_response = client.put(
        response_path(invitation),
        {"response_status": Invitation.ResponseStatus.ACCEPTED},
        format="json",
        REMOTE_ADDR="192.0.2.40",
        HTTP_X_FORWARDED_FOR="198.51.100.1",
    )
    throttled_response = client.put(
        response_path(invitation),
        {"response_status": Invitation.ResponseStatus.DECLINED},
        format="json",
        REMOTE_ADDR="192.0.2.40",
        HTTP_X_FORWARDED_FOR="203.0.113.1",
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    invitation.refresh_from_db()
    assert invitation.response_status == Invitation.ResponseStatus.ACCEPTED


def test_openapi_documents_public_response_contract() -> None:
    """The schema documents request, result, errors, throttling, and no auth."""
    schema_response = APIClient().get("/api/schema/?format=json")

    assert schema_response.status_code == status.HTTP_200_OK
    schema = schema_response.json()
    path = schema["paths"]["/api/v1/invitations/{id}/response/"]
    assert "put" in path
    assert not {"get", "post", "patch", "delete"}.intersection(path)
    operation = path["put"]
    assert operation.get("security", []) == []
    assert set(operation["responses"]) >= {"200", "400", "404", "409", "429"}
    request_reference = operation["requestBody"]["content"]["application/json"]["schema"]["$ref"]
    assert request_reference.endswith("/InvitationResponseUpdate")
