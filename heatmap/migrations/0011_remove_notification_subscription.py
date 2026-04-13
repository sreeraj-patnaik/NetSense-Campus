from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("heatmap", "0010_notification_subscription"),
    ]

    operations = [
        migrations.DeleteModel(
            name="NotificationSubscription",
        ),
    ]
