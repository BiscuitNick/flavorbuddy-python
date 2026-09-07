"""Rehearse the lifecycle backfill on a disposable PostgreSQL database."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class LifecycleMigrationTests(TransactionTestCase):
    def test_existing_private_work_and_public_aliases_survive(self):
        executor = MigrationExecutor(connection)
        old_target = [("scrape_me", "0009_cookingcompletion_recipe_snapshot_and_more")]
        new_target = [("scrape_me", "0010_recipe_lifecycle")]
        executor.migrate(old_target)
        try:
            apps = executor.loader.project_state(old_target).apps
            User = apps.get_model("auth", "User")
            Recipe = apps.get_model("scrape_me", "Recipe")
            Starter = apps.get_model("scrape_me", "StarterRecipe")
            owner = User.objects.create(username="migration-owner")
            old = Recipe.objects.create(
                owner=owner,
                title="My private recipe",
                ingredients=["Salt"],
                instructions=["Mix"],
                notes="Private note",
                favorite=True,
                version=9,
            )
            unfinished = Recipe.objects.create(
                owner=owner, title="Unfinished", ingredients=[], instructions=[]
            )
            legacy = Recipe.objects.create(
                title="Unowned", ingredients=["Salt"], instructions=["Mix"]
            )
            source = Starter.objects.create(
                slug="legacy-link",
                title="Public original",
                content={
                    "title": "Public original",
                    "ingredients": ["1 cup water"],
                    "instructions": ["Pour."],
                    "notes": "Source timing text",
                },
                provenance={"license": "Unlicense"},
                source_markdown="untouched markdown",
            )
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(new_target)
        from scrape_me.models import Recipe, StarterRecipe

        migrated = Recipe.objects.get(pk=old.pk)
        self.assertEqual(
            (migrated.owner_id, migrated.notes, migrated.favorite, migrated.version),
            (owner.pk, "Private note", True, 9),
        )
        self.assertEqual(
            (migrated.state, migrated.visibility), ("finalized", "private")
        )
        self.assertEqual(Recipe.objects.get(pk=unfinished.pk).state, "draft")
        self.assertEqual(Recipe.objects.get(pk=legacy.pk).visibility, "private")
        alias = StarterRecipe.objects.get(pk=source.pk)
        self.assertEqual(alias.slug, "legacy-link")
        self.assertEqual(alias.recipe.source_markdown, "untouched markdown")
        self.assertEqual(alias.recipe.provenance["source_notes"], "Source timing text")
        self.assertEqual(
            (alias.recipe.state, alias.recipe.visibility), ("finalized", "public")
        )
        self.assertEqual(
            len(set(Recipe.objects.values_list("public_id", flat=True))), 4
        )
