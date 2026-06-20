from __future__ import annotations

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("jukebox", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="jukeboxqueueitem",
            name="status",
            field=models.CharField(
                choices=[
                    ("queued", "Queued"),
                    ("playing", "Playing"),
                    ("played", "Played"),
                ],
                db_index=True,
                default="queued",
                max_length=16,
                verbose_name="Status",
            ),
        ),
    ]
