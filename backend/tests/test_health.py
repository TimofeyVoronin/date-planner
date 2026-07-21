"""Tests for the public health endpoint."""

from rest_framework import status
from rest_framework.test import APIClient


def test_health_endpoint_returns_service_status() -> None:
    """The endpoint reports a stable status payload without authentication."""
    response = APIClient().get("/api/v1/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "ok",
        "service": "date-planner-backend",
    }
