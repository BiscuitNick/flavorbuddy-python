from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from integrations.models import Catalog
from scrape_me.models import StarterRecipe


class Command(BaseCommand):
    help = (
        "Explicitly grant the seeded licensed starter snapshot to a local test catalog."
    )

    def handle(self, *args, **kwargs):
        if settings.PRODUCTION:
            raise CommandError(
                "Production catalogs require operator review; use admin for explicit membership."
            )
        catalog, _ = Catalog.objects.get_or_create(
            slug="starter-local", defaults={"title": "Local licensed starters"}
        )
        recipes = StarterRecipe.objects.filter(
            provenance__license="Unlicense",
            provenance__repository="https://github.com/ronaldl29/public-domain-recipes",
        )
        if not recipes.exists():
            raise CommandError(
                "No Unlicense starters found; seed and inspect provenance first."
            )
        catalog.recipes.set(recipes)
        self.stdout.write(
            f"Local catalog contains {recipes.count()} licensed starters."
        )
