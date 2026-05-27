import uuid

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies: list = []

    operations = [
        migrations.CreateModel(
            name="AuditEvent",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("time", models.DateTimeField(auto_now_add=True)),
                ("user", models.CharField(max_length=255)),
                ("action", models.CharField(max_length=255)),
                ("detail", models.TextField(blank=True)),
                ("severity", models.CharField(default="info", max_length=32)),
            ],
            options={
                "db_table": "ifinmail_audit_event",
                "ordering": ["-time"],
                "managed": True,
            },
        ),
    ]
