"""Common and invitation API views."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.common.authentication import (
    HasInvitationManagementToken,
    ManagementTokenAuthentication,
)
from apps.common.capabilities import generate_management_token, hash_management_token
from apps.common.models import Invitation
from apps.common.serializers import (
    HealthResponseSerializer,
    InvitationCreateResponseSerializer,
    InvitationSerializer,
)


class NoStoreResponseMixin:
    """Prevent browsers and intermediaries from storing capability responses."""

    def finalize_response(
        self,
        request: Request,
        response: Response,
        *args: object,
        **kwargs: object,
    ) -> Response:
        """Attach cache directives to success and error responses alike."""
        finalized_response = super().finalize_response(request, response, *args, **kwargs)
        finalized_response["Cache-Control"] = "private, no-store"
        finalized_response["Pragma"] = "no-cache"
        return finalized_response


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


class InvitationCreateView(NoStoreResponseMixin, generics.CreateAPIView):
    """Create invitations without exposing a collection endpoint."""

    serializer_class = InvitationSerializer
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "invitation_create"
    http_method_names = ["post", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Create an invitation",
        request=InvitationSerializer,
        responses={
            status.HTTP_201_CREATED: InvitationCreateResponseSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The invitation fields are invalid."
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The invitation creation rate limit was exceeded."
            ),
        },
        auth=[],
    )
    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Create one invitation for an author and recipient."""
        return super().post(request, *args, **kwargs)

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Create an invitation and expose its management capability once."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        management_token = generate_management_token()
        invitation = serializer.save(
            management_token_hash=hash_management_token(management_token),
        )
        response_serializer = InvitationCreateResponseSerializer(
            invitation,
            context={
                **self.get_serializer_context(),
                "management_token": management_token,
            },
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=self.get_success_headers(serializer.data),
        )


class InvitationDetailView(NoStoreResponseMixin, generics.RetrieveAPIView):
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


class InvitationManagementDetailView(NoStoreResponseMixin, generics.RetrieveAPIView):
    """Retrieve an invitation through its author-only management capability."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Get an invitation for management",
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
        },
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Return one invitation when its management capability is valid."""
        return super().get(request, *args, **kwargs)
