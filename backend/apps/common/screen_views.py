"""Protected API view for extended invitation screen configurations."""

from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response

from apps.common.authentication import (
    HasInvitationManagementToken,
    ManagementTokenAuthentication,
)
from apps.common.mixins import NoStoreResponseMixin
from apps.common.models import Invitation
from apps.common.screens import order_invitation_screens
from apps.common.serializers import InvitationScreenSerializer


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
