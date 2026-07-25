"""Store the secondary invitation-screen action label."""

from django.db import migrations, models


def backfill_invitation_secondary_button(apps, schema_editor) -> None:
    """Give existing invitation screens the default decline label."""
    InvitationScreen = apps.get_model("common", "InvitationScreen")
    InvitationScreen.objects.filter(
        screen_type="invitation",
        secondary_button_text="",
    ).update(secondary_button_text="Нет")


def clear_invitation_secondary_button(apps, schema_editor) -> None:
    """Restore the neutral value before reversing the added field."""
    InvitationScreen = apps.get_model("common", "InvitationScreen")
    InvitationScreen.objects.filter(screen_type="invitation").update(
        secondary_button_text=""
    )


class Migration(migrations.Migration):
    """Add the independently editable text for the invitation's secondary action."""

    dependencies = [
        ("common", "0008_invitation_screen_config"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitationscreen",
            name="secondary_button_text",
            field=models.CharField(blank=True, default="", max_length=80),
        ),
        migrations.RunPython(
            backfill_invitation_secondary_button,
            clear_invitation_secondary_button,
        ),
    ]
