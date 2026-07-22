"""Serializers for common API responses."""

from rest_framework import serializers

from apps.common.models import Invitation


class HealthResponseSerializer(serializers.Serializer):
    """Describe the health endpoint response."""

    status = serializers.CharField(read_only=True)
    service = serializers.CharField(read_only=True)


class InvitationSerializer(serializers.ModelSerializer):
    """Validate invitation input and expose its public representation."""

    class Meta:
        """Configure persisted and read-only invitation fields."""

        model = Invitation
        fields = (
            "id",
            "author_name",
            "recipient_name",
            "message",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")
        extra_kwargs = {
            "author_name": {"min_length": 1, "trim_whitespace": True},
            "recipient_name": {"min_length": 1, "trim_whitespace": True},
            "message": {"min_length": 1, "trim_whitespace": True},
        }


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
