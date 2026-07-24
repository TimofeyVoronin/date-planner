"""Add default screen configurations for extended invitations."""

import uuid

import django.db.models.deletion
from django.db import migrations, models


SCREEN_DEFAULTS = (
    (
        "invitation",
        "Ты пойдёшь со мной на свидание?",
        "Для тебя приготовили особенное приглашение 💌",
        "Да! 😍",
        "invitation-default",
    ),
    (
        "acceptance",
        "Ура! 💘",
        "Теперь давай выберем, когда увидимся.",
        "Выбрать дату",
        "acceptance-default",
    ),
    (
        "date_selection",
        "Когда тебе удобно?",
        "Выбери один из предложенных вариантов даты и времени.",
        "Продолжить",
        "date-selection-default",
    ),
    (
        "activity_selection",
        "Чем займёмся?",
        "Выбери вариант, который нравится больше всего.",
        "Продолжить",
        "activity-selection-default",
    ),
    (
        "final",
        "Договорились 💞",
        "Осталось дождаться итогового подтверждения плана.",
        "Посмотреть план",
        "final-default",
    ),
)


def create_missing_extended_invitation_screens(apps, schema_editor) -> None:
    """Backfill complete screen sets without duplicating existing configurations."""
    Invitation = apps.get_model("common", "Invitation")
    InvitationScreen = apps.get_model("common", "InvitationScreen")

    extended_invitations = Invitation.objects.filter(creation_mode="extended").iterator()
    for invitation in extended_invitations:
        existing_types = set(
            InvitationScreen.objects.filter(invitation_id=invitation.pk).values_list(
                "screen_type",
                flat=True,
            )
        )
        InvitationScreen.objects.bulk_create(
            [
                InvitationScreen(
                    invitation_id=invitation.pk,
                    screen_type=screen_type,
                    title=title,
                    subtitle=subtitle,
                    button_text=button_text,
                    image_key=image_key,
                )
                for screen_type, title, subtitle, button_text, image_key in SCREEN_DEFAULTS
                if screen_type not in existing_types
            ],
            ignore_conflicts=True,
        )


def remove_invitation_screens(apps, schema_editor) -> None:
    """Remove screen rows when reversing this feature migration."""
    InvitationScreen = apps.get_model("common", "InvitationScreen")
    InvitationScreen.objects.all().delete()


class Migration(migrations.Migration):
    """Persist the five configurable screens used by the extended builder."""

    dependencies = [
        ("common", "0007_invitation_publication_lifecycle"),
    ]

    operations = [
        migrations.CreateModel(
            name="InvitationScreen",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "screen_type",
                    models.CharField(
                        choices=[
                            ("invitation", "Invitation"),
                            ("acceptance", "Acceptance"),
                            ("date_selection", "Date selection"),
                            ("activity_selection", "Activity selection"),
                            ("final", "Final"),
                        ],
                        max_length=18,
                    ),
                ),
                ("title", models.CharField(max_length=160)),
                ("subtitle", models.CharField(blank=True, default="", max_length=500)),
                ("button_text", models.CharField(blank=True, default="", max_length=80)),
                ("image_key", models.CharField(blank=True, default="", max_length=80)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "invitation",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="screens",
                        to="common.invitation",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="invitationscreen",
            constraint=models.UniqueConstraint(
                fields=("invitation", "screen_type"),
                name="unique_invitation_screen_type",
            ),
        ),
        migrations.AddConstraint(
            model_name="invitationscreen",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    screen_type__in=(
                        "invitation",
                        "acceptance",
                        "date_selection",
                        "activity_selection",
                        "final",
                    )
                ),
                name="invitation_screen_type_valid",
            ),
        ),
        migrations.RunPython(
            create_missing_extended_invitation_screens,
            remove_invitation_screens,
        ),
    ]
