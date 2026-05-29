import uuid

from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name='Device',
            fields=[
                (
                    'id',
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('name', models.CharField(max_length=255)),
                ('device_type', models.CharField(blank=True, default='', max_length=64)),
                ('identifier', models.CharField(max_length=512, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('last_seen', models.DateTimeField(blank=True, null=True)),
            ],
            options={
                'ordering': ['-last_seen'],
            },
        ),
    ]
