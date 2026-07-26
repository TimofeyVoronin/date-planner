"""API views for proposing and selecting invitation planning options."""

from django.db import transaction
from django.utils.timezone import now
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import generics, status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle

from apps.common.authentication import (
    HasInvitationManagementToken,
    ManagementTokenAuthentication,
)
from apps.common.mixins import NoStoreResponseMixin
from apps.common.models import Invitation, InvitationPlanOption
from apps.common.serializers import (
    InvitationPlanOptionsUpdateSerializer,
    InvitationSelectionUpdateSerializer,
    InvitationSerializer,
)


class InvitationPlanOptionsView(NoStoreResponseMixin, generics.GenericAPIView):
    """Atomically replace options at the time selected by the invitation author."""

    queryset = Invitation.objects.select_for_update()
    serializer_class = InvitationPlanOptionsUpdateSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_plan"
    http_method_names = ["put", "options"]

    @extend_schema(
        tags=["planning"],
        summary="Replace the invitation planning options",
        request=InvitationPlanOptionsUpdateSerializer,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(description="The option set is invalid."),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description=(
                    "The invitation is not currently editable in its planning mode, or its "
                    "selection is still future-dated or already confirmed. A published "
                    "before-acceptance set can recover only after an unconfirmed selection "
                    "expires; exact retries remain idempotent."
                )
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The planning rate limit was exceeded."
            ),
        },
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Replace options only in an editable or safely recoverable planning state."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)

            submitted_options = input_serializer.validated_data["options"]
            existing_options = list(invitation.plan_options.all())
            options_unchanged = len(existing_options) == len(submitted_options) and all(
                existing.starts_at == submitted["starts_at"]
                and existing.place == submitted["place"]
                and existing.comment == submitted["comment"]
                for existing, submitted in zip(
                    existing_options,
                    submitted_options,
                    strict=True,
                )
            )
            current_selection = invitation.plan_options.filter(selected_at__isnull=False).first()
            request_time = now()
            selection_is_expired_and_unconfirmed = (
                current_selection is not None
                and current_selection.confirmed_at is None
                and current_selection.starts_at <= request_time
            )

            if invitation.planning_mode == Invitation.PlanningMode.BEFORE_ACCEPTANCE:
                draft_is_editable = (
                    invitation.creation_mode == Invitation.CreationMode.EXTENDED
                    and invitation.publication_status == Invitation.PublicationStatus.DRAFT
                )
                published_recovery_is_available = (
                    invitation.creation_mode == Invitation.CreationMode.EXTENDED
                    and invitation.publication_status == Invitation.PublicationStatus.PUBLISHED
                    and invitation.response_status == Invitation.ResponseStatus.ACCEPTED
                    and selection_is_expired_and_unconfirmed
                )
                published_retry_is_idempotent = (
                    invitation.publication_status == Invitation.PublicationStatus.PUBLISHED
                    and options_unchanged
                )
                planning_is_available = (
                    draft_is_editable
                    or published_recovery_is_available
                    or published_retry_is_idempotent
                )
                planning_error = (
                    "Published dates prepared before acceptance can change only after the "
                    "selected, unconfirmed option has expired."
                )
            else:
                planning_is_available = (
                    invitation.response_status == Invitation.ResponseStatus.ACCEPTED
                )
                planning_error = "Planning is available only after the invitation is accepted."

            if not planning_is_available:
                return Response(
                    {"detail": planning_error},
                    status=status.HTTP_409_CONFLICT,
                )

            if (
                not options_unchanged
                and current_selection is not None
                and not selection_is_expired_and_unconfirmed
            ):
                return Response(
                    {
                        "detail": (
                            "Planning options cannot change while the selection is future "
                            "or confirmed."
                        )
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            if not options_unchanged:
                InvitationPlanOption.objects.filter(invitation=invitation).delete()
                InvitationPlanOption.objects.bulk_create(
                    [
                        InvitationPlanOption(
                            invitation=invitation,
                            starts_at=option["starts_at"],
                            place=option["place"],
                            comment=option["comment"],
                            position=position,
                        )
                        for position, option in enumerate(submitted_options)
                    ]
                )
                invitation.save(update_fields=("updated_at",))
            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)


class InvitationSelectionView(NoStoreResponseMixin, generics.GenericAPIView):
    """Store the recipient's current option selection through the public UUID."""

    queryset = Invitation.objects.filter(
        publication_status=Invitation.PublicationStatus.PUBLISHED,
    ).select_for_update()
    serializer_class = InvitationSelectionUpdateSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_plan"
    http_method_names = ["put", "options"]

    @extend_schema(
        tags=["planning"],
        summary="Select one invitation planning option",
        request=InvitationSelectionUpdateSerializer,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The option identifier is invalid or unavailable."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description=(
                    "The invitation has not been accepted or its selected plan is already "
                    "confirmed."
                )
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The planning rate limit was exceeded."
            ),
        },
        auth=[],
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Select or replace one option, leaving exact retries idempotent."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            option_id = input_serializer.validated_data["option_id"]
            if invitation.response_status != Invitation.ResponseStatus.ACCEPTED:
                return Response(
                    {"detail": "Selection is available only for an accepted invitation."},
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                selected_option = InvitationPlanOption.objects.get(
                    invitation=invitation,
                    pk=option_id,
                )
            except InvitationPlanOption.DoesNotExist:
                return Response(
                    {"option_id": ["This option is not available for the invitation."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_selection = invitation.plan_options.filter(selected_at__isnull=False).first()
            if (
                current_selection is not None
                and current_selection.confirmed_at is not None
                and current_selection.pk != selected_option.pk
            ):
                return Response(
                    {"detail": "The confirmed planning option cannot be changed."},
                    status=status.HTTP_409_CONFLICT,
                )

            if current_selection is None or current_selection.pk != selected_option.pk:
                selected_at = now()
                if selected_option.starts_at <= selected_at:
                    return Response(
                        {"option_id": ["This option is no longer in the future."]},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                invitation.plan_options.filter(selected_at__isnull=False).update(selected_at=None)
                selected_option.selected_at = selected_at
                selected_option.save(update_fields=("selected_at",))
                invitation.save(update_fields=("updated_at",))

            invitation._selected_plan_option_cache = selected_option

            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)
