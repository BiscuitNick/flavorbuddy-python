import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings
from django.utils import timezone
from oauth2_provider.models import Application, AccessToken
from rest_framework.test import APIClient
from scrape_me.models import Recipe, StarterRecipe
from .models import AppGrant, Catalog, AppAudit

BASE = "/api/integrations/v1/"


class Setup:
    def setUp(self):
        self.app = Application.objects.create(
            name="test-server",
            client_type="confidential",
            authorization_grant_type="client-credentials",
            client_secret="test-secret",
        )
        self.grant = AppGrant.objects.create(
            application=self.app,
            environment=settings.ENVIRONMENT,
            expires_at=timezone.now() + timedelta(days=1),
        )
        self.catalog = Catalog.objects.create(slug="approved", title="Approved")
        self.starter = StarterRecipe.objects.create(
            slug="pasta",
            title="Pasta",
            content={
                "title": "Pasta",
                "ingredients": ["Pasta"],
                "instructions": ["Boil"],
            },
            provenance={"license": "CC0", "source_url": "https://example.com/pasta"},
        )
        from scrape_me.services.starter_identity import attach_recipe

        attach_recipe(self.starter)
        self.starter.refresh_from_db()
        self.catalog.recipes.add(self.starter)
        self.grant.catalogs.add(self.catalog)
        self.client = APIClient()

    def issue(self, **data):
        auth = base64.b64encode(f"{self.app.client_id}:test-secret".encode()).decode()
        return self.client.post(
            BASE + "oauth/token",
            {
                "grant_type": "client_credentials",
                "scope": "catalog:read",
                "resource": settings.CATALOG_AUDIENCE,
                **data,
            },
            HTTP_AUTHORIZATION="Basic " + auth,
        )

    def bearer(self):
        response = self.issue()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["expires_in"], 300)
        self.assertNotIn("refresh_token", response.json())
        return response.json()["access_token"]

    def get(self, token, path="catalogs/approved/recipes", **kwargs):
        return self.client.get(
            BASE + path, HTTP_AUTHORIZATION="Bearer " + token, **kwargs
        )


@override_settings(CATALOG_AUDIENCE="http://testserver/api/integrations/v1/")
class CatalogTests(Setup, TestCase):
    def test_real_client_credentials_and_attribution(self):
        token = self.bearer()
        response = self.get(token)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(response.json()["results"][0]["provenance"]["license"], "CC0")
        self.assertEqual(response["Cache-Control"], "private, no-store")
        self.assertTrue(AppAudit.objects.filter(status=200, action="catalog").exists())
        self.assertNotIn(token, str(list(AppAudit.objects.values())))

    def test_disabled_expired_wrong_environment_unknown(self):
        token = self.bearer()
        for field, value in [
            ("enabled", False),
            ("expires_at", timezone.now() - timedelta(days=1)),
            ("environment", "other"),
        ]:
            original = getattr(self.grant, field)
            setattr(self.grant, field, value)
            self.grant.save()
            self.assertEqual(self.get(token).status_code, 401)
            self.assertEqual(self.issue().status_code, 401)
            setattr(self.grant, field, original)
            self.grant.save()
        self.assertEqual(self.get("unknown").status_code, 401)
        self.assertEqual(
            self.client.post(
                BASE + "oauth/token", {"grant_type": "client_credentials"}
            ).status_code,
            401,
        )

    def test_expired_wrong_audience_unrestricted_missing_scope_and_user_tokens(self):
        token = self.bearer()
        stored = AccessToken.objects.get(application=self.app)
        for field, bad in [
            ("expires", timezone.now() - timedelta(seconds=1)),
            ("resource", ["https://other.example/"]),
            ("resource", []),
            ("scope", "recipes:read"),
        ]:
            old = getattr(stored, field)
            setattr(stored, field, bad)
            stored.save()
            self.assertIn(self.get(token).status_code, [401, 403])
            setattr(stored, field, old)
            stored.save()
        stored.user = get_user_model().objects.create_user("alice")
        stored.save()
        self.assertEqual(self.get(token).status_code, 401)
        self.assertEqual(self.issue(resource="https://other.example/").status_code, 400)
        self.assertEqual(self.issue(scope="recipes:write").status_code, 400)
        self.assertEqual(self.issue(resource="").status_code, 400)

    def test_catalog_grant_removal_and_no_private_or_paid_routes(self):
        token = self.bearer()
        other = Catalog.objects.create(slug="other", title="Other")
        other.recipes.add(self.starter)
        self.assertEqual(self.get(token, "catalogs/other/recipes").status_code, 404)
        self.catalog.recipes.clear()
        self.assertEqual(
            self.get(token, f"catalogs/approved/recipes/{self.starter.pk}").status_code,
            404,
        )
        self.grant.catalogs.clear()
        self.assertEqual(self.get(token).status_code, 404)
        for name in ["alice", "bob"]:
            owner = get_user_model().objects.create_user(name)
            recipe = Recipe.objects.create(owner=owner, title=name)
            self.assertEqual(
                self.client.get(
                    f"/api/v1/recipes/{recipe.pk}", HTTP_AUTHORIZATION="Bearer " + token
                ).status_code,
                403,
            )
        for path in ["recipes/export", "imports", "recipes", "me"]:
            response = self.client.get(
                "/api/v1/" + path, HTTP_AUTHORIZATION="Bearer " + token
            )
            if path == "me":
                self.assertIsNone(response.json()["user"])
            else:
                self.assertEqual(response.status_code, 403)
        self.assertEqual(
            self.client.post(
                "/api/v1/imports",
                {},
                format="json",
                HTTP_AUTHORIZATION="Bearer " + token,
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post(
                BASE + "catalogs",
                {},
                format="json",
                HTTP_AUTHORIZATION="Bearer " + token,
            ).status_code,
            405,
        )
        self.assertEqual(self.client.get("/api/v1/starters").status_code, 200)

    def test_quotas_survive_new_tokens_query_and_forwarded_headers(self):
        self.grant.daily_limit = 1
        self.grant.save()
        token = self.bearer()
        self.assertEqual(self.get(token).status_code, 200)
        self.assertEqual(self.get(self.bearer(), "?ignored=1").status_code, 404)
        self.assertEqual(
            self.get(
                self.bearer(), "catalogs", HTTP_X_FORWARDED_FOR="8.8.8.8"
            ).status_code,
            429,
        )

    def test_revocation_and_rotation(self):
        from django.core.management import call_command
        from tempfile import TemporaryDirectory

        token = self.bearer()
        with TemporaryDirectory() as folder:
            call_command(
                "catalog_app",
                "rotate",
                self.app.name,
                credentials_file=folder + "/app.json",
            )
        self.assertEqual(self.get(token).status_code, 401)
        self.assertEqual(self.issue().status_code, 401)

    def test_other_app_is_not_granted_and_explicit_revocation(self):
        token = self.bearer()
        second = Application.objects.create(
            name="other-app",
            client_type="confidential",
            authorization_grant_type="client-credentials",
            client_secret="other-secret",
        )
        AppGrant.objects.create(
            application=second,
            environment=settings.ENVIRONMENT,
            expires_at=timezone.now() + timedelta(days=1),
        )
        auth = base64.b64encode(f"{second.client_id}:other-secret".encode()).decode()
        result = self.client.post(
            BASE + "oauth/token",
            {
                "grant_type": "client_credentials",
                "scope": "catalog:read",
                "resource": settings.CATALOG_AUDIENCE,
            },
            HTTP_AUTHORIZATION="Basic " + auth,
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.get(result.json()["access_token"]).status_code, 404)
        auth = base64.b64encode(f"{self.app.client_id}:test-secret".encode()).decode()
        result = self.client.post(
            BASE + "oauth/revoke", {"token": token}, HTTP_AUTHORIZATION="Basic " + auth
        )
        self.assertEqual(result.status_code, 200)
        self.assertEqual(self.get(token).status_code, 401)

    def test_contract_and_tokens_redacted_at_rest(self):
        token = self.bearer()
        stored = AccessToken.objects.get(application=self.app)
        self.assertEqual(stored.token, "")
        self.assertNotEqual(self.app.client_secret, "test-secret")
        contract = self.client.get(BASE + "openapi.json")
        self.assertEqual(contract.status_code, 200)
        self.assertEqual(contract.json()["info"]["version"], "1.0.0")
        self.assertIn("/catalogs/{catalog}/recipes", contract.json()["paths"])

    @override_settings(APP_TOKEN_MINUTE_LIMIT=1)
    def test_token_endpoint_limit(self):
        self.bearer()
        self.assertEqual(self.issue().status_code, 429)


@override_settings(CATALOG_AUDIENCE="http://testserver/api/integrations/v1/")
class ConcurrentCatalogTests(Setup, TransactionTestCase):
    def test_parallel_reads_cannot_exceed_quota(self):
        token = self.bearer()
        self.grant.daily_limit = 1
        self.grant.save()

        def read(_):
            close_old_connections()
            try:
                return (
                    APIClient()
                    .get(BASE + "catalogs", HTTP_AUTHORIZATION="Bearer " + token)
                    .status_code
                )
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(read, range(2))), [200, 429])
