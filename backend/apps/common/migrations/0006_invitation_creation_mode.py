"""Store whether an invitation uses the quick or extended authoring flow."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add the creation mode with a safe default for existing invitations."""

    dependencies = [
        ("common", "0005_invitation_plan_confirmation"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitation",
            name="creation_mode",
            field=models.CharField(
                choices=[("quick", "Quick"), ("extended", "Extended")],
                default="quick",
                max_length=8,
            ),
        ),
        migrations.AddConstraint(
            model_name="invitation",
            constraint=models.CheckConstraint(
                condition=models.Q(("creation_mode__in", ("quick", "extended"))),
                name="invitation_creation_mode_valid",
            ),
        ),
    ]
