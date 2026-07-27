"""Serializers for common API responses."""

from collections.abc import Mapping
from datetime import datetime
from uuid import UUID

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, now
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.models import (
    INVITATION_ANSWER_STATUS_CHOICES,
    ActivityOption,
    Invitation,
    InvitationPlanOption,
    InvitationScreen,
)
from apps.common.screen_images import is_invitation_screen_image_compatible
from apps.common.screens import order_invitation_screens


class HealthResponseSerializer(serializers.Serializer):
    """Describe the health endpoint response."""

    status = serializers.CharField(read_only=True)
    service = serializers.CharField(read_only=True)


class InvitationScreenSerializer(serializers.ModelSerializer):
    """Expose only the configurable fields required by the author builder."""

    class Meta:
        """Keep database identifiers and timestamps internal to the service."""

        model = InvitationScreen
        fields = (
            "screen_type",
            "title",
            "subtitle",
            "button_text",
            "secondary_button_text",
            "image_key",
        )
        read_only_fields = fields


class InvitationScreenUpdateSerializer(serializers.ModelSerializer):
    """Validate editable fields shared by configurable invitation screens."""

    editable_fields = (
        "title",
        "subtitle",
        "button_text",
        "image_key",
    )

    class Meta:
        """Keep lifecycle, ownership, and screen type server-controlled."""

        model = InvitationScreen
        fields = (
            "title",
            "subtitle",
            "button_text",
            "image_key",
        )
        extra_kwargs = {
            "title": {"min_length": 1, "trim_whitespace": True},
            "subtitle": {"allow_blank": True, "trim_whitespace": True},
            "button_text": {"min_length": 1, "allow_blank": False, "trim_whitespace": True},
            "image_key": {"min_length": 1, "allow_blank": False, "trim_whitespace": True},
        }

    def to_internal_value(self, data: object) -> dict[str, object]:
        """Reject unknown and server-controlled fields instead of ignoring them."""
        if isinstance(data, Mapping):
            unsupported_fields = sorted(set(data) - set(self.editable_fields))
            if unsupported_fields:
                raise serializers.ValidationError(
                    {
                        field: ["This field cannot be edited through this endpoint."]
                        for field in unsupported_fields
                    }
                )
        return super().to_internal_value(data)

    def validate_image_key(self, image_key: str) -> str:
        """Accept only built-in image keys assigned to the current screen."""
        screen = self.instance
        if not isinstance(screen, InvitationScreen):
            raise RuntimeError("Screen updates require an InvitationScreen instance.")
        if not is_invitation_screen_image_compatible(screen.screen_type, image_key):
            raise serializers.ValidationError(
                "Choose a built-in image that belongs to this invitation screen."
            )
        return image_key

    def update(
        self,
        screen: InvitationScreen,
        validated_data: dict[str, object],
    ) -> InvitationScreen:
        """Persist only actual changes so exact PATCH retries remain idempotent."""
        changed_fields: list[str] = []
        for field, value in validated_data.items():
            if getattr(screen, field) == value:
                continue
            setattr(screen, field, value)
            changed_fields.append(field)

        if changed_fields:
            screen.save(update_fields=(*changed_fields, "updated_at"))

        return screen


class InvitationPrimaryScreenUpdateSerializer(InvitationScreenUpdateSerializer):
    """Validate the extra decline-button field of the primary screen."""

    editable_fields = (
        *InvitationScreenUpdateSerializer.editable_fields,
        "secondary_button_text",
    )

    class Meta(InvitationScreenUpdateSerializer.Meta):
        """Extend the shared screen fields with the decline action."""

        fields = (
            *InvitationScreenUpdateSerializer.Meta.fields,
            "secondary_button_text",
        )
        extra_kwargs = {
            **InvitationScreenUpdateSerializer.Meta.extra_kwargs,
            "secondary_button_text": {
                "min_length": 1,
                "allow_blank": False,
                "trim_whitespace": True,
            },
        }


class InvitationPlanOptionSerializer(serializers.ModelSerializer):
    """Expose one persisted planning option in its stable submitted position."""

    class Meta:
        """Expose only recipient-facing option fields."""

        model = InvitationPlanOption
        fields = ("id", "starts_at", "place", "comment", "position")
        read_only_fields = fields


class ActivityOptionSerializer(serializers.ModelSerializer):
    """Expose one persisted activity option in stable author order."""

    class Meta:
        """Keep future commercial metadata out of the first public contract."""

        model = ActivityOption
        fields = ("id", "title", "description", "image_key", "place", "position")
        read_only_fields = fields


class ActivityOptionInputSerializer(serializers.Serializer):
    """Validate one activity idea accepted by the first management API."""

    editable_fields = frozenset(("title", "description", "image_key", "place"))

    title = serializers.CharField(max_length=120, allow_blank=False, trim_whitespace=True)
    description = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )
    image_key = serializers.RegexField(
        regex=r"^[a-z0-9]+(?:-[a-z0-9]+)*$",
        max_length=80,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
        error_messages={
            "invalid": "Use a stable local image key made of lowercase words and hyphens."
        },
    )
    place = serializers.CharField(
        max_length=200,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )

    def to_internal_value(self, data: object) -> dict[str, object]:
        """Reject internal and future fields instead of silently ignoring them."""
        if isinstance(data, Mapping):
            unsupported_fields = sorted(set(data) - self.editable_fields)
            if unsupported_fields:
                raise serializers.ValidationError(
                    {
                        field: ["This field is not part of the activity API yet."]
                        for field in unsupported_fields
                    }
                )
        return super().to_internal_value(data)


class PositionalErrorListField(serializers.ListField):
    """Keep nested validation errors aligned with their input positions."""

    def run_child_validation(self, data: list[object]) -> list[object]:
        """Return list-shaped errors while retaining ListField schema constraints."""
        result: list[object] = []
        errors: list[object] = []
        has_errors = False

        for item in data:
            try:
                result.append(self.child.run_validation(item))
            except serializers.ValidationError as exc:
                errors.append(exc.detail)
                has_errors = True
            else:
                errors.append({})

        if has_errors:
            raise serializers.ValidationError(errors)
        return result


class ActivityOptionsUpdateSerializer(serializers.Serializer):
    """Validate an atomic replacement of three to six ordered activities."""

    editable_fields = frozenset(("options",))

    options = PositionalErrorListField(
        child=ActivityOptionInputSerializer(),
        min_length=3,
        max_length=6,
    )

    def to_internal_value(self, data: object) -> dict[str, object]:
        """Reject unknown collection fields before validating nested options."""
        if isinstance(data, Mapping):
            unsupported_fields = sorted(set(data) - self.editable_fields)
            if unsupported_fields:
                raise serializers.ValidationError(
                    {field: ["This field is not supported."] for field in unsupported_fields}
                )
        return super().to_internal_value(data)


class ActivityOptionsResponseSerializer(serializers.Serializer):
    """Document the ordered management collection response."""

    options = ActivityOptionSerializer(many=True, read_only=True)


class ActivitySelectionUpdateSerializer(serializers.Serializer):
    """Validate the recipient's selected activity identifier."""

    editable_fields = frozenset(("option_id",))

    option_id = serializers.UUIDField()

    def to_internal_value(self, data: object) -> dict[str, object]:
        """Reject unknown fields instead of silently ignoring them."""
        if isinstance(data, Mapping):
            unsupported_fields = sorted(set(data) - self.editable_fields)
            if unsupported_fields:
                raise serializers.ValidationError(
                    {field: ["This field is not supported."] for field in unsupported_fields}
                )
        return super().to_internal_value(data)


class InvitationSerializer(serializers.ModelSerializer):
    """Validate invitation input and expose its public representation."""

    plan_options = serializers.SerializerMethodField(
        help_text=(
            "Ordered planning options. Pending recipients do not receive options prepared "
            "before acceptance."
        )
    )
    activity_options = serializers.SerializerMethodField(
        help_text=(
            "Ordered activity options. Public recipients receive them only after accepting "
            "an extended invitation."
        )
    )
    screens = serializers.SerializerMethodField(
        help_text="Recipient-facing screen configuration in stable flow order."
    )
    selected_option_id = serializers.UUIDField(read_only=True, allow_null=True)
    selected_at = serializers.DateTimeField(read_only=True, allow_null=True)
    selected_activity_option_id = serializers.UUIDField(read_only=True, allow_null=True)
    activity_selected_at = serializers.DateTimeField(read_only=True, allow_null=True)
    confirmed_at = serializers.DateTimeField(read_only=True, allow_null=True)
    server_now = serializers.SerializerMethodField(
        help_text="Server time captured while serializing this API response."
    )

    class Meta:
        """Configure persisted and read-only invitation fields."""

        model = Invitation
        fields = (
            "id",
            "author_name",
            "recipient_name",
            "message",
            "creation_mode",
            "planning_mode",
            "publication_status",
            "published_at",
            "response_status",
            "responded_at",
            "screens",
            "plan_options",
            "activity_options",
            "selected_option_id",
            "selected_at",
            "selected_activity_option_id",
            "activity_selected_at",
            "confirmed_at",
            "server_now",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "publication_status",
            "published_at",
            "response_status",
            "responded_at",
            "screens",
            "plan_options",
            "activity_options",
            "selected_option_id",
            "selected_at",
            "selected_activity_option_id",
            "activity_selected_at",
            "confirmed_at",
            "server_now",
            "created_at",
            "updated_at",
        )
        extra_kwargs = {
            "author_name": {"min_length": 1, "trim_whitespace": True},
            "recipient_name": {"min_length": 1, "trim_whitespace": True},
            "message": {
                "required": False,
                "allow_blank": True,
                "trim_whitespace": True,
            },
            "creation_mode": {
                "required": False,
                "help_text": (
                    "The authoring flow: quick creates the current compact invitation, "
                    "while extended reserves the invitation for the guided builder."
                ),
            },
            "planning_mode": {
                "required": False,
                "help_text": (
                    "Whether the author prepares date options before the recipient accepts "
                    "or only after acceptance."
                ),
            },
        }

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Keep quick invitations on the compact post-acceptance planning flow."""
        creation_mode = attrs.get(
            "creation_mode",
            getattr(self.instance, "creation_mode", Invitation.CreationMode.QUICK),
        )
        planning_mode = attrs.get(
            "planning_mode",
            getattr(
                self.instance,
                "planning_mode",
                Invitation.PlanningMode.AFTER_ACCEPTANCE,
            ),
        )
        if (
            creation_mode == Invitation.CreationMode.QUICK
            and planning_mode != Invitation.PlanningMode.AFTER_ACCEPTANCE
        ):
            raise serializers.ValidationError(
                {"planning_mode": ["Quick invitations always prepare dates after acceptance."]}
            )
        return attrs

    @extend_schema_field(InvitationPlanOptionSerializer(many=True))
    def get_plan_options(self, invitation: Invitation) -> list[dict[str, object]]:
        """Hide preconfigured options until acceptance outside management requests."""
        request = self.context.get("request")
        has_management_capability = isinstance(getattr(request, "auth", None), str)
        if (
            invitation.planning_mode == Invitation.PlanningMode.BEFORE_ACCEPTANCE
            and invitation.response_status != Invitation.ResponseStatus.ACCEPTED
            and not has_management_capability
        ):
            return []
        return InvitationPlanOptionSerializer(invitation.plan_options.all(), many=True).data

    @extend_schema_field(ActivityOptionSerializer(many=True))
    def get_activity_options(self, invitation: Invitation) -> list[dict[str, object]]:
        """Hide activity choices until an extended invitation is accepted publicly."""
        if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
            return []

        request = self.context.get("request")
        has_management_capability = isinstance(getattr(request, "auth", None), str)
        if (
            invitation.response_status != Invitation.ResponseStatus.ACCEPTED
            and not has_management_capability
        ):
            return []

        return ActivityOptionSerializer(invitation.activity_options.all(), many=True).data

    @extend_schema_field(InvitationScreenSerializer(many=True))
    def get_screens(self, invitation: Invitation) -> list[dict[str, object]]:
        """Expose complete extended-screen configuration without internal identifiers."""
        if invitation.creation_mode != Invitation.CreationMode.EXTENDED:
            return []

        screens = order_invitation_screens(invitation.screens.all())
        return InvitationScreenSerializer(screens, many=True).data

    @extend_schema_field(serializers.DateTimeField())
    def get_server_now(self, invitation: Invitation) -> datetime:
        """Return a non-persisted server-clock snapshot for client expiry decisions."""
        return now()


class InvitationManagementUpdateSerializer(serializers.ModelSerializer):
    """Validate the small set of fields an author may edit through a capability."""

    editable_fields = (
        "author_name",
        "recipient_name",
        "message",
        "creation_mode",
        "planning_mode",
    )

    class Meta:
        """Expose only fields that are safe to update after creation."""

        model = Invitation
        fields = (
            "author_name",
            "recipient_name",
            "message",
            "creation_mode",
            "planning_mode",
        )
        extra_kwargs = {
            "author_name": {"min_length": 1, "trim_whitespace": True},
            "recipient_name": {"min_length": 1, "trim_whitespace": True},
            "message": {
                "required": False,
                "allow_blank": True,
                "trim_whitespace": True,
            },
            "creation_mode": {"required": False},
            "planning_mode": {"required": False},
        }

    def validate(self, attrs: dict[str, object]) -> dict[str, object]:
        """Validate the combined creation and planning flow before applying changes."""
        invitation = self.instance
        if not isinstance(invitation, Invitation):
            raise RuntimeError("Management updates require an Invitation instance.")

        creation_mode = attrs.get("creation_mode", invitation.creation_mode)
        planning_mode = attrs.get("planning_mode", invitation.planning_mode)
        if creation_mode == Invitation.CreationMode.QUICK:
            if (
                "planning_mode" in attrs
                and planning_mode != Invitation.PlanningMode.AFTER_ACCEPTANCE
            ):
                raise serializers.ValidationError(
                    {"planning_mode": ["Quick invitations always prepare dates after acceptance."]}
                )
            planning_mode = Invitation.PlanningMode.AFTER_ACCEPTANCE
            attrs["planning_mode"] = planning_mode

        if (
            planning_mode == Invitation.PlanningMode.BEFORE_ACCEPTANCE
            and creation_mode != Invitation.CreationMode.EXTENDED
        ):
            raise serializers.ValidationError(
                {"planning_mode": ["Preparing dates before acceptance requires extended mode."]}
            )

        return attrs

    def to_internal_value(self, data: object) -> dict[str, object]:
        """Reject unknown and lifecycle fields instead of silently ignoring them."""
        if isinstance(data, Mapping):
            unsupported_fields = sorted(set(data) - set(self.editable_fields))
            if unsupported_fields:
                raise serializers.ValidationError(
                    {
                        field: ["This field cannot be edited through this endpoint."]
                        for field in unsupported_fields
                    }
                )
        return super().to_internal_value(data)

    def update(
        self,
        invitation: Invitation,
        validated_data: dict[str, object],
    ) -> Invitation:
        """Persist only actual changes so exact retries keep ``updated_at`` stable."""
        changed_fields: list[str] = []
        for field, value in validated_data.items():
            if getattr(invitation, field) == value:
                continue
            setattr(invitation, field, value)
            changed_fields.append(field)

        if changed_fields:
            invitation.save(update_fields=(*changed_fields, "updated_at"))

        if (
            "planning_mode" in changed_fields
            and invitation.planning_mode == Invitation.PlanningMode.AFTER_ACCEPTANCE
            and invitation.publication_status == Invitation.PublicationStatus.DRAFT
        ):
            invitation.plan_options.all().delete()

        if invitation.creation_mode == Invitation.CreationMode.EXTENDED:
            from apps.common.screens import ensure_default_invitation_screens

            ensure_default_invitation_screens(invitation)
        return invitation


class InvitationResponseUpdateSerializer(serializers.Serializer):
    """Validate a recipient's explicit answer to an invitation."""

    response_status = serializers.ChoiceField(
        choices=INVITATION_ANSWER_STATUS_CHOICES,
        help_text="The recipient's current answer.",
    )


class AwareFutureDateTimeField(serializers.DateTimeField):
    """Accept only ISO-8601 datetimes with an explicit offset in the future."""

    def to_internal_value(self, value: object) -> datetime:
        """Reject implicit local time before applying DRF datetime normalization."""
        parsed_value = parse_datetime(value) if isinstance(value, str) else None
        if parsed_value is None or is_naive(parsed_value):
            raise serializers.ValidationError(
                "Use an ISO-8601 datetime with an explicit timezone offset."
            )

        normalized_value = super().to_internal_value(value)
        if normalized_value <= now():
            raise serializers.ValidationError("The proposed time must be in the future.")
        return normalized_value


class InvitationPlanOptionInputSerializer(serializers.Serializer):
    """Validate one author-proposed date and place."""

    starts_at = AwareFutureDateTimeField()
    place = serializers.CharField(max_length=200, allow_blank=False, trim_whitespace=True)
    comment = serializers.CharField(
        max_length=500,
        required=False,
        allow_blank=True,
        default="",
        trim_whitespace=True,
    )


class InvitationPlanOptionsUpdateSerializer(serializers.Serializer):
    """Validate an atomic replacement set of two to five ordered options."""

    options = InvitationPlanOptionInputSerializer(
        many=True,
        min_length=2,
        max_length=5,
    )


class InvitationSelectionUpdateSerializer(serializers.Serializer):
    """Validate the recipient's selected option identifier."""

    option_id = serializers.UUIDField()


@extend_schema_field({"type": "boolean", "enum": [True]})
class LiteralTrueBooleanField(serializers.BooleanField):
    """Accept only the literal JSON boolean true and document that restriction."""

    def to_internal_value(self, data: object) -> bool:
        """Reject BooleanField's usual string and numeric coercions."""
        if data is not True:
            raise serializers.ValidationError(
                "Final confirmation accepts only the boolean value true.",
                code="not_true",
            )
        return True


class StrictUUIDField(serializers.UUIDField):
    """Accept UUIDs only in their JSON string representation."""

    def to_internal_value(self, data: object) -> UUID:
        """Reject UUIDField's permissive integer coercion."""
        if not isinstance(data, str):
            raise serializers.ValidationError(
                "Enter a valid UUID string.",
                code="invalid",
            )
        return super().to_internal_value(data)


class InvitationConfirmationSerializer(serializers.Serializer):
    """Validate the author's irreversible confirmation of the shown plan."""

    confirmed = LiteralTrueBooleanField(
        help_text="Must be the literal JSON boolean true; confirmation cannot be undone."
    )
    option_id = StrictUUIDField(
        help_text="The selected date option UUID visible to the author when confirming."
    )
    activity_option_id = StrictUUIDField(
        required=False,
        allow_null=True,
        help_text=(
            "The selected activity option UUID visible to the author, or null when the "
            "invitation has no activity choices."
        ),
    )


class InvitationCreateResponseSerializer(InvitationSerializer):
    """Expose the management capability once, only in the creation response."""

    management_token = serializers.SerializerMethodField(
        help_text="Save this capability now; it cannot be retrieved again.",
    )

    class Meta(InvitationSerializer.Meta):
        """Add the transient token to the normal public invitation fields."""

        fields = InvitationSerializer.Meta.fields + ("management_token",)
        read_only_fields = InvitationSerializer.Meta.read_only_fields + ("management_token",)

    def get_management_token(self, invitation: Invitation) -> str:
        """Read the transient plaintext token passed only by the create view."""
        token = self.context.get("management_token")
        if not isinstance(token, str):
            raise RuntimeError("The creation response requires a management token.")
        return token
