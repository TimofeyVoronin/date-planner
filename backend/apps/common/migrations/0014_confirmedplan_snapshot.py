"""Persist the immutable final-plan snapshot and planning time zone."""

import uuid
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import django.db.models.deletion
from django.db import migrations, models


DEFAULT_FINAL_TEXT_TEMPLATE = (
    "{recipient}, жду тебя {date} в {time}. "
    "Встречаемся в {place}, а дальше нас ждёт {activity} 💘"
)
RUSSIAN_MONTH_NAMES = (
    "января",
    "февраля",
    "марта",
    "апреля",
    "мая",
    "июня",
    "июля",
    "августа",
    "сентября",
    "октября",
    "ноября",
    "декабря",
)


def render_template(template: str, values: dict[str, str]) -> str:
    """Render the already validated historical template without executing expressions."""
    rendered = template.replace("{{", "\0").replace("}}", "\1")
    for variable, value in values.items():
        rendered = rendered.replace(f"{{{variable}}}", value)
    return rendered.replace("\0", "{").replace("\1", "}")


def backfill_confirmed_plans(apps, schema_editor) -> None:
    """Snapshot every plan that was already confirmed before this migration."""
    Invitation = apps.get_model("common", "Invitation")
    InvitationScreen = apps.get_model("common", "InvitationScreen")
    InvitationPlanOption = apps.get_model("common", "InvitationPlanOption")
    ActivityOption = apps.get_model("common", "ActivityOption")
    ConfirmedPlan = apps.get_model("common", "ConfirmedPlan")

    selected_options = InvitationPlanOption.objects.filter(
        confirmed_at__isnull=False,
        selected_at__isnull=False,
    ).select_related("invitation")

    for option in selected_options.iterator():
        invitation = option.invitation
        activity = ActivityOption.objects.filter(
            invitation_id=invitation.pk,
            selected_at__isnull=False,
        ).first()
        final_screen = None
        if invitation.creation_mode == "extended":
            final_screen = InvitationScreen.objects.filter(
                invitation_id=invitation.pk,
                screen_type="final",
            ).first()
        time_zone = option.time_zone or "UTC"
        try:
            localized = option.starts_at.astimezone(ZoneInfo(time_zone))
        except (ValueError, ZoneInfoNotFoundError):
            time_zone = "UTC"
            localized = option.starts_at.astimezone(ZoneInfo("UTC"))

        values = {
            "author": invitation.author_name or "Автор приглашения",
            "recipient": invitation.recipient_name or "Получатель приглашения",
            "date": (
                f"{localized.day} {RUSSIAN_MONTH_NAMES[localized.month - 1]} "
                f"{localized.year}"
            ),
            "time": f"{localized:%H:%M} ({time_zone})",
            "place": option.place or "в выбранном месте",
            "activity": activity.title if activity is not None else "приятное свидание",
        }
        template = (
            final_screen.template_text
            if final_screen is not None and final_screen.template_text
            else DEFAULT_FINAL_TEXT_TEMPLATE
        )
        ConfirmedPlan.objects.get_or_create(
            invitation_id=invitation.pk,
            defaults={
                "option_id": option.pk,
                "activity_option_id": activity.pk if activity is not None else None,
                "starts_at": option.starts_at,
                "time_zone": time_zone,
                "place": option.place,
                "comment": option.comment,
                "activity_title": activity.title if activity is not None else "",
                "activity_description": activity.description if activity is not None else "",
                "activity_place": activity.place if activity is not None else "",
                "activity_image_key": activity.image_key if activity is not None else "",
                "final_title": final_screen.title if final_screen is not None else "Договорились 💞",
                "final_subtitle": (
                    final_screen.subtitle
                    if final_screen is not None
                    else "Осталось дождаться итогового подтверждения плана."
                ),
                "final_image_key": final_screen.image_key if final_screen is not None else "final-default",
                "final_text": render_template(template, values),
                "confirmed_at": option.confirmed_at,
            },
        )


def clear_confirmed_plans(apps, schema_editor) -> None:
    """Delete snapshots before reversing the model creation."""
    ConfirmedPlan = apps.get_model("common", "ConfirmedPlan")
    ConfirmedPlan.objects.all().delete()


class Migration(migrations.Migration):
    """Add stable time-zone metadata and one immutable final snapshot per invitation."""

    dependencies = [
        ("common", "0013_invitationscreen_template_text"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitationplanoption",
            name="time_zone",
            field=models.CharField(default="UTC", max_length=64),
        ),
        migrations.CreateModel(
            name="ConfirmedPlan",
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
                ("option_id", models.UUIDField()),
                ("activity_option_id", models.UUIDField(blank=True, null=True)),
                ("starts_at", models.DateTimeField()),
                ("time_zone", models.CharField(default="UTC", max_length=64)),
                ("place", models.CharField(max_length=200)),
                ("comment", models.CharField(blank=True, default="", max_length=500)),
                ("activity_title", models.CharField(blank=True, default="", max_length=120)),
                (
                    "activity_description",
                    models.CharField(blank=True, default="", max_length=500),
                ),
                ("activity_place", models.CharField(blank=True, default="", max_length=200)),
                (
                    "activity_image_key",
                    models.CharField(blank=True, default="", max_length=80),
                ),
                ("final_title", models.CharField(max_length=160)),
                ("final_subtitle", models.CharField(blank=True, default="", max_length=500)),
                ("final_image_key", models.CharField(blank=True, default="", max_length=80)),
                ("final_text", models.TextField()),
                ("confirmed_at", models.DateTimeField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "invitation",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="confirmed_plan",
                        to="common.invitation",
                    ),
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="confirmedplan",
            constraint=models.CheckConstraint(
                condition=models.Q(confirmed_at__lt=models.F("starts_at")),
                name="confirmed_plan_precedes_start",
            ),
        ),
        migrations.RunPython(backfill_confirmed_plans, clear_confirmed_plans),
    ]
