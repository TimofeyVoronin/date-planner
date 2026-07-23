"""Common and invitation API views."""

from django.db import transaction
from django.utils.timezone import now
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

from apps.common.authentication import (
    HasInvitationManagementToken,
    ManagementTokenAuthentication,
)
from apps.common.capabilities import generate_management_token, hash_management_token
from apps.common.mixins import NoStoreResponseMixin
from apps.common.models import Invitation
from apps.common.serializers import (
    HealthResponseSerializer,
    InvitationCreateResponseSerializer,
    InvitationManagementUpdateSerializer,
    InvitationResponseUpdateSerializer,
    InvitationSerializer,
)


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
        creation_mode = serializer.validated_data.get(
            "creation_mode",
            Invitation.CreationMode.QUICK,
        )
        is_extended = creation_mode == Invitation.CreationMode.EXTENDED
        invitation = serializer.save(
            management_token_hash=hash_management_token(management_token),
            publication_status=(
                Invitation.PublicationStatus.DRAFT
                if is_extended
                else Invitation.PublicationStatus.PUBLISHED
            ),
            published_at=None if is_extended else now(),
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

    queryset = Invitation.objects.filter(
        publication_status=Invitation.PublicationStatus.PUBLISHED,
    )
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


class InvitationManagementDetailView(NoStoreResponseMixin, generics.GenericAPIView):
    """Read or partially edit an invitation through its author capability."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationManagementUpdateSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    http_method_names = ["get", "patch", "options"]

    def get_queryset(self):
        """Lock the row only while applying a partial update."""
        queryset = super().get_queryset()
        if self.request.method == "PATCH":
            return queryset.select_for_update()
        return queryset

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
        invitation = self.get_object()
        output_data = InvitationSerializer(
            invitation,
            context=self.get_serializer_context(),
        ).data
        return Response(output_data, status=status.HTTP_200_OK)

    @extend_schema(
        tags=["invitations"],
        summary="Partially update an invitation for management",
        request=InvitationManagementUpdateSerializer,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The editable invitation fields are invalid."
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The invitation management rate limit was exceeded."
            ),
        },
    )
    def patch(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Apply only author-editable fields and keep exact retries idempotent."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(
                invitation,
                data=request.data,
                partial=True,
            )
            input_serializer.is_valid(raise_exception=True)
            invitation = input_serializer.save()
            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)


class InvitationResponseView(NoStoreResponseMixin, generics.GenericAPIView):
    """Store the recipient's current response through the public invitation UUID."""

    queryset = Invitation.objects.filter(
        publication_status=Invitation.PublicationStatus.PUBLISHED,
    ).select_for_update()
    serializer_class = InvitationResponseUpdateSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_response"
    http_method_names = ["put", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Set the invitation response",
        request=InvitationResponseUpdateSerializer,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The response status must be accepted or declined."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="A confirmed invitation response cannot be changed."
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The invitation response rate limit was exceeded."
            ),
        },
        auth=[],
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Set or replace the invitation response, preserving idempotent repeats."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            response_status = input_serializer.validated_data["response_status"]
            confirmation_exists = invitation.plan_options.filter(
                confirmed_at__isnull=False
            ).exists()
            if confirmation_exists and invitation.response_status != response_status:
                return Response(
                    {"detail": "The response cannot change after final confirmation."},
                    status=status.HTTP_409_CONFLICT,
                )
            clear_selection = (
                response_status == Invitation.ResponseStatus.DECLINED
                and invitation.plan_options.filter(selected_at__isnull=False).exists()
            )
            if (
                invitation.response_status != response_status
                or invitation.responded_at is None
                or clear_selection
            ):
                invitation.response_status = response_status
                invitation.responded_at = now()
                update_fields = ["response_status", "responded_at", "updated_at"]
                if clear_selection:
                    invitation.plan_options.filter(selected_at__isnull=False).update(
                        selected_at=None
                    )
                invitation.save(update_fields=update_fields)

            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(
            output_data,
            status=status.HTTP_200_OK,
        )
