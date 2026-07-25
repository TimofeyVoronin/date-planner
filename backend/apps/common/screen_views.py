"""Protected API views for extended invitation screen configurations."""

from django.db import transaction
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.authentication import (
    HasInvitationManagementToken,
    ManagementTokenAuthentication,
)
from apps.common.mixins import NoStoreResponseMixin
from apps.common.models import Invitation, InvitationScreen
from apps.common.screens import order_invitation_screens
from apps.common.serializers import (
    InvitationScreenSerializer,
    InvitationScreenUpdateSerializer,
)


class InvitationScreenListView(NoStoreResponseMixin, generics.GenericAPIView):
    """Return the stable screen set owned by one extended invitation."""

    queryset = Invitation.objects.prefetch_related("screens")
    serializer_class = InvitationScreenSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    http_method_names = ["get", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Get invitation screen configurations",
        responses={
            status.HTTP_200_OK: InvitationScreenSerializer(many=True),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="Screen configuration belongs only to extended invitations."
            ),
        },
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Return all five screen configurations in recipient-flow order."""
        invitation = self.get_object()
        if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
            return Response(
                {"detail": ("Screen configuration is available only for extended invitations.")},
                status=status.HTTP_409_CONFLICT,
            )

        screens = order_invitation_screens(invitation.screens.all())
        output_data = self.get_serializer(screens, many=True).data
        return Response(output_data, status=status.HTTP_200_OK)


class InvitationPrimaryScreenUpdateView(NoStoreResponseMixin, generics.GenericAPIView):
    """Partially update the primary recipient-facing screen of an extended draft."""

    queryset = Invitation.objects.all()
    serializer_class = InvitationScreenUpdateSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    http_method_names = ["patch", "options"]

    def get_queryset(self):
        """Lock the invitation capability target during a screen update."""
        return super().get_queryset().select_for_update()

    @extend_schema(
        tags=["invitations"],
        summary="Partially update the primary invitation screen",
        request=InvitationScreenUpdateSerializer,
        responses={
            status.HTTP_200_OK: InvitationScreenSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The editable screen fields are invalid."
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(
                description="Invitation or primary screen not found."
            ),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="Only an unpublished extended invitation can be edited."
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The invitation management rate limit was exceeded."
            ),
        },
    )
    def patch(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Apply a minimal idempotent PATCH to the draft's invitation screen."""
        with transaction.atomic():
            invitation = self.get_object()
            if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
                return Response(
                    {"detail": "Screen editing belongs only to extended invitations."},
                    status=status.HTTP_409_CONFLICT,
                )
            if invitation.publication_status != Invitation.PublicationStatus.DRAFT:
                return Response(
                    {"detail": "Published invitations are closed for screen editing."},
                    status=status.HTTP_409_CONFLICT,
                )

            screen = get_object_or_404(
                InvitationScreen.objects.select_for_update(),
                invitation_id=invitation.pk,
                screen_type=InvitationScreen.ScreenType.INVITATION,
            )
            input_serializer = self.get_serializer(
                screen,
                data=request.data,
                partial=True,
            )
            input_serializer.is_valid(raise_exception=True)
            screen = input_serializer.save()
            output_data = InvitationScreenSerializer(screen).data

        return Response(output_data, status=status.HTTP_200_OK)
