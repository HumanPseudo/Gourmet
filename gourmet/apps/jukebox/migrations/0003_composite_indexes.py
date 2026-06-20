from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("jukebox", "0002_jukeboxqueueitem_status"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="jukeboxqueueitem",
            index=models.Index(
                fields=["status", "sort_order", "created_at"],
                name="jukebox_jukeb_statu_1f8e81_idx",
            ),
        ),
    ]
