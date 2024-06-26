# Generated by Django 4.2.11 on 2024-04-02 08:53

import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_channel_last_heartbeat"),
    ]

    operations = [
        migrations.AddField(
            model_name="job",
            name="output_download_url_expires_at",
            field=models.DateTimeField(blank=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
    ]
