"""Tests for browser access to public and capability-protected API routes."""

import uuid

from rest_framework import status
from rest_framework.test import APIClient


def test_trusted_frontend_preflight_allows_authorization_header(settings) -> None:
    """The configured frontend can send a Bearer capability from the browser."""
    trusted_origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = APIClient().options(
        f"/api/v1/invitations/{uuid.uuid4()}/manage/",
        HTTP_ORIGIN=trusted_origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Access-Control-Allow-Origin"] == trusted_origin
    assert "authorization" in response["Access-Control-Allow-Headers"].lower()


def test_untrusted_origin_receives_no_cors_permission() -> None:
    """An unrelated website is never granted browser access to invitation data."""
    response = APIClient().options(
        f"/api/v1/invitations/{uuid.uuid4()}/manage/",
        HTTP_ORIGIN="https://attacker.example",
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="GET",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization",
    )

    assert response.status_code == status.HTTP_200_OK
    assert "Access-Control-Allow-Origin" not in response
