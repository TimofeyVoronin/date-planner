"""API view for publishing author-owned invitation drafts."""

from django.db import transaction
from django.utils.timezone import now
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

from apps.common.authentication import (
    HasInvitationManagementToken,
    ManagementTokenAuthentication,
)
from apps.common.mixins import NoStoreResponseMixin
from apps.common.models import Invitation
from apps.common.serializers import InvitationSerializer


class InvitationPublicationView(NoStoreResponseMixin, generics.GenericAPIView):
    """Publish one author-owned draft and keep exact retries idempotent."""

    queryset = Invitation.objects.select_for_update()
    serializer_class = InvitationSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_plan"
    http_method_names = ["put", "options"]

    @extend_schema(
        tags=["invitations"],
        summary="Publish an invitation draft",
        request=None,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The invitation publication rate limit was exceeded."
            ),
        },
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Make the invitation public once without replacing its publication time."""
        with transaction.atomic():
            invitation = self.get_object()
            if invitation.publication_status == Invitation.PublicationStatus.DRAFT:
                invitation.publication_status = Invitation.PublicationStatus.PUBLISHED
                invitation.published_at = now()
                invitation.save(
                    update_fields=(
                        "publication_status",
                        "published_at",
                        "updated_at",
                    )
                )

            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)
