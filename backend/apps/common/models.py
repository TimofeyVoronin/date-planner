"""Database models shared by the invitation API."""

import uuid

from django.db import models


class Invitation(models.Model):
    """A personal invitation that can be shared through an unguessable UUID."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_name = models.CharField(max_length=100)
    recipient_name = models.CharField(max_length=100)
    message = models.TextField(max_length=1000)
    management_token_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self) -> str:
        """Return a concise human-readable representation."""
        return f"{self.author_name} → {self.recipient_name}"
