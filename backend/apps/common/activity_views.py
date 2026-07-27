"""Protected API views for ordered invitation activity options."""

from django.db import transaction
from django.shortcuts import get_object_or_404
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
from apps.common.models import ActivityOption, Invitation
from apps.common.serializers import (
    ActivityOptionSerializer,
    ActivityOptionsResponseSerializer,
    ActivityOptionsUpdateSerializer,
    ActivitySelectionUpdateSerializer,
    InvitationSerializer,
)


class InvitationActivityOptionsView(NoStoreResponseMixin, generics.GenericAPIView):
    """Read or atomically replace one invitation's ordered activity collection."""

    queryset = Invitation.objects.prefetch_related("activity_options")
    serializer_class = ActivityOptionsUpdateSerializer
    authentication_classes = [ManagementTokenAuthentication]
    permission_classes = [HasInvitationManagementToken]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_plan"
    http_method_names = ["get", "put", "options"]

    @staticmethod
    def _response_data(invitation: Invitation) -> dict[str, object]:
        """Serialize the current collection without exposing future model fields."""
        return {
            "options": ActivityOptionSerializer(
                invitation.activity_options.all(),
                many=True,
            ).data
        }

    @staticmethod
    def _editing_conflict(invitation: Invitation) -> Response | None:
        """Keep activity authoring inside the unpublished extended builder."""
        if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
            return Response(
                {"detail": "Activity options belong only to extended invitations."},
                status=status.HTTP_409_CONFLICT,
            )
        if invitation.publication_status != Invitation.PublicationStatus.DRAFT:
            return Response(
                {"detail": "Published activity options are closed for editing."},
                status=status.HTTP_409_CONFLICT,
            )
        return None

    @extend_schema(
        tags=["activities"],
        summary="Get invitation activity options",
        responses={
            status.HTTP_200_OK: ActivityOptionsResponseSerializer,
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="Activity options belong only to extended invitations."
            ),
        },
    )
    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Return saved activities in author-defined order."""
        invitation = self.get_object()
        if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
            return Response(
                {"detail": "Activity options belong only to extended invitations."},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(self._response_data(invitation), status=status.HTTP_200_OK)

    @extend_schema(
        tags=["activities"],
        summary="Replace invitation activity options",
        request=ActivityOptionsUpdateSerializer,
        responses={
            status.HTTP_200_OK: ActivityOptionsResponseSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The activity collection is invalid."
            ),
            status.HTTP_401_UNAUTHORIZED: OpenApiResponse(
                description="The Bearer authorization header is missing or malformed."
            ),
            status.HTTP_403_FORBIDDEN: OpenApiResponse(
                description="The management token does not match this invitation."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description="Only an unpublished extended invitation can edit activities."
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The planning rate limit was exceeded."
            ),
        },
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Replace all activities while preserving exact retries and array order."""
        with transaction.atomic():
            invitation = get_object_or_404(
                Invitation.objects.select_for_update().prefetch_related("activity_options"),
                pk=kwargs["pk"],
            )
            self.check_object_permissions(request, invitation)

            conflict = self._editing_conflict(invitation)
            if conflict is not None:
                return conflict

            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            submitted_options = input_serializer.validated_data["options"]
            existing_options = list(invitation.activity_options.all())
            options_unchanged = len(existing_options) == len(submitted_options) and all(
                existing.title == submitted["title"]
                and existing.description == submitted["description"]
                and existing.image_key == submitted["image_key"]
                and existing.place == submitted["place"]
                for existing, submitted in zip(
                    existing_options,
                    submitted_options,
                    strict=True,
                )
            )

            if not options_unchanged:
                invitation.activity_options.all().delete()
                ActivityOption.objects.bulk_create(
                    [
                        ActivityOption(
                            invitation=invitation,
                            title=option["title"],
                            description=option["description"],
                            image_key=option["image_key"],
                            place=option["place"],
                            position=position,
                        )
                        for position, option in enumerate(submitted_options)
                    ]
                )
                invitation.save(update_fields=("updated_at",))
                invitation = Invitation.objects.prefetch_related("activity_options").get(
                    pk=invitation.pk
                )

            output_data = self._response_data(invitation)

        return Response(output_data, status=status.HTTP_200_OK)


class InvitationActivitySelectionView(NoStoreResponseMixin, generics.GenericAPIView):
    """Store the recipient's current activity selection through the public UUID."""

    queryset = Invitation.objects.filter(
        publication_status=Invitation.PublicationStatus.PUBLISHED,
    ).select_for_update()
    serializer_class = ActivitySelectionUpdateSerializer
    authentication_classes = []
    permission_classes = [AllowAny]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "invitation_plan"
    http_method_names = ["put", "options"]

    @extend_schema(
        tags=["activities"],
        summary="Select one invitation activity option",
        request=ActivitySelectionUpdateSerializer,
        responses={
            status.HTTP_200_OK: InvitationSerializer,
            status.HTTP_400_BAD_REQUEST: OpenApiResponse(
                description="The activity option identifier is invalid or unavailable."
            ),
            status.HTTP_404_NOT_FOUND: OpenApiResponse(description="Invitation not found."),
            status.HTTP_409_CONFLICT: OpenApiResponse(
                description=(
                    "The invitation has not been accepted or its final plan is already confirmed."
                )
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The planning rate limit was exceeded."
            ),
        },
        auth=[],
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Select or replace one activity, leaving exact retries idempotent."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            option_id = input_serializer.validated_data["option_id"]

            if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
                return Response(
                    {"detail": "Activity selection belongs only to extended invitations."},
                    status=status.HTTP_409_CONFLICT,
                )

            if invitation.response_status != Invitation.ResponseStatus.ACCEPTED:
                return Response(
                    {"detail": "Activity selection is available only after acceptance."},
                    status=status.HTTP_409_CONFLICT,
                )

            try:
                selected_option = ActivityOption.objects.get(
                    invitation=invitation,
                    pk=option_id,
                )
            except ActivityOption.DoesNotExist:
                return Response(
                    {"option_id": ["This activity is not available for the invitation."]},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            current_selection = invitation.activity_options.filter(
                selected_at__isnull=False
            ).first()
            final_plan_confirmed = invitation.plan_options.filter(
                confirmed_at__isnull=False
            ).exists()
            if final_plan_confirmed and (
                current_selection is None or current_selection.pk != selected_option.pk
            ):
                return Response(
                    {"detail": "The confirmed activity selection cannot be changed."},
                    status=status.HTTP_409_CONFLICT,
                )

            if current_selection is None or current_selection.pk != selected_option.pk:
                selection_time = now()
                invitation.activity_options.filter(selected_at__isnull=False).update(
                    selected_at=None
                )
                selected_option.selected_at = selection_time
                selected_option.save(update_fields=("selected_at",))
                invitation.save(update_fields=("updated_at",))

            invitation._selected_activity_option_cache = selected_option
            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)
