from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("heatmap", "0012_institutions_and_memberships"),
    ]

    operations = [
        migrations.AddField(
            model_name="institutionmembership",
            name="can_scan",
            field=models.BooleanField(default=False),
        ),
    ]
