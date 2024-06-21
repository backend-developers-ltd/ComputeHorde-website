# Generated by Django 4.2.13 on 2024-06-03 15:39

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0018_add_specs_materialized_views"),
    ]

    operations = [
        migrations.AddField(
            model_name="userpreferences",
            name="exclusive",
            field=models.BooleanField(
                default=False,
                help_text="If set only preference miners/validators are used. Error rised if unavailable.",
            ),
        ),
    ]
