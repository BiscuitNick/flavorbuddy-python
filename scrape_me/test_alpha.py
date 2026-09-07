import json
import uuid
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch
from django.contrib.auth import get_user_model
from django.db import connection, close_old_connections
from django.test import (
    TestCase,
    TransactionTestCase,
    Client,
    SimpleTestCase,
    override_settings,
)
from rest_framework.test import APIClient
from scrape_me.models import Recipe, ImportDraft, UsageCounter, AIInvocation
from scrape_me.services.fetching import (
    canonical_url,
    resolve_public,
    fetch_html,
    FetchFailure,
)
from scrape_me.services.extraction import validate_preview, extract_url
from scrape_me.api.errors import ImportFailure
from scrape_me.services.budgets import reserve
from rest_framework.exceptions import Throttled

CONTENT = {
    "title": "Lemon pasta",
    "ingredients": ["200g pasta", "1 lemon"],
    "instructions": ["Boil water.", "Cook pasta."],
    "total_time": 20,
}
User = get_user_model()


class PrivateAPITests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user(
            "alice@example.com", password="A-secure-test-password!"
        )
        self.bob = User.objects.create_user(
            "bob@example.com", password="B-secure-test-password!"
        )
        self.client = APIClient()
        self.client.force_login(self.alice)

    def post(self, path, data):
        return self.client.post("/api/v1/" + path, data, format="json")

    def test_postgres_and_owned_crud_search_export(self):
        self.assertEqual(connection.vendor, "postgresql")
        legacy = Recipe.objects.create(title="Legacy", ingredients=["old"])
        recipe = self.post("recipes", {**CONTENT, "owner": self.bob.pk}).json()
        pk = recipe["id"]
        self.assertEqual(Recipe.objects.get(pk=pk).owner, self.alice)
        found = self.client.get("/api/v1/recipes?q=LEMON&page_size=1").json()
        self.assertEqual(found["count"], 1)
        self.assertEqual(
            self.client.get("/api/v1/recipes?page=2").json()["results"], []
        )
        self.assertEqual(self.client.get("/api/v1/recipes?page=0").status_code, 400)
        self.assertEqual(
            self.client.get(f"/api/v1/recipes/{legacy.pk}").status_code, 404
        )
        update = self.client.patch(
            f"/api/v1/recipes/{pk}",
            {"version": 1, "notes": "Less lemon", "favorite": True},
            format="json",
        )
        self.assertEqual(update.status_code, 200)
        self.assertEqual(
            self.client.patch(
                f"/api/v1/recipes/{pk}", {"version": 1, "title": "Stale"}, format="json"
            ).status_code,
            409,
        )
        self.assertEqual(
            self.client.get("/api/v1/recipes/export").json()["recipes"][0]["notes"],
            "Less lemon",
        )
        self.client.force_login(self.bob)
        for method in ("get", "patch", "delete"):
            self.assertEqual(
                getattr(self.client, method)(f"/api/v1/recipes/{pk}").status_code, 404
            )
        self.assertEqual(
            self.client.get("/api/v1/recipes/export").json()["recipes"], []
        )
        self.assertEqual(self.client.get("/api/v1/recipes?q=Lemon").json()["count"], 0)
        self.client.force_login(self.alice)
        self.assertEqual(self.client.delete(f"/api/v1/recipes/{pk}").status_code, 204)
        self.assertTrue(Recipe.objects.filter(pk=legacy.pk, owner=None).exists())

    def test_independent_sources_and_manual_recipes(self):
        content = {**CONTENT, "source_url": "https://example.com/pasta"}
        a = self.post("recipes", content).json()
        self.assertEqual(self.post("recipes", content).status_code, 201)
        self.client.force_login(self.bob)
        b = self.post("recipes", content).json()
        self.assertNotEqual(a["id"], b["id"])
        self.assertEqual(self.post("recipes", CONTENT).status_code, 201)
        self.assertEqual(self.post("recipes", CONTENT).status_code, 201)

    @patch("scrape_me.services.extraction.extract_url", return_value=CONTENT)
    def test_owned_idempotent_preview_save(self, extract):
        body = {
            "mode": "url",
            "input": "https://example.com/pasta",
            "key": str(uuid.uuid4()),
        }
        draft = self.post("imports", body).json()
        self.assertEqual(draft["state"], "ready")
        self.assertEqual(self.post("imports", body).json()["id"], draft["id"])
        extract.assert_called_once()
        self.assertEqual(
            self.post(
                "imports", {**body, "input": "https://example.com/other"}
            ).status_code,
            409,
        )
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get(f"/api/v1/imports/{draft['id']}").status_code, 404
        )
        self.assertEqual(
            self.post("recipes", {**CONTENT, "import_id": draft["id"]}).status_code, 404
        )
        self.client.force_login(self.alice)
        recipe = self.post("recipes", {**CONTENT, "import_id": draft["id"]}).json()
        self.assertEqual(
            self.post("recipes", {**CONTENT, "import_id": draft["id"]}).json()["id"],
            recipe["id"],
        )
        self.assertEqual(Recipe.objects.count(), 1)

    def test_invalid_bodies_and_content(self):
        for body in ([], None, 42, {}, {"title": "Incomplete"}):
            for route in ("imports", "recipes"):
                response = self.client.generic(
                    "POST",
                    "/api/v1/" + route,
                    json.dumps(
                        {**body, "state": "finalized"}
                        if route == "recipes" and isinstance(body, dict)
                        else body
                    ),
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
        for body in (b"\xff", b"{broken"):
            self.assertEqual(
                self.client.generic(
                    "POST", "/api/v1/imports", body, content_type="application/json"
                ).status_code,
                400,
            )
        for bad in (
            {"image": "javascript:alert(1)"},
            {"ingredients": []},
            {"title": ""},
            {"instructions": ["x" * 10001]},
        ):
            self.assertEqual(
                self.post(
                    "recipes", {**CONTENT, **bad, "state": "finalized"}
                ).status_code,
                400,
            )

    @patch("scrape_me.services.extraction.extract_url", side_effect=FetchFailure())
    def test_failed_preview_preserves_input_and_can_be_corrected(self, extract):
        draft = self.post(
            "imports",
            {"mode": "url", "input": "https://example.com", "key": str(uuid.uuid4())},
        ).json()
        self.assertEqual(draft["state"], "failed")
        self.assertEqual(
            ImportDraft.objects.get(pk=draft["id"]).input["input"],
            "https://example.com",
        )
        self.assertEqual(
            self.post("recipes", {**CONTENT, "import_id": draft["id"]}).status_code, 201
        )

    def test_anonymous_and_retired_paths(self):
        self.client.logout()
        for path in ("recipes", "recipes/export", "imports/1"):
            self.assertEqual(self.client.get("/api/v1/" + path).status_code, 403)
        for path in ("get-recipes", "parse-recipe-url", "convert-raw-recipe"):
            self.assertEqual(self.client.get("/" + path).status_code, 410)
        self.assertEqual(self.client.get("/test-example").status_code, 404)

    @patch("scrape_me.services.ai_extraction.invoke")
    def test_ai_disabled_without_paid_call(self, invoke):
        draft = self.post(
            "imports", {"mode": "text", "input": "Pasta", "key": str(uuid.uuid4())}
        ).json()
        self.assertEqual(draft["error_code"], "ai_unavailable")
        invoke.assert_not_called()

    @override_settings(AI_ENABLED=True, AI_USER_DAILY_LIMIT=1, AI_GLOBAL_DAILY_LIMIT=2)
    @patch.dict("os.environ", {"REPLICATE_API_TOKEN": "test-only"})
    @patch(
        "scrape_me.services.ai_extraction.invoke",
        return_value={
            "id": "fixture",
            "status": "succeeded",
            "output": json.dumps(CONTENT),
        },
    )
    def test_ai_reservation_and_quota(self, invoke):
        first = self.post(
            "imports", {"mode": "text", "input": "Pasta", "key": str(uuid.uuid4())}
        ).json()
        second = self.post(
            "imports", {"mode": "text", "input": "Pasta", "key": str(uuid.uuid4())}
        ).json()
        self.assertEqual(first["state"], "ready")
        self.assertEqual(second["error_code"], "throttled")
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(AIInvocation.objects.get().provider_id, "fixture")


class SessionTests(TestCase):
    def test_csrf_registration_login_logout(self):
        client = Client(enforce_csrf_checks=True)
        credentials = {
            "email": "cook@example.com",
            "password": "Long-unique-password-481!",
        }
        self.assertEqual(
            client.post(
                "/api/v1/auth/register", credentials, content_type="application/json"
            ).status_code,
            403,
        )
        token = client.get("/api/v1/me").json()["csrf_token"]
        response = client.post(
            "/api/v1/auth/register",
            credentials,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertEqual(response.status_code, 200)
        token = response.json()["csrf_token"]
        self.assertEqual(
            client.post(
                "/api/v1/recipes", CONTENT, content_type="application/json"
            ).status_code,
            403,
        )
        self.assertEqual(
            client.post(
                "/api/v1/recipes",
                CONTENT,
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            201,
        )
        self.assertEqual(
            client.post(
                "/api/v1/auth/logout",
                {},
                content_type="application/json",
                HTTP_X_CSRFTOKEN=token,
            ).status_code,
            200,
        )
        self.assertIsNone(client.get("/api/v1/me").json()["user"])

    def test_password_reset_token_single_use(self):
        from django.contrib.auth.tokens import default_token_generator
        from django.utils.http import urlsafe_base64_encode
        from django.utils.encoding import force_bytes

        user = User.objects.create_user(
            "cook@example.com", password="Old-secure-password!"
        )
        token = default_token_generator.make_token(user)
        payload = {
            "uid": urlsafe_base64_encode(force_bytes(user.pk)),
            "token": token,
            "password": "New-secure-password-17!",
        }
        client = Client()
        self.assertEqual(
            client.post(
                "/api/v1/auth/reset-confirm", payload, content_type="application/json"
            ).status_code,
            200,
        )
        self.assertEqual(
            client.post(
                "/api/v1/auth/reset-confirm", payload, content_type="application/json"
            ).status_code,
            400,
        )


class FetchTests(SimpleTestCase):
    def test_url_policy(self):
        for url in (
            "file:///etc/passwd",
            "https://u:p@example.com",
            "https://example.com:444",
            "https://example.com\\@localhost",
            "https://example.com/\nfoo",
        ):
            with self.assertRaises(FetchFailure):
                canonical_url(url)
        self.assertEqual(
            canonical_url("HTTPS://Example.com/pasta?size=2#x"),
            "https://example.com/pasta?size=2",
        )

    def test_private_addresses_blocked_without_connection(self):
        import time

        for host in (
            "127.0.0.1",
            "10.0.0.1",
            "169.254.169.254",
            "::1",
            "::ffff:127.0.0.1",
            "192.168.0.1",
            "0.0.0.0",
            "224.0.0.1",
            "4000::1",
        ):
            with self.assertRaises(FetchFailure):
                resolve_public(host, time.monotonic() + 15)

    @patch("scrape_me.services.fetching.dns.resolver.Resolver")
    def test_mixed_dns_answers_rejected(self, resolver):
        import time

        resolver.return_value.resolve.side_effect = [
            ["8.8.8.8", "10.0.0.1"],
            ["2606:4700:4700::1111"],
        ]
        with self.assertRaises(FetchFailure):
            resolve_public("example.com", time.monotonic() + 15)

    @patch("scrape_me.services.fetching.PinnedConnection")
    @patch("scrape_me.services.fetching.resolve_public", return_value="8.8.8.8")
    def test_transport_pins_ip_and_bounds_response(self, resolve, connection):
        response = connection.return_value.getresponse.return_value
        response.status = 200
        response.getheader.side_effect = lambda name, default=None: {
            "Content-Type": "text/html",
            "Content-Length": "5",
        }.get(name, default)
        response.read.side_effect = [b"hello", b""]
        self.assertEqual(fetch_html("https://example.com/a")[0], "hello")
        self.assertEqual(
            connection.call_args.args[:4], ("example.com", "8.8.8.8", 443, True)
        )
        response.getheader.side_effect = lambda name, default=None: {
            "Content-Type": "text/html",
            "Content-Length": "9999999",
        }.get(name, default)
        with self.assertRaises(FetchFailure):
            fetch_html("https://example.com")
        response.getheader.side_effect = lambda name, default=None: {
            "Content-Type": "text/html",
            "Content-Encoding": "gzip",
        }.get(name, default)
        with self.assertRaises(FetchFailure):
            fetch_html("https://example.com")

    @patch("scrape_me.services.fetching.PinnedConnection")
    def test_redirect_revalidates_destination(self, connection):
        response = connection.return_value.getresponse.return_value
        response.status = 302
        response.getheader.return_value = "http://127.0.0.1/metadata"
        with self.assertRaises(FetchFailure):
            fetch_html("http://8.8.8.8")
        self.assertEqual(connection.call_count, 1)

    def test_invalid_provider_shapes(self):
        for data in (
            [],
            None,
            42,
            {"instructions": {"text": "bad"}},
            {"image": "file:///private"},
        ):
            with self.assertRaises(ImportFailure):
                validate_preview(data)

    @patch("scrape_me.services.extraction.fetch_html")
    def test_real_parser_fixture(self, fetch):
        fetch.return_value = (
            '<html><script type="application/ld+json">'
            + json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "Recipe",
                    "name": "Lemon pasta",
                    "recipeIngredient": ["200g pasta"],
                    "recipeInstructions": [
                        {"@type": "HowToStep", "text": "Boil."},
                        {"@type": "HowToStep", "text": "Serve."},
                    ],
                }
            )
            + "</script></html>",
            "https://example.com/pasta",
        )
        result = extract_url("https://example.com/pasta")
        self.assertEqual(result["title"], "Lemon pasta")
        self.assertEqual(result["instructions"], ["Boil.", "Serve."])


class ConcurrencyTests(TransactionTestCase):
    def test_concurrent_budget_reservation(self):
        def attempt(_):
            close_old_connections()
            try:
                reserve([("test-budget", 1)])
                return True
            except Throttled:
                return False
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=4) as pool:
            self.assertEqual(sum(pool.map(attempt, range(4))), 1)
        self.assertEqual(UsageCounter.objects.get(key="test-budget").count, 1)

    def test_concurrent_saves_create_one_recipe(self):
        user = User.objects.create_user("concurrent")
        draft = ImportDraft.objects.create(
            owner=user, key=uuid.uuid4(), input_hash="test", state="ready"
        )

        def save(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(user)
                response = client.post(
                    "/api/v1/recipes", {**CONTENT, "import_id": draft.pk}, format="json"
                )
                return response.status_code, response.json().get("id")
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(save, range(3)))
        self.assertEqual(sorted(code for code, _ in results), [200, 200, 201])
        self.assertEqual(len(set(pk for _, pk in results)), 1)
        self.assertEqual(Recipe.objects.count(), 1)


class OperationsTests(TestCase):
    def test_health_and_unavailable_database(self):
        self.assertEqual(self.client.get("/health/live").status_code, 200)
        self.assertEqual(self.client.get("/health/ready").status_code, 200)
        from django.db import OperationalError

        with patch("config.health.connection.cursor", side_effect=OperationalError()):
            self.assertEqual(self.client.get("/health/ready").status_code, 503)

    def test_cooking_completion_owned_idempotent_and_versioned(self):
        from scrape_me.models import CookingCompletion

        alice = User.objects.create_user("chef")
        bob = User.objects.create_user("other-chef")
        recipe = Recipe.objects.create(owner=alice, state="finalized", **CONTENT)
        client = APIClient()
        client.force_login(alice)
        payload = {"key": str(uuid.uuid4()), "notes": "Made it!", "version": 1}
        self.assertEqual(
            client.post(
                f"/api/v1/recipes/{recipe.pk}/cook", payload, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(
            client.post(
                f"/api/v1/recipes/{recipe.pk}/cook", payload, format="json"
            ).status_code,
            200,
        )
        self.assertEqual(CookingCompletion.objects.count(), 1)
        self.assertEqual(
            client.post(
                f"/api/v1/recipes/{recipe.pk}/cook",
                {**payload, "key": str(uuid.uuid4())},
                format="json",
            ).status_code,
            409,
        )
        client.force_login(bob)
        self.assertEqual(
            client.post(
                f"/api/v1/recipes/{recipe.pk}/cook", payload, format="json"
            ).status_code,
            404,
        )

    def test_body_limit(self):
        client = APIClient()
        client.force_login(User.objects.create_user("large"))
        result = client.post("/api/v1/recipes", {"title": "x" * 270000}, format="json")
        self.assertEqual(result.status_code, 413)
        self.assertEqual(result.json()["error"]["code"], "body_too_large")

    def test_auth_throttle_prevents_unlimited_attempts(self):
        for _ in range(15):
            response = self.client.post(
                "/api/v1/auth/login",
                {"email": "missing@example.com", "password": "nope"},
                content_type="application/json",
            )
            self.assertEqual(response.status_code, 400)
        self.assertEqual(
            self.client.post(
                "/api/v1/auth/login",
                {"email": "missing@example.com", "password": "nope"},
                content_type="application/json",
            ).status_code,
            429,
        )


class MigrationTests(TransactionTestCase):
    def test_legacy_content_survives_ownership_migration(self):
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([("scrape_me", "0005_recipe_description")])
        old_apps = executor.loader.project_state(
            [("scrape_me", "0005_recipe_description")]
        ).apps
        old = old_apps.get_model("scrape_me", "Recipe").objects.create(
            title="Legacy supper",
            source_url="https://example.com/legacy",
            ingredients=["A carrot"],
            instructions=["Roast."],
            description="Keep me",
        )
        old_id = old.pk
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
        row = Recipe.objects.get(pk=old_id)
        self.assertIsNone(row.owner_id)
        self.assertEqual(row.description, "Keep me")
        self.assertEqual(row.ingredients, ["A carrot"])
        self.assertEqual(row.source_url, "https://example.com/legacy")


class MoreFetchTests(SimpleTestCase):
    @patch("scrape_me.services.fetching.socket.socket")
    @patch("scrape_me.services.fetching.ssl.create_default_context")
    def test_socket_uses_numeric_ip_and_tls_uses_hostname(self, context, socket):
        from scrape_me.services.fetching import PinnedConnection

        client = PinnedConnection("example.com", "8.8.8.8", 443, True, 5)
        client.connect()
        socket.return_value.connect.assert_called_once_with(("8.8.8.8", 443))
        context.return_value.wrap_socket.assert_called_once_with(
            socket.return_value, server_hostname="example.com"
        )
        # http.client may detach the connection socket for a Connection: close body.
        client.sock = None
        client.abort()
        context.return_value.wrap_socket.return_value.shutdown.assert_called_once()

    @patch("scrape_me.services.fetching.PinnedConnection")
    def test_timeout_and_unsupported_type(self, connection):
        connection.return_value.getresponse.side_effect = TimeoutError()
        with self.assertRaises(FetchFailure):
            fetch_html("https://8.8.8.8")
        connection.return_value.getresponse.side_effect = None
        response = connection.return_value.getresponse.return_value
        response.status = 200
        response.getheader.return_value = "application/pdf"
        with self.assertRaises(FetchFailure):
            fetch_html("https://8.8.8.8")

    @patch("scrape_me.services.fetching.PinnedConnection")
    def test_excessive_redirects_and_stream_limit(self, connection):
        response = connection.return_value.getresponse.return_value
        response.status = 302
        response.getheader.return_value = "https://8.8.8.8/again"
        with self.assertRaises(FetchFailure):
            fetch_html("https://8.8.8.8")
        self.assertEqual(connection.call_count, 6)
        response.status = 200
        response.getheader.side_effect = lambda name, default=None: {
            "Content-Type": "text/html"
        }.get(name, default)
        response.read.return_value = b"x" * 65536
        with self.assertRaises(FetchFailure):
            fetch_html("https://8.8.8.8")


class AIFailureTests(TestCase):
    @override_settings(AI_ENABLED=True, AI_USER_DAILY_LIMIT=1, AI_GLOBAL_DAILY_LIMIT=1)
    @patch.dict("os.environ", {"REPLICATE_API_TOKEN": "test-only"})
    @patch(
        "scrape_me.services.ai_extraction.invoke",
        return_value={
            "id": "invalid-fixture",
            "status": "succeeded",
            "output": "[1,2]",
        },
    )
    def test_invalid_ai_result_consumes_reservation_and_does_not_save(self, invoke):
        client = APIClient()
        client.force_login(User.objects.create_user("ai-failure"))
        result = client.post(
            "/api/v1/imports",
            {"mode": "text", "input": "Some pasted recipe", "key": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(result.json()["state"], "failed")
        self.assertEqual(AIInvocation.objects.get().state, "failed_or_uncertain")
        self.assertEqual(Recipe.objects.count(), 0)
        again = client.post(
            "/api/v1/imports",
            {"mode": "text", "input": "Some pasted recipe", "key": str(uuid.uuid4())},
            format="json",
        )
        self.assertEqual(again.json()["error_code"], "throttled")
        self.assertEqual(invoke.call_count, 1)

    def test_expire_abandoned_imports_without_deleting_saved_recipes(self):
        from datetime import timedelta
        from django.utils import timezone
        from django.core.management import call_command

        user = User.objects.create_user("expiry")
        old = ImportDraft.objects.create(owner=user, key=uuid.uuid4(), input_hash="x")
        ImportDraft.objects.filter(pk=old.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        stale = ImportDraft.objects.create(owner=user, key=uuid.uuid4(), input_hash="x")
        ImportDraft.objects.filter(pk=stale.pk).update(
            updated_at=timezone.now() - timedelta(minutes=3)
        )
        recipe = Recipe.objects.create(owner=user, **CONTENT)
        saved = ImportDraft.objects.create(
            owner=user,
            key=uuid.uuid4(),
            input_hash="x",
            state="saved",
            recipe=recipe,
            input={"input": "private pasted text"},
        )
        call_command("expire_imports", verbosity=0)
        self.assertFalse(ImportDraft.objects.filter(pk=old.pk).exists())
        stale.refresh_from_db()
        saved.refresh_from_db()
        self.assertEqual(stale.state, "failed")
        self.assertEqual(saved.input, {})
        self.assertTrue(Recipe.objects.filter(pk=recipe.pk).exists())
