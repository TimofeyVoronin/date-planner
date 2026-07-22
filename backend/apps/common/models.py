"""Database models shared by the invitation API."""

import uuid
from datetime import datetime

from django.db import models


class Invitation(models.Model):
    """A personal invitation that can be shared through an unguessable UUID."""

    class CreationMode(models.TextChoices):
        """Supported authoring flows for an invitation."""

        QUICK = "quick", "Quick"
        EXTENDED = "extended", "Extended"

    class ResponseStatus(models.TextChoices):
        """Allowed lifecycle states for a recipient's response."""

        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        DECLINED = "declined", "Declined"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    author_name = models.CharField(max_length=100)
    recipient_name = models.CharField(max_length=100)
    message = models.TextField(max_length=1000, blank=True, default="")
    creation_mode = models.CharField(
        max_length=8,
        choices=CreationMode.choices,
        default=CreationMode.QUICK,
    )
    management_token_hash = models.CharField(
        max_length=64,
        blank=True,
        default="",
        editable=False,
    )
    response_status = models.CharField(
        max_length=8,
        choices=ResponseStatus.choices,
        default=ResponseStatus.PENDING,
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Keep the response state and its timestamp consistent in the database."""

        constraints = [
            models.CheckConstraint(
                condition=models.Q(creation_mode__in=("quick", "extended")),
                name="invitation_creation_mode_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        response_status="pending",
                        responded_at__isnull=True,
                    )
                    | models.Q(
                        response_status__in=(
                            "accepted",
                            "declined",
                        ),
                        responded_at__isnull=False,
                    )
                ),
                name="invitation_response_state_consistent",
            ),
        ]

    @property
    def selected_plan_option(self) -> "InvitationPlanOption | None":
        """Return the structurally owned selected option, if one exists."""
        cache_attribute = "_selected_plan_option_cache"
        if not hasattr(self, cache_attribute):
            selected_option = self.plan_options.filter(selected_at__isnull=False).first()
            setattr(self, cache_attribute, selected_option)
        return getattr(self, cache_attribute)

    @property
    def selected_option_id(self) -> uuid.UUID | None:
        """Expose the selected option UUID for API serialization."""
        selected_option = self.selected_plan_option
        return selected_option.pk if selected_option is not None else None

    @property
    def selected_at(self) -> datetime | None:
        """Expose the selection timestamp stored on the selected option."""
        selected_option = self.selected_plan_option
        return selected_option.selected_at if selected_option is not None else None

    @property
    def confirmed_at(self) -> datetime | None:
        """Expose the final confirmation timestamp stored on the selected option."""
        selected_option = self.selected_plan_option
        return selected_option.confirmed_at if selected_option is not None else None

    def __str__(self) -> str:
        """Return a concise human-readable representation."""
        return f"{self.author_name} → {self.recipient_name}"


class InvitationPlanOption(models.Model):
    """One ordered date and place proposed for an accepted invitation."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invitation = models.ForeignKey(
        Invitation,
        on_delete=models.CASCADE,
        related_name="plan_options",
    )
    starts_at = models.DateTimeField()
    place = models.CharField(max_length=200)
    comment = models.CharField(max_length=500, blank=True, default="")
    position = models.PositiveSmallIntegerField()
    selected_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        """Keep each invitation's options in their submitted order."""

        ordering = ("position",)
        constraints = [
            models.UniqueConstraint(
                fields=("invitation", "position"),
                name="unique_invitation_plan_option_position",
            ),
            models.CheckConstraint(
                condition=models.Q(position__gte=0, position__lte=4),
                name="invitation_plan_option_position_range",
            ),
            models.UniqueConstraint(
                fields=("invitation",),
                condition=models.Q(selected_at__isnull=False),
                name="unique_selected_plan_option_per_invitation",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(confirmed_at__isnull=True)
                    | (
                        models.Q(selected_at__isnull=False)
                        & models.Q(confirmed_at__gte=models.F("selected_at"))
                        & models.Q(confirmed_at__lt=models.F("starts_at"))
                    )
                ),
                name="invitation_plan_confirmation_requires_selection",
            ),
        ]

    def __str__(self) -> str:
        """Return a concise description for diagnostics and admin tools."""
        return f"{self.invitation_id}: {self.starts_at} at {self.place}"


INVITATION_RESPONSE_STATUS_CHOICES = Invitation.ResponseStatus.choices
INVITATION_ANSWER_STATUS_CHOICES = (
    (
        Invitation.ResponseStatus.ACCEPTED.value,
        Invitation.ResponseStatus.ACCEPTED.label,
    ),
    (
        Invitation.ResponseStatus.DECLINED.value,
        Invitation.ResponseStatus.DECLINED.label,
    ),
)
