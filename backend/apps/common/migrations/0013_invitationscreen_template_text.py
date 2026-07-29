"""Store a safe variable template for the final invitation screen."""

from django.db import migrations, models


DEFAULT_FINAL_TEXT_TEMPLATE = (
    "{recipient}, жду тебя {date} в {time}. "
    "Встречаемся в {place}, а дальше нас ждёт {activity} 💘"
)


def backfill_final_screen_template(apps, schema_editor) -> None:
    """Give existing final screens the stable default template."""
    InvitationScreen = apps.get_model("common", "InvitationScreen")
    InvitationScreen.objects.filter(
        screen_type="final",
        template_text="",
    ).update(template_text=DEFAULT_FINAL_TEXT_TEMPLATE)


def clear_final_screen_template(apps, schema_editor) -> None:
    """Clear the final template before reversing the added field."""
    InvitationScreen = apps.get_model("common", "InvitationScreen")
    InvitationScreen.objects.filter(screen_type="final").update(template_text="")


class Migration(migrations.Migration):
    """Persist and backfill the safe final-message template."""

    dependencies = [
        ("common", "0012_activityoption_selected_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitationscreen",
            name="template_text",
            field=models.TextField(blank=True, default="", max_length=1000),
        ),
        migrations.RunPython(
            backfill_final_screen_template,
            clear_final_screen_template,
        ),
        migrations.AddConstraint(
            model_name="invitationscreen",
            constraint=models.CheckConstraint(
                condition=models.Q(screen_type="final") | models.Q(template_text=""),
                name="nonfinal_invitation_screen_template_empty",
            ),
        ),
    ]
