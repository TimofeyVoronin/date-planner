"""Common API views."""

from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.serializers import HealthResponseSerializer


@extend_schema(
    tags=["system"],
    summary="Check backend health",
    responses={200: HealthResponseSerializer},
    auth=[],
)
@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def health_check(request: Request) -> Response:
    """Return a lightweight public service health response."""
    return Response(
        {
            "status": "ok",
            "service": "date-planner-backend",
        }
    )
