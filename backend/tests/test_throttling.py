"""Tests for the global API request throttling policy."""

from collections.abc import Iterator

import pytest
from django.core.cache import cache
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework.throttling import AnonRateThrottle


@pytest.fixture
def isolated_throttle_cache() -> Iterator[None]:
    """Keep throttle counters isolated from the rest of the test suite."""
    cache.clear()
    yield
    cache.clear()


def test_throttle_cache_is_shared_between_server_workers(settings) -> None:
    """The configured cache must not fall back to per-process local memory."""
    assert settings.CACHES["default"]["BACKEND"] == (
        "django.core.cache.backends.filebased.FileBasedCache"
    )
    assert settings.CACHES["default"]["LOCATION"].startswith("/")


def test_global_anonymous_throttle_returns_retry_after(
    monkeypatch: pytest.MonkeyPatch,
    isolated_throttle_cache: None,
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
