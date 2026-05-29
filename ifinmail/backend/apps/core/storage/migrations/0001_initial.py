import uuid

from django.db import migrations, models

import backend.apps.core.storage.models.stored_file


class Migration(migrations.Migration):
    initial = True

    dependencies: list[tuple[str, str]] = []

    operations = [
        migrations.CreateModel(
            name='StoredFile',
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
                (
                    'file',
                    models.FileField(
                        upload_to=backend.apps.core.storage.models.stored_file._upload_to
                    ),
                ),
                ('original_filename', models.CharField(max_length=255)),
                ('content_type', models.CharField(max_length=255)),
                ('size_bytes', models.BigIntegerField()),
                (
                    'entity_type',
                    models.CharField(
                        choices=[
                            ('PRODUCT', 'PRODUCT'),
                            ('USER', 'USER'),
                            ('MESSAGE', 'MESSAGE'),
                            ('DOCUMENT', 'DOCUMENT'),
                        ],
                        max_length=32,
                    ),
                ),
                ('entity_id', models.UUIDField(blank=True, null=True)),
                (
                    'visibility',
                    models.CharField(
                        choices=[
                            ('PRIVATE', 'PRIVATE'),
                            ('INTERNAL', 'INTERNAL'),
                            ('PUBLIC', 'PUBLIC'),
                        ],
                        default='PRIVATE',
                        max_length=16,
                    ),
                ),
            ],
            options={
                'db_table': 'ifinmail_stored_file',
                'ordering': ['-created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='storedfile',
            index=models.Index(
                fields=['entity_type', 'entity_id'],
                name='ifinmail_st_entity_93fa19_idx',
            ),
        ),
    ]
