import json
from io import StringIO
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient
from scrape_me.models import Recipe, StarterRecipe


class StarterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_starter_recipes", stdout=StringIO())

    def test_snapshot_count_validation_and_repeatable_seed(self):
        catalog = json.loads(
            (settings.BASE_DIR / "data/starter/public-domain-recipes.json").read_text()
        )
        self.assertEqual(catalog["target"], 500)
        self.assertEqual(catalog["available"], 415)
        self.assertEqual(StarterRecipe.objects.count(), 415)
        self.assertEqual(len({r["slug"] for r in catalog["recipes"]}), 415)
        call_command("seed_starter_recipes", stdout=StringIO())
        self.assertEqual(StarterRecipe.objects.count(), 415)
        self.assertEqual(
            Recipe.objects.filter(state="finalized", visibility="public").count(), 415
        )

    def test_public_browsing_never_includes_private_or_legacy_rows(self):
        user = get_user_model().objects.create_user("private")
        Recipe.objects.create(owner=user, title="Secret cake")
        Recipe.objects.create(title="Legacy cake")
        client = APIClient()
        result = client.get("/api/v1/starters").json()
        self.assertEqual(result["count"], 415)
        self.assertEqual(len(result["results"]), 24)
        self.assertEqual(client.get("/api/v1/starters?q=Secret").json()["count"], 0)
        self.assertEqual(client.get("/api/v1/starters?page=0").status_code, 400)
        self.assertEqual(client.get("/api/v1/starters?page=19").json()["results"], [])
        self.assertEqual(
            client.post(
                f"/api/v1/starters/{result['results'][0]['id']}/save", {}, format="json"
            ).status_code,
            403,
        )

    def test_private_copies_and_provenance_survive_catalog_reload(self):
        client = APIClient()
        users = [
            get_user_model().objects.create_user(name) for name in ["alice", "bob"]
        ]
        starter = StarterRecipe.objects.get(slug="apple-pie")
        ids = []
        for user in users:
            client.force_login(user)
            first = client.post(
                f"/api/v1/starters/{starter.pk}/save", {}, format="json"
            )
            self.assertEqual(first.status_code, 201)
            ids.append(first.json()["id"])
            again = client.post(
                f"/api/v1/starters/{starter.pk}/save", {}, format="json"
            )
            self.assertEqual(again.status_code, 200)
            self.assertEqual(first.json()["id"], again.json()["id"])
            self.assertEqual(first.json()["provenance"]["license"], "Unlicense")
        self.assertNotEqual(*ids)
        Recipe.objects.filter(pk=ids[0]).update(
            title="Alice pie", notes="Private adjustment"
        )
        call_command("seed_starter_recipes", stdout=StringIO())
        client.force_login(users[0])
        again = client.post(
            f"/api/v1/starters/{starter.pk}/save", {}, format="json"
        ).json()
        self.assertEqual(again["notes"], "Private adjustment")
        self.assertEqual(
            StarterRecipe.objects.get(pk=starter.pk).content["title"], "Apple Pie"
        )
        client.force_login(users[1])
        self.assertEqual(client.get(f"/api/v1/recipes/{ids[0]}").status_code, 404)
        self.assertEqual(len(client.get("/api/v1/recipes/export").json()["recipes"]), 1)

    def test_group_labels_and_original_content_preserved(self):
        starter = StarterRecipe.objects.get(slug="apple-pie")
        self.assertTrue(
            any(s.startswith("Filling:") for s in starter.content["ingredients"])
        )
        self.assertTrue(
            any(s.startswith("Crust:") for s in starter.content["ingredients"])
        )
        self.assertIn("Prep time", starter.content["notes"])
        self.assertIn("## Ingredients", starter.source_markdown)
        self.assertEqual(len(starter.provenance["revision"]), 40)
