"""Serializers for common API responses."""

from rest_framework import serializers


class HealthResponseSerializer(serializers.Serializer):
    """Describe the health endpoint response."""

    status = serializers.CharField(read_only=True)
    service = serializers.CharField(read_only=True)
