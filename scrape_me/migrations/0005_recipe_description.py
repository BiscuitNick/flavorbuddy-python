from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scrape_me", "0004_recipe_type_field"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="description",
            field=models.TextField(blank=True, default=""),
            preserve_default=False,
        ),
    ]
