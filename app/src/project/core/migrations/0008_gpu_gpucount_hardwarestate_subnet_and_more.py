# Generated by Django 4.2.11 on 2024-04-25 09:00

import django.db.models.deletion
import django.db.models.functions.text
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0007_validator_runner_version_validator_version"),
    ]

    operations = [
        migrations.CreateModel(
            name="GPU",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                (
                    "capacity",
                    models.PositiveIntegerField(blank=True, default=0, help_text="in MB"),
                ),
            ],
        ),
        migrations.CreateModel(
            name="GpuCount",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("count", models.PositiveIntegerField()),
                (
                    "measured_at",
                    models.DateTimeField(blank=True, default=django.utils.timezone.now),
                ),
            ],
        ),
        migrations.CreateModel(
            name="HardwareState",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("state", models.JSONField()),
                (
                    "measured_at",
                    models.DateTimeField(default=django.utils.timezone.now),
                ),
            ],
        ),
        migrations.CreateModel(
            name="Subnet",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=255)),
                ("uid", models.PositiveSmallIntegerField()),
            ],
        ),
        migrations.AddConstraint(
            model_name="subnet",
            constraint=models.UniqueConstraint(fields=("name",), name="unique_subnet_name"),
        ),
        migrations.AddConstraint(
            model_name="subnet",
            constraint=models.UniqueConstraint(fields=("uid",), name="unique_subnet_uid"),
        ),
        migrations.AddField(
            model_name="hardwarestate",
            name="subnet",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="hardware_states",
                to="core.subnet",
            ),
        ),
        migrations.AddField(
            model_name="gpucount",
            name="gpu",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="counts",
                to="core.gpu",
            ),
        ),
        migrations.AddField(
            model_name="gpucount",
            name="subnet",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="gpu_counts",
                to="core.subnet",
            ),
        ),
        migrations.AddConstraint(
            model_name="gpu",
            constraint=models.UniqueConstraint(
                django.db.models.functions.text.Lower("name"),
                models.F("capacity"),
                name="unique_gpu",
            ),
        ),
        migrations.AddConstraint(
            model_name="gpucount",
            constraint=models.UniqueConstraint(fields=("subnet", "gpu", "measured_at"), name="unique_gpu_count"),
        ),
    ]
