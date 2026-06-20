from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("menu", "0001_initial"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="product",
            index=models.Index(
                fields=["is_available", "sort_order", "name"],
                name="menu_product_is_avail_08943b_idx",
            ),
        ),
    ]
