from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("scrape_me", "0002_remove_recipe_short_url"),
    ]

    operations = [
        migrations.AddField(
            model_name="recipe",
            name="views",
            field=models.PositiveIntegerField(default=0),
        ),
    ]
