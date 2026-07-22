"""Tests for browser access to public and capability-protected API routes."""

import uuid

import pytest
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


def test_trusted_frontend_preflight_allows_public_response_put(settings) -> None:
    """The configured frontend can submit an invitation answer with JSON PUT."""
    trusted_origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = APIClient().options(
        f"/api/v1/invitations/{uuid.uuid4()}/response/",
        HTTP_ORIGIN=trusted_origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="PUT",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="content-type",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Access-Control-Allow-Origin"] == trusted_origin
    assert "PUT" in response["Access-Control-Allow-Methods"]
    assert "content-type" in response["Access-Control-Allow-Headers"].lower()


@pytest.mark.parametrize("suffix", ["plan-options", "selection", "confirmation"])
def test_trusted_frontend_preflight_allows_planning_put(settings, suffix: str) -> None:
    """The frontend can submit author and recipient planning JSON requests."""
    trusted_origin = settings.CORS_ALLOWED_ORIGINS[0]

    response = APIClient().options(
        f"/api/v1/invitations/{uuid.uuid4()}/{suffix}/",
        HTTP_ORIGIN=trusted_origin,
        HTTP_ACCESS_CONTROL_REQUEST_METHOD="PUT",
        HTTP_ACCESS_CONTROL_REQUEST_HEADERS="authorization, content-type",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response["Access-Control-Allow-Origin"] == trusted_origin
    assert "PUT" in response["Access-Control-Allow-Methods"]
    assert "authorization" in response["Access-Control-Allow-Headers"].lower()
