import json
from pathlib import Path
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from scrape_me.models import StarterRecipe
from scrape_me.api.serializers import RecipeSerializer


class Command(BaseCommand):
    help = "Load the pinned public starter catalog; never modify private recipes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=Path,
            default=settings.BASE_DIR / "data/starter/public-domain-recipes.json",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        catalog = json.loads(options["file"].read_text())
        created = 0
        for row in catalog["recipes"]:
            serializer = RecipeSerializer(data=row["content"])
            if not serializer.is_valid():
                raise CommandError(
                    f"Invalid starter {row['slug']}: {serializer.errors}"
                )
            if row["provenance"].get("license") != "Unlicense" or not row[
                "provenance"
            ].get("revision"):
                raise CommandError("Seed provenance and license are required.")
            existing = StarterRecipe.objects.filter(slug=row["slug"]).first()
            content = dict(serializer.validated_data)
            provenance = dict(row["provenance"])
            media = existing.provenance.get("image_storage") if existing else None
            if media and media.get("source_url") == content.get("image"):
                content["image"] = existing.content["image"]
                provenance["image_storage"] = media
            if existing:
                # Compare source fields, allowing already migrated image storage metadata.
                existing_validator = RecipeSerializer(
                    data={**existing.content, "image": row["content"].get("image", "")}
                )
                existing_validator.is_valid(raise_exception=True)
                if (
                    {
                        **dict(existing_validator.validated_data),
                        "image": existing.content.get("image", ""),
                    }
                    != content
                    or existing.source_markdown != row["source_markdown"]
                    or existing.provenance != provenance
                ):
                    raise CommandError(
                        f"{row['slug']} already identifies a recipe. Changed content needs a new slug/recipe; it cannot overwrite the old link."
                    )
                starter, new = existing, False
            else:
                starter, new = (
                    StarterRecipe.objects.create(
                        slug=row["slug"],
                        title=content["title"],
                        content=content,
                        provenance=provenance,
                        source_markdown=row["source_markdown"],
                    ),
                    True,
                )
            from scrape_me.services.starter_identity import attach_recipe

            attach_recipe(starter)
            created += new
        self.stdout.write(
            f"Loaded {len(catalog['recipes'])} starters ({created} new). Requested target: {catalog['target']}; source available: {catalog['available']}."
        )
