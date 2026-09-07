from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient
from scrape_me.models import Recipe

CONTENT = {
    "title": "Meatballs",
    "ingredients": ["Ground beef"],
    "instructions": ["Mix and shape."],
    "source_url": "https://example.com/meatballs",
}


class LifecycleTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("owner")
        self.other = get_user_model().objects.create_user("other")
        self.client = APIClient()
        self.client.force_login(self.user)

    def post(self, path, body):
        return self.client.post("/api/v1/" + path, body, format="json")

    def create(self, **extra):
        result = self.post("recipes", {**CONTENT, **extra})
        self.assertEqual(result.status_code, 201, result.content)
        return result.json()

    def test_incomplete_draft_stays_private(self):
        draft = self.create(title="", ingredients=[], instructions=[])
        self.assertEqual(draft["state"], "draft")
        self.assertEqual(
            self.post(f"recipes/{draft['id']}/finalize", {"version": 1}).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                f"recipes/{draft['id']}/visibility",
                {"version": 1, "visibility": "public"},
            ).status_code,
            409,
        )
        self.assertEqual(self.client.get("/api/v1/shared-recipes").json()["count"], 0)
        self.assertEqual(
            self.post(
                "recipes", {**CONTENT, "state": "finalized", "visibility": "public"}
            ).status_code,
            400,
        )

    def test_finalize_share_variation_identity_and_privacy(self):
        draft = self.create(notes="private note", favorite=True)
        recipe = self.post(f"recipes/{draft['id']}/finalize", {"version": 1}).json()
        self.assertEqual(recipe["public_id"], draft["public_id"])
        self.assertEqual(
            (recipe["state"], recipe["visibility"]), ("finalized", "private")
        )
        self.assertEqual(
            self.post(f"recipes/{draft['id']}/finalize", {"version": 1}).status_code,
            200,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/recipes/{draft['id']}",
                {"version": 2, "title": "changed"},
                format="json",
            ).status_code,
            409,
        )
        shared = self.post(
            f"recipes/{draft['id']}/visibility", {"version": 2, "visibility": "public"}
        ).json()
        anonymous = APIClient()
        link = "/api/v1/shared-recipes/" + shared["public_id"]
        public = anonymous.get(link).json()
        self.assertEqual(public["title"], CONTENT["title"])
        for field in ("notes", "favorite", "private_cover", "owner", "version"):
            self.assertNotIn(field, public)
        variation = self.post(f"recipes/{draft['id']}/variations", {}).json()
        self.assertNotEqual(variation["public_id"], draft["public_id"])
        self.assertEqual(variation["inspired_by_recipe_id"], draft["public_id"])
        self.assertEqual(
            (
                variation["state"],
                variation["visibility"],
                variation["notes"],
                variation["favorite"],
            ),
            ("draft", "private", "", False),
        )
        self.assertEqual(
            self.client.patch(
                f"/api/v1/recipes/{variation['id']}",
                {"version": 1, "title": "Variation"},
                format="json",
            ).status_code,
            200,
        )
        self.assertEqual(anonymous.get(link).json(), public)
        self.assertEqual(
            self.post(
                f"recipes/{draft['id']}/visibility",
                {"version": 3, "visibility": "private"},
            ).status_code,
            200,
        )
        self.assertEqual(anonymous.get(link).status_code, 404)
        self.assertEqual(self.client.get(link).status_code, 200)

    def test_other_user_denied_and_notes_editable(self):
        recipe = self.create(state="finalized")
        self.client.force_login(self.other)
        for action in ("finalize", "visibility", "variations"):
            self.assertEqual(
                self.post(
                    f"recipes/{recipe['id']}/{action}",
                    {"version": 1, "visibility": "public"},
                ).status_code,
                404,
            )
        self.assertEqual(
            self.client.get(
                "/api/v1/shared-recipes/" + recipe["public_id"]
            ).status_code,
            404,
        )
        self.client.force_login(self.user)
        result = self.client.patch(
            f"/api/v1/recipes/{recipe['id']}",
            {"version": 1, "notes": "Less salt", "favorite": True},
            format="json",
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.json()["title"], CONTENT["title"])

    def test_database_blocks_mutation_and_hard_delete(self):
        recipe = Recipe.objects.create(owner=self.user, state="finalized", **CONTENT)
        for update in (
            {"title": "tampered"},
            {"ingredients": ["Other"]},
            {"state": "draft", "finalized_at": None},
            {"provenance": {"fake": True}},
            {"inspired_by_id": recipe.id},
        ):
            with self.assertRaises(IntegrityError), transaction.atomic():
                Recipe.objects.filter(pk=recipe.pk).update(**update)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Recipe.objects.filter(pk=recipe.pk).delete()
        Recipe.objects.filter(pk=recipe.pk).update(notes="Allowed", visibility="public")
        recipe.refresh_from_db()
        self.assertEqual(recipe.title, CONTENT["title"])

    def test_distinct_same_source_and_archive_tombstone(self):
        first = self.create(state="finalized")
        second = self.create(state="finalized")
        self.assertNotEqual(first["id"], second["id"])
        self.post(
            f"recipes/{first['id']}/visibility", {"version": 1, "visibility": "public"}
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/recipes/{first['id']}").status_code, 204
        )
        self.assertTrue(Recipe.objects.filter(pk=first["id"]).exists())
        self.assertEqual(
            APIClient().get("/api/v1/shared-recipes/" + first["public_id"]).status_code,
            410,
        )
        self.assertEqual(self.client.get("/api/v1/recipes").json()["count"], 1)

    def test_database_cannot_finalize_an_incomplete_draft(self):
        from django.utils import timezone

        draft = Recipe.objects.create(owner=self.user)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Recipe.objects.filter(pk=draft.pk).update(
                state="finalized", finalized_at=timezone.now()
            )

    def test_changed_seed_preserves_original(self):
        import tempfile, json
        from pathlib import Path
        from io import StringIO
        from django.core.management import call_command
        from django.core.management.base import CommandError
        from scrape_me.models import StarterRecipe

        row = {
            "slug": "meatballs",
            "content": CONTENT,
            "provenance": {"license": "Unlicense", "revision": "fixture"},
            "source_markdown": "original source",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "seed.json"

            def seed():
                path.write_text(
                    json.dumps({"recipes": [row], "target": 1, "available": 1})
                )
                call_command("seed_starter_recipes", file=path, stdout=StringIO())

            seed()
            original = StarterRecipe.objects.get(slug="meatballs").recipe
            seed()
            self.assertEqual(Recipe.objects.count(), 1)
            row["content"] = {**CONTENT, "title": "Replacement"}
            with self.assertRaises(CommandError):
                seed()
            original.refresh_from_db()
            self.assertEqual(original.title, CONTENT["title"])
