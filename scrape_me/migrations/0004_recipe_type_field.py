from django.db import migrations, models


def set_recipe_types(apps, schema_editor):
    Recipe = apps.get_model("scrape_me", "Recipe")
    Recipe.objects.filter(source_url__isnull=False).update(type="url")
    Recipe.objects.filter(source_url__isnull=True).update(type="user_input")


class Migration(migrations.Migration):

    dependencies = [
        ("scrape_me", "0003_recipe_views"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="recipe",
            name="extra",
        ),
        migrations.AlterField(
            model_name="recipe",
            name="source_url",
            field=models.URLField(blank=True, null=True, unique=True),
        ),
        migrations.AddField(
            model_name="recipe",
            name="type",
            field=models.CharField(
                choices=[
                    ("url", "URL"),
                    ("image_upload", "Image Upload"),
                    ("user_input", "User Input"),
                    ("ai_generated", "AI Generated"),
                ],
                default="user_input",
                max_length=32,
            ),
        ),
        migrations.RunPython(set_recipe_types, migrations.RunPython.noop),
    ]
