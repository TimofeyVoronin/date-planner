"""Serializers for common API responses."""

from datetime import datetime
from uuid import UUID

from django.utils.dateparse import parse_datetime
from django.utils.timezone import is_naive, now
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.common.models import (
    INVITATION_ANSWER_STATUS_CHOICES,
    Invitation,
    InvitationPlanOption,
)


class HealthResponseSerializer(serializers.Serializer):
    """Describe the health endpoint response."""

    status = serializers.CharField(read_only=True)
    service = serializers.CharField(read_only=True)


class InvitationPlanOptionSerializer(serializers.ModelSerializer):
    """Expose one persisted planning option in its stable submitted position."""

    class Meta:
        """Expose only recipient-facing option fields."""

        model = InvitationPlanOption
        fields = ("id", "starts_at", "place", "comment", "position")
        read_only_fields = fields


class InvitationSerializer(serializers.ModelSerializer):
    """Validate invitation input and expose its public representation."""

    plan_options = InvitationPlanOptionSerializer(many=True, read_only=True)
    selected_option_id = serializers.UUIDField(read_only=True, allow_null=True)
    selected_at = serializers.DateTimeField(read_only=True, allow_null=True)
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
            "publication_status",
            "published_at",
            "response_status",
            "responded_at",
            "plan_options",
            "selected_option_id",
            "selected_at",
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
            "plan_options",
            "selected_option_id",
            "selected_at",
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
        }

    @extend_schema_field(serializers.DateTimeField())
    def get_server_now(self, invitation: Invitation) -> datetime:
        """Return a non-persisted server-clock snapshot for client expiry decisions."""
        return now()


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
    """Validate the author's irreversible final confirmation."""

    confirmed = LiteralTrueBooleanField(
        help_text="Must be the literal JSON boolean true; confirmation cannot be undone."
    )
    option_id = StrictUUIDField(
        help_text="The selected option UUID visible to the author when confirming."
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
