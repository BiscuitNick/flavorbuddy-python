from datetime import timedelta
import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import AccessToken
from scrape_me.models import Recipe, StarterRecipe
from scrape_me.services.starter_identity import attach_recipe
from .documents import document_validator
from .models import AppAudit, Catalog
from .tests import Setup

BASE = "/api/integrations/v2/"


@override_settings(
    CATALOG_AUDIENCE="http://testserver/api/integrations/v1/",
    CATALOG_V2_AUDIENCE="http://testserver/api/integrations/v2/",
)
class V2Tests(Setup, TestCase):
    def setUp(self):
        super().setUp()
        self.token = self.issue(resource=settings.CATALOG_V2_AUDIENCE).json()[
            "access_token"
        ]
        self.grant.minute_limit = 200
        self.grant.save()

    def read(self, path="catalogs/approved/recipes", **params):
        return self.client.get(
            BASE + path, params, HTTP_AUTHORIZATION="Bearer " + self.token
        )

    def add(self, title, ingredients=None, time=None, grant=True):
        starter = StarterRecipe.objects.create(
            slug=f"recipe-{StarterRecipe.objects.count()}",
            title=title,
            content={
                "title": title,
                "ingredients": ingredients or ["Salt"],
                "instructions": ["Stir", "Serve"],
                "total_time": time,
            },
            provenance={"license": "CC0"},
        )
        recipe = attach_recipe(starter)
        if grant:
            self.catalog.recipes.add(starter)
        return recipe

    def test_search_shared_phrase_semantics_and_grants(self):
        ingredient_match = self.add("Lunch", ["2 cups Pasta"])
        self.add("Secret Pasta", grant=False)
        results = self.read(q="pasta", sort="relevance").json()["results"]
        self.assertEqual([r["title"] for r in results], ["Pasta", "Lunch"])
        self.assertIsNone(results[0]["feedback"])
        public = self.client.get("/api/v1/shared-recipes", {"q": "2 cups Pasta"})
        starters = self.client.get("/api/v1/starters", {"q": "2 cups Pasta"})
        self.assertEqual(
            public.json()["results"][0]["public_id"], str(ingredient_match.public_id)
        )
        self.assertEqual(
            starters.json()["results"][0]["public_id"], str(ingredient_match.public_id)
        )
        self.assertEqual(self.read(q="missing").json()["results"], [])

    def test_lossless_document_stable_ids_personal_edits_and_audit(self):
        recipe = self.starter.recipe
        path = f"recipes/{recipe.public_id}"
        response = self.read(path)
        self.assertEqual(response.status_code, 200, response.content)
        document = response.json()["document"]
        document_validator().validate(document)
        self.assertEqual(document["ingredients"][0]["original_text"], "Pasta")
        self.assertEqual(document["steps"][0]["instruction"], "Boil")
        self.assertIsNone(document["ingredients"][0]["quantity"])
        self.assertIsNone(document["steps"][0]["ingredient_refs"])
        self.assertIsNone(document["timing"]["total"])
        Recipe.objects.filter(pk=recipe.pk).update(
            notes="Private note", favorite=True, version=9
        )
        self.assertEqual(self.read(path).json()["document"], document)
        self.assertNotIn("Private note", json.dumps(document))
        audit = AppAudit.objects.filter(recipe_uuid=recipe.public_id).latest("pk")
        self.assertEqual(audit.application_id, self.app.pk)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_keyset_pagination_ties_new_rows_and_parameter_binding(self):
        for _ in range(4):
            self.add("Same", time=5)
        for sort in ["newest", "quickest", "relevance"]:
            first = self.read(q="Same", sort=sort, limit=2).json()
            cursor = first["next_cursor"]
            self.assertTrue(cursor)
            late = self.add("Same", time=1)
            second = self.read(q="Same", sort=sort, limit=2, cursor=cursor).json()
            ids = [r["recipe_id"] for r in first["results"] + second["results"]]
            self.assertEqual(len(ids), len(set(ids)))
            self.assertNotIn(str(late.public_id), ids)
            self.assertEqual(
                self.read(q="Other", sort=sort, limit=2, cursor=cursor).status_code, 400
            )
            self.assertEqual(
                self.read(q="Same", sort=sort, limit=3, cursor=cursor).status_code, 400
            )
            self.assertEqual(
                self.read(
                    q="Same", sort=sort, limit=2, cursor=cursor + "x"
                ).status_code,
                400,
            )
            self.assertEqual(
                self.read(q="Same", sort=sort, limit=2, cursor=cursor).json(), second
            )
            Recipe.objects.filter(pk=late.pk).update(archived_at=timezone.now())

    def test_time_filter_unknowns_and_no_unsupported_features(self):
        self.add("Fast", time=5)
        self.add("Slow", time=60)
        results = self.read(sort="quickest").json()["results"]
        self.assertEqual([r["title"] for r in results], ["Fast", "Slow", "Pasta"])
        self.assertEqual(
            [r["title"] for r in self.read(max_total_minutes=10).json()["results"]],
            ["Fast"],
        )
        for params in [
            {"sort": "top_rated"},
            {"tags": "dish:soup"},
            {"min_votes": 0},
            {"after": 1},
            {"limit": 0},
            {"limit": 101},
            {"q": "x" * 201},
            {"max_total_minutes": 0},
            {"cursor": "bad"},
        ]:
            self.assertEqual(self.read(**params).status_code, 400, params)
        self.assertEqual(
            self.read("catalogs/approved/recipes?q=a&q=b").status_code, 400
        )

    def test_availability_grant_revocation_and_private_boundaries(self):
        recipe = self.starter.recipe
        path = f"recipes/{recipe.public_id}"
        for changes in [
            {"visibility": "private"},
            {"visibility": "public", "archived_at": timezone.now()},
        ]:
            Recipe.objects.filter(pk=recipe.pk).update(**changes)
            self.assertEqual(self.read().json()["results"], [])
            gone = self.read(path)
            self.assertEqual(gone.status_code, 410)
            self.assertIsNone(gone.json()["document"])
        self.catalog.recipes.clear()
        self.assertEqual(self.read(path).status_code, 404)
        ungranted = self.add("Public but ungranted", grant=False)
        self.assertEqual(self.read(f"recipes/{ungranted.public_id}").status_code, 404)
        private = Recipe.objects.create(
            owner=get_user_model().objects.create_user("owner"), title="private"
        )
        self.assertEqual(self.read(f"recipes/{private.public_id}").status_code, 404)
        self.assertEqual(self.client.get(BASE + path).status_code, 401)

    def test_same_quota_kill_switch_audience_and_read_only(self):
        self.grant.daily_limit = 1
        self.grant.save()
        self.assertEqual(self.get(self.token).status_code, 401)
        v1 = self.bearer()
        self.assertEqual(self.get(v1).status_code, 200)
        self.assertEqual(self.read().status_code, 429)
        self.grant.daily_limit = 100
        self.grant.save()
        for field, value in [
            ("resource", ["https://wrong.example/"]),
            ("expires", timezone.now() - timedelta(seconds=1)),
            ("scope", "recipes:write"),
        ]:
            token = AccessToken.objects.get(
                application=self.app, resource=[settings.CATALOG_V2_AUDIENCE]
            )
            old = getattr(token, field)
            setattr(token, field, value)
            token.save()
            self.assertIn(self.read().status_code, [401, 403])
            setattr(token, field, old)
            token.save()
        self.assertEqual(
            self.client.post(
                BASE + "catalogs/approved/recipes",
                {},
                format="json",
                HTTP_AUTHORIZATION="Bearer " + self.token,
            ).status_code,
            405,
        )
        self.grant.enabled = False
        self.grant.save()
        self.assertEqual(self.read().status_code, 401)

    def test_overlapping_catalogs_and_cursor_cannot_cross_apps_or_catalogs(self):
        other = Catalog.objects.create(slug="second", title="Second")
        other.recipes.add(self.starter)
        self.grant.catalogs.add(other)
        self.add("Second recipe")
        first = self.read(limit=1).json()
        self.assertEqual(
            self.read(
                "catalogs/second/recipes", limit=1, cursor=first["next_cursor"]
            ).status_code,
            400,
        )
        self.assertEqual(
            self.read(f"recipes/{self.starter.recipe.public_id}").status_code, 200
        )
        self.grant.catalogs.clear()
        self.assertEqual(
            self.read(limit=1, cursor=first["next_cursor"]).status_code, 404
        )

    def test_contract_and_full_seed_projection(self):
        from django.core.management import call_command
        from .documents import recipe_document

        self.starter.slug = "integration-test-pasta"
        self.starter.save(update_fields=["slug"])
        call_command("seed_starter_recipes", verbosity=0)
        recipes = Recipe.objects.filter(state="finalized", visibility="public")
        self.assertGreaterEqual(recipes.count(), 415)
        for recipe in recipes:
            document = recipe_document(recipe)
            self.assertEqual(
                [i["original_text"] for i in document["ingredients"]],
                recipe.ingredients,
            )
            self.assertEqual(
                [s["original_text"] for s in document["steps"]], recipe.instructions
            )
        contract = self.client.get(BASE + "openapi.json").json()
        self.assertEqual(contract["info"]["version"], "2.0.0")

        def check_references(node):
            if isinstance(node, dict):
                if "$ref" in node:
                    target = contract
                    for part in node["$ref"].removeprefix("#/").split("/"):
                        target = target[part]
                for value in node.values():
                    check_references(value)
            elif isinstance(node, list):
                for value in node:
                    check_references(value)

        check_references(contract)
        self.assertEqual(
            self.client.get(BASE + "recipe-document.schema.json").status_code, 200
        )
