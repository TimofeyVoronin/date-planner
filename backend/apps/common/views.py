"""Common and invitation API views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.models import Invitation
from apps.common.serializers import HealthResponseSerializer, InvitationSerializer


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


class InvitationCreateView(generics.CreateAPIView):
    """Create invitations without exposing a collection endpoint."""

    serializer_class = InvitationSerializer
    permission_classes = [AllowAny]
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Create an invitation",
        request=InvitationSerializer,
        responses={
            status.HTTP_201_CREATED: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The invitation fields are invalid."
            ),
        },
        auth=[],
    )
    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Create one invitation for an author and recipient."""
        return super().post(request, *args, **kwargs)


class InvitationDetailView(generics.RetrieveAPIView):
    """Retrieve one invitation by its public UUID."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    permission_classes = [AllowAny]
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Get an invitation",
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
        },
        auth=[],
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Return the invitation addressed by the URL UUID."""
        return super().get(request, *args, **kwargs)
