"""Tests for the global API request throttling policy."""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle


def test_throttle_cache_is_shared_between_server_workers(settings) -> None:
    """The configured cache must not fall back to per-process local memory."""
    assert settings.CACHES["default"]["BACKEND"] == (
        "django.core.cache.backends.filebased.FileBasedCache"
    )
    assert settings.CACHES["default"]["LOCATION"].startswith("/")


def test_global_anonymous_throttle_returns_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The global anonymous limit rejects excess API traffic with retry guidance."""
    monkeypatch.setitem(AnonRateThrottle.THROTTLE_RATES, "anon", "2/min")
    client = APIClient()
    client_address = {"REMOTE_ADDR": "192.0.2.10"}

    first_response = client.get("/api/v1/health/", **client_address)
    second_response = client.get("/api/v1/health/", **client_address)
    throttled_response = client.get("/api/v1/health/", **client_address)

    assert first_response.status_code == status.HTTP_200_OK
    assert second_response.status_code == status.HTTP_200_OK
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    retry_after = throttled_response.headers.get("Retry-After")
    assert retry_after is not None
    assert 1 <= int(retry_after) <= 60


def test_untrusted_forwarded_for_cannot_bypass_client_rate_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no trusted proxy, spoofed forwarding headers do not change identity."""
    monkeypatch.setitem(AnonRateThrottle.THROTTLE_RATES, "anon", "1/min")
    client = APIClient()

    first_response = client.get(
        "/api/v1/health/",
        REMOTE_ADDR="192.0.2.15",
        HTTP_X_FORWARDED_FOR="198.51.100.1",
    )
    throttled_response = client.get(
        "/api/v1/health/",
        REMOTE_ADDR="192.0.2.15",
        HTTP_X_FORWARDED_FOR="203.0.113.1",
    )

    assert first_response.status_code == status.HTTP_200_OK
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_invitation_create_throttle_returns_retry_after(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invitation creation has a stricter independent per-client rate limit."""
    monkeypatch.setitem(
        ScopedRateThrottle.THROTTLE_RATES,
        "invitation_create",
        "2/min",
    )
    client = APIClient()
    client_address = {"REMOTE_ADDR": "192.0.2.20"}
    payload = {
        "author_name": "Алиса",
        "recipient_name": "Борис",
        "message": "Давай сходим на свидание?",
    }

    first_response = client.post(
        "/api/v1/invitations/",
        payload,
        format="json",
        **client_address,
    )
    second_response = client.post(
        "/api/v1/invitations/",
        payload,
        format="json",
        **client_address,
    )
    throttled_response = client.post(
        "/api/v1/invitations/",
        payload,
        format="json",
        **client_address,
    )

    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    assert throttled_response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert throttled_response["Cache-Control"] == "private, no-store"

    retry_after = throttled_response.headers.get("Retry-After")
    assert retry_after is not None
    assert 1 <= int(retry_after) <= 60
