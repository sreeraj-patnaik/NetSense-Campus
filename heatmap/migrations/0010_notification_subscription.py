from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("heatmap", "0009_cellaggregate_signal_variance"),
    ]

    operations = [
        migrations.CreateModel(
            name="NotificationSubscription",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("endpoint", models.TextField(unique=True)),
                ("p256dh", models.CharField(max_length=255)),
                ("auth", models.CharField(max_length=255)),
                ("block", models.CharField(blank=True, max_length=20)),
                ("floor", models.IntegerField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ["-last_seen_at"],
            },
        ),
    ]
