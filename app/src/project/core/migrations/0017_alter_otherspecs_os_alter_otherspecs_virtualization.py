# Generated by Django 4.2.11 on 2024-05-24 10:35

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0016_remove_rawspecsdata_core_rawspe_data_e05b87_hash_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="otherspecs",
            name="os",
            field=models.CharField(blank=True, default="", max_length=255, null=True),
        ),
        migrations.AlterField(
            model_name="otherspecs",
            name="virtualization",
            field=models.CharField(blank=True, default="", max_length=255, null=True),
        ),
    ]
