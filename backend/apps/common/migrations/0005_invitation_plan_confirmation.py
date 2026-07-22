"""Store the irreversible final confirmation on the selected plan option."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Add a nullable confirmation timestamp with a selection consistency check."""

    dependencies = [
        ("common", "0004_invitation_planning"),
    ]

    operations = [
        migrations.AddField(
            model_name="invitationplanoption",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddConstraint(
            model_name="invitationplanoption",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(("confirmed_at__isnull", True))
                    | (
                        models.Q(("selected_at__isnull", False))
                        & models.Q(("confirmed_at__gte", models.F("selected_at")))
                        & models.Q(("confirmed_at__lt", models.F("starts_at")))
                    )
                ),
                name="invitation_plan_confirmation_requires_selection",
            ),
        ),
    ]
