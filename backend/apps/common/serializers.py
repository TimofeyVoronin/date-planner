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
