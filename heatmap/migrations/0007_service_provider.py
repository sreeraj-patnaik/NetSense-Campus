from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("heatmap", "0006_floorplan_fk_and_interpolation"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=60)),
                ("mode", models.CharField(choices=[("wifi", "WiFi"), ("mobile", "Mobile")], default="wifi", max_length=10)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["mode", "name"],
            },
        ),
        migrations.AddConstraint(
            model_name="serviceprovider",
            constraint=models.UniqueConstraint(fields=("mode", "name"), name="uniq_service_provider_mode_name"),
        ),
    ]
