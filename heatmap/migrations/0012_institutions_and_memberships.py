from django.db import migrations, models


def create_default_institution(apps, schema_editor):
    Institution = apps.get_model("heatmap", "Institution")
    Block = apps.get_model("heatmap", "Block")
    default = Institution.objects.create(name="Default Institution", code="default")
    Block.objects.filter(institution__isnull=True).update(institution=default)


def rollback_default_institution(apps, schema_editor):
    Institution = apps.get_model("heatmap", "Institution")
    Block = apps.get_model("heatmap", "Block")
    default = Institution.objects.filter(code="default").first()
    if not default:
        return
    Block.objects.filter(institution=default).update(institution=None)
    default.delete()


class Migration(migrations.Migration):
    dependencies = [
        ("heatmap", "0011_remove_notification_subscription"),
    ]

    operations = [
        migrations.CreateModel(
            name="Institution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=160, unique=True)),
                ("code", models.CharField(max_length=40, unique=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["name"]},
        ),
        migrations.CreateModel(
            name="InstitutionMembership",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pending"), ("approved", "Approved"), ("rejected", "Rejected")], default="pending", max_length=12)),
                ("role", models.CharField(choices=[("member", "Member"), ("admin", "Admin")], default="member", max_length=12)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("approved_at", models.DateTimeField(blank=True, null=True)),
                ("institution", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="memberships", to="heatmap.institution")),
                ("user", models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="institution_memberships", to="auth.user")),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddConstraint(
            model_name="institutionmembership",
            constraint=models.UniqueConstraint(fields=("user", "institution"), name="uniq_institution_membership"),
        ),
        migrations.AddField(
            model_name="block",
            name="institution",
            field=models.ForeignKey(blank=True, null=True, on_delete=models.deletion.SET_NULL, related_name="blocks", to="heatmap.institution"),
        ),
        migrations.RunPython(create_default_institution, rollback_default_institution),
    ]
