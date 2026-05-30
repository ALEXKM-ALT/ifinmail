from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('domains', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='domain',
            name='ip_address',
            field=models.GenericIPAddressField(blank=True, null=True),
        ),
    ]
