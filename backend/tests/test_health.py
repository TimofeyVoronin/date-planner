"""Tests for the public health endpoint."""

import pytest
from django.db import OperationalError
from rest_framework import status
from rest_framework.test import APIClient

from apps.common import views


def test_health_endpoint_returns_service_status() -> None:
    """The endpoint reports a stable status payload without authentication."""
    response = APIClient().get("/api/v1/health/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "ok",
        "service": "date-planner-backend",
    }


@pytest.mark.django_db
def test_readiness_endpoint_checks_the_database() -> None:
    """The readiness endpoint succeeds when PostgreSQL accepts a query."""
    response = APIClient().get("/api/v1/ready/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "status": "ok",
        "service": "date-planner-backend",
    }


def test_readiness_endpoint_returns_generic_503_when_database_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Database errors never disclose connection details in the public response."""

    class UnavailableDatabase:
        def cursor(self) -> None:
            raise OperationalError("password=do-not-expose host=private-db")

    monkeypatch.setattr(views, "connection", UnavailableDatabase())

    response = APIClient().get("/api/v1/ready/")

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json() == {
        "status": "unavailable",
        "service": "date-planner-backend",
    }
    assert "do-not-expose" not in response.content.decode()
