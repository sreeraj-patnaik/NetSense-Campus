from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("heatmap", "0014_userdashboardpreference"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="institutionmembership",
            constraint=models.UniqueConstraint(
                fields=("user",),
                condition=models.Q(status="approved"),
                name="uniq_approved_membership_per_user",
            ),
        ),
    ]
