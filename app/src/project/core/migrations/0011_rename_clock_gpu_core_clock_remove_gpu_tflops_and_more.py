# Generated by Django 4.2.11 on 2024-05-01 12:34

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_minergpuspecs_minerspecs_rawspecssnapshot_gpu_clock_and_more"),
    ]

    operations = [
        migrations.RenameField(
            model_name="gpu",
            old_name="clock",
            new_name="core_clock",
        ),
        migrations.RemoveField(
            model_name="gpu",
            name="tflops",
        ),
        migrations.AddField(
            model_name="gpu",
            name="bus_width",
            field=models.PositiveIntegerField(default=0, help_text="in bits"),
        ),
        migrations.AddField(
            model_name="gpu",
            name="fp16",
            field=models.FloatField(default=0, help_text="in TFLOPS"),
        ),
        migrations.AddField(
            model_name="gpu",
            name="fp32",
            field=models.FloatField(default=0, help_text="in TFLOPS"),
        ),
        migrations.AddField(
            model_name="gpu",
            name="fp64",
            field=models.FloatField(default=0, help_text="in TFLOPS"),
        ),
        migrations.AddField(
            model_name="gpu",
            name="memory_clock",
            field=models.PositiveIntegerField(default=0, help_text="in MHz"),
        ),
    ]
