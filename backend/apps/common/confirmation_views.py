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
from apps.common.final_templates import (
    build_final_template_values,
    render_final_text_template,
)
from apps.common.mixins import NoStoreResponseMixin
from apps.common.models import ConfirmedPlan, Invitation, InvitationScreen
from apps.common.screens import DEFAULT_INVITATION_SCREEN_CONFIGS
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
                    "The invitation is not accepted, has no selection, or the selected "
                    "date/activity differs from the plan shown to the author, or the date "
                    "is no longer in the future (codes: activity_selection_required, "
                    "selected_option_changed, selected_activity_changed, "
                    "selected_option_expired)."
                )
            ),
            status.HTTP_429_TOO_MANY_REQUESTS: OpenApiResponse(
                description="The planning rate limit was exceeded."
            ),
        },
    )
    def put(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Create one immutable final snapshot and leave exact retries unchanged."""
        with transaction.atomic():
            invitation = self.get_object()
            input_serializer = self.get_serializer(data=request.data)
            input_serializer.is_valid(raise_exception=True)
            expected_option_id = input_serializer.validated_data["option_id"]
            expected_activity_option_id = input_serializer.validated_data.get("activity_option_id")

            existing_snapshot = ConfirmedPlan.objects.filter(invitation=invitation).first()
            if existing_snapshot is not None:
                if existing_snapshot.option_id != expected_option_id:
                    return Response(
                        {
                            "code": "selected_option_changed",
                            "detail": (
                                "The confirmed date differs from the plan in this retry. "
                                "Refresh the immutable final plan."
                            ),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )
                if existing_snapshot.activity_option_id != expected_activity_option_id:
                    return Response(
                        {
                            "code": "selected_activity_changed",
                            "detail": (
                                "The confirmed activity differs from the plan in this retry. "
                                "Refresh the immutable final plan."
                            ),
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

                output_data = InvitationSerializer(
                    invitation,
                    context=self.get_serializer_context(),
                ).data
                return Response(output_data, status=status.HTTP_200_OK)

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
                    {
                        "code": "selected_option_changed",
                        "detail": "The selected planning option changed before confirmation.",
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            has_activity_options = (
                invitation.creation_mode == Invitation.CreationMode.EXTENDED
                and invitation.activity_options.exists()
            )
            selected_activity_option = None
            if has_activity_options:
                selected_activity_option = invitation.activity_options.filter(
                    selected_at__isnull=False
                ).first()
                if selected_activity_option is None:
                    return Response(
                        {
                            "code": "activity_selection_required",
                            "detail": "Confirmation requires a selected activity option.",
                        },
                        status=status.HTTP_409_CONFLICT,
                    )

            selected_activity_option_id = (
                selected_activity_option.pk if selected_activity_option is not None else None
            )
            if expected_activity_option_id != selected_activity_option_id:
                return Response(
                    {
                        "code": "selected_activity_changed",
                        "detail": (
                            "The selected activity changed before confirmation. Refresh the "
                            "plan and confirm the current combination."
                        ),
                    },
                    status=status.HTTP_409_CONFLICT,
                )

            confirmed_at = selected_option.confirmed_at
            if confirmed_at is None:
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

            final_defaults = DEFAULT_INVITATION_SCREEN_CONFIGS[InvitationScreen.ScreenType.FINAL]
            final_screen = None
            if invitation.creation_mode == Invitation.CreationMode.EXTENDED:
                final_screen = invitation.screens.filter(
                    screen_type=InvitationScreen.ScreenType.FINAL
                ).first()
            final_title = (
                final_screen.title if final_screen is not None else final_defaults["title"]
            )
            final_subtitle = (
                final_screen.subtitle if final_screen is not None else final_defaults["subtitle"]
            )
            final_image_key = (
                final_screen.image_key if final_screen is not None else final_defaults["image_key"]
            )
            final_template = (
                final_screen.template_text
                if final_screen is not None and final_screen.template_text
                else final_defaults["template_text"]
            )
            activity_title = (
                selected_activity_option.title if selected_activity_option is not None else ""
            )
            final_text = render_final_text_template(
                final_template,
                build_final_template_values(
                    activity_title=activity_title,
                    author_name=invitation.author_name,
                    place=selected_option.place,
                    recipient_name=invitation.recipient_name,
                    starts_at=selected_option.starts_at,
                    time_zone=selected_option.time_zone,
                ),
            )
            ConfirmedPlan.objects.create(
                invitation=invitation,
                option_id=selected_option.pk,
                activity_option_id=selected_activity_option_id,
                starts_at=selected_option.starts_at,
                time_zone=selected_option.time_zone,
                place=selected_option.place,
                comment=selected_option.comment,
                activity_title=activity_title,
                activity_description=(
                    selected_activity_option.description
                    if selected_activity_option is not None
                    else ""
                ),
                activity_place=(
                    selected_activity_option.place if selected_activity_option is not None else ""
                ),
                activity_image_key=(
                    selected_activity_option.image_key
                    if selected_activity_option is not None
                    else ""
                ),
                final_title=final_title,
                final_subtitle=final_subtitle,
                final_image_key=final_image_key,
                final_text=final_text,
                confirmed_at=confirmed_at,
            )
            invitation.save(update_fields=("updated_at",))
            invitation._selected_plan_option_cache = selected_option
            invitation._selected_activity_option_cache = selected_activity_option
            output_data = InvitationSerializer(
                invitation,
                context=self.get_serializer_context(),
            ).data

        return Response(output_data, status=status.HTTP_200_OK)
