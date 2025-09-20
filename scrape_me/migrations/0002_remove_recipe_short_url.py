from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("scrape_me", "0001_initial"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="recipe",
            name="short_url",
        ),
    ]
