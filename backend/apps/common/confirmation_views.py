"""API view for the author's irreversible final plan confirmation."""

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
from apps.common.serializers import (
    InvitationConfirmationSerializer,
    InvitationSerializer,
)


class InvitationConfirmationView(NoStoreResponseMixin, generics.GenericAPIView):
    """Irreversibly confirm the accepted invitation's selected future option."""

    queryset = Invitation.objects.select_for_update()
    serializer_class = InvitationConfirmationSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_plan"
    http_method_names = ["put", "options"]

    @extend_schema(
        tags=["planning"],
        summary="Confirm the selected invitation plan",
        request=InvitationConfirmationSerializer,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description=(
                    "The confirmed field must be the boolean value true and option_id must "
                    "be a UUID."
                )
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description=(
                    "The invitation is not accepted, has no selection, or its selected "
                    "option differs from option_id or is no longer in the future "
                    "(code: selected_option_expired)."
                )
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The planning rate limit was exceeded."
            ),
        },
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Set the final confirmation once and leave exact retries unchanged."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            expected_option_id = input_serializer.validated_data["option_id"]

            if invitation.response_status != Invitation.ResponseStatus.ACCEPTED:
                return Response(
                    {"detail": "Confirmation requires an accepted invitation."},
                    status=status.HTTP_409_CONFLICT,
                )

            selected_option = invitation.plan_options.filter(selected_at__isnull=False).first()
            if selected_option is None:
                return Response(
                    {"detail": "Confirmation requires a selected planning option."},
                    status=status.HTTP_409_CONFLICT,
                )

            if selected_option.pk != expected_option_id:
                return Response(
                    {"detail": "The selected planning option changed before confirmation."},
                    status=status.HTTP_409_CONFLICT,
                )

            if selected_option.confirmed_at is None:
                confirmed_at = now()
                if selected_option.starts_at <= confirmed_at:
                    return Response(
                        {
                            "code": "selected_option_expired",
                            "detail": "The selected option is no longer in the future.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                selected_option.confirmed_at = confirmed_at
                selected_option.save(update_fields=("confirmed_at",))
                invitation.save(update_fields=("updated_at",))

            invitation._selected_plan_option_cache = selected_option
            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)
