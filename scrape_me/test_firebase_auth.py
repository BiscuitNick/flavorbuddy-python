import os
import subprocess
import sys
import time
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from firebase_admin import auth, exceptions

from scrape_me.models import FirebaseIdentity, Recipe

User = get_user_model()


@override_settings(
    FIREBASE_ENABLED=True,
    FIREBASE_PROJECT_ID="demo-flavorbuddy",
    FIREBASE_API_KEY="test-public-key",
    FIREBASE_AUTH_DOMAIN="demo-flavorbuddy.firebaseapp.com",
    FIREBASE_APP_ID="test-app",
    LOCAL_AUTH_ENABLED=False,
)
class FirebaseAuthTests(TestCase):
    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.claims = {
            "uid": "google-cook",
            "email": "cook@example.com",
            "email_verified": True,
            "auth_time": int(time.time()),
            "firebase": {"sign_in_provider": "google.com"},
        }
        self.app = patch(
            "scrape_me.firebase_auth.firebase_app", return_value=object()
        ).start()
        self.verify = patch(
            "scrape_me.firebase_auth.auth.verify_id_token", return_value=self.claims
        ).start()
        self.create = patch(
            "scrape_me.firebase_auth.auth.create_session_cookie",
            return_value="private-provider-session",
        ).start()
        self.session_verify = patch(
            "scrape_me.firebase_auth.auth.verify_session_cookie",
            return_value=self.claims,
        ).start()
        self.addCleanup(patch.stopall)
        self.csrf = self.client.get("/api/v1/me").json()["csrf_token"]

    def post(self, payload=None, action="firebase"):
        return self.client.post(
            "/api/v1/auth/" + action,
            payload if payload is not None else {"id_token": "provider-token"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=self.csrf,
        )

    def test_csrf_required_and_public_configuration_has_no_tokens(self):
        response = self.client.post(
            "/api/v1/auth/firebase",
            {"id_token": "provider-token"},
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)
        self.verify.assert_not_called()
        data = self.client.get("/api/v1/me").json()
        self.assertEqual(data["firebase"]["projectId"], "demo-flavorbuddy")
        self.assertFalse(data["recovery_available"])
        self.assertFalse(data["local_auth_enabled"])
        self.assertNotIn("private-provider-session", str(data))

    def test_first_sign_in_session_rotation_repeat_and_logout(self):
        response = self.post()
        self.assertEqual(response.status_code, 200, response.content)
        self.assertNotEqual(response.json()["csrf_token"], self.csrf)
        self.assertNotIn("private-provider-session", response.content.decode())
        user = User.objects.get()
        self.assertFalse(user.has_usable_password())
        self.assertTrue(response.cookies["sessionid"]["httponly"])
        self.verify.assert_called_once_with(
            "provider-token", app=self.app.return_value, check_revoked=True
        )
        self.assertEqual(self.client.get("/api/v1/me").json()["user"]["id"], user.pk)
        self.session_verify.assert_called_with(
            "private-provider-session", app=self.app.return_value, check_revoked=True
        )
        self.csrf = response.json()["csrf_token"]
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(FirebaseIdentity.objects.count(), 1)
        self.csrf = self.client.get("/api/v1/me").json()["csrf_token"]
        self.assertEqual(self.post({}, "logout").status_code, 200)
        self.assertIsNone(self.client.get("/api/v1/me").json()["user"])

    def test_legacy_link_requires_password_and_preserves_ownership(self):
        user = User.objects.create_user(
            "cook@example.com",
            email="cook@example.com",
            password="Original-password-123!",
        )
        recipe = Recipe.objects.create(owner=user, title="Private family dish")
        self.assertEqual(self.post().status_code, 409)
        self.assertEqual(
            self.post(
                {"id_token": "provider-token", "legacy_password": "wrong"}
            ).status_code,
            409,
        )
        self.assertFalse(FirebaseIdentity.objects.exists())
        result = self.post(
            {"id_token": "provider-token", "legacy_password": "Original-password-123!"}
        )
        self.assertEqual(result.status_code, 200, result.content)
        self.assertEqual(result.json()["user"]["id"], user.pk)
        self.assertEqual(
            self.client.get(f"/api/v1/recipes/{recipe.pk}").status_code, 200
        )
        user.refresh_from_db()
        self.assertFalse(user.has_usable_password())
        self.assertEqual(User.objects.count(), 1)

    def test_distinct_identity_cannot_read_another_users_recipes(self):
        other = User.objects.create_user("other")
        recipe = Recipe.objects.create(owner=other, title="Other private dish")
        self.assertEqual(self.post().status_code, 200)
        self.assertEqual(
            self.client.get(f"/api/v1/recipes/{recipe.pk}").status_code, 404
        )

    def test_google_verified_recent_sign_in_only(self):
        for change in (
            {"email_verified": False},
            {"firebase": {"sign_in_provider": "password"}},
            {"auth_time": int(time.time()) - 301},
            {"auth_time": int(time.time()) + 60},
            {"auth_time": "invalid"},
        ):
            with self.subTest(change=change):
                self.verify.return_value = {**self.claims, **change}
                self.assertEqual(self.post().status_code, 403)
        self.assertFalse(FirebaseIdentity.objects.exists())
        self.create.assert_not_called()

    def test_invalid_revoked_disabled_tokens_rejected(self):
        for exc in (
            auth.InvalidIdTokenError("invalid signature or audience"),
            auth.RevokedIdTokenError("revoked"),
            auth.UserDisabledError("disabled"),
        ):
            self.verify.side_effect = exc
            self.assertEqual(self.post().status_code, 403)
        self.assertFalse(User.objects.exists())

    def test_provider_outage_does_not_create_or_link_user(self):
        self.verify.side_effect = auth.CertificateFetchError("unavailable", None)
        self.assertEqual(self.post().status_code, 503)
        self.verify.side_effect = None
        self.create.side_effect = exceptions.UnavailableError("unavailable")
        self.assertEqual(self.post().status_code, 503)
        self.assertFalse(User.objects.exists())

    def test_revoked_disabled_expired_or_mismatched_session_loses_access(self):
        response = self.post()
        self.assertEqual(response.status_code, 200)
        for exc in (
            auth.RevokedSessionCookieError("revoked"),
            auth.UserDisabledError("disabled"),
            auth.InvalidSessionCookieError("expired"),
        ):
            self.session_verify.side_effect = exc
            self.assertIsNone(self.client.get("/api/v1/me").json()["user"])
            self.session_verify.side_effect = None
            self.csrf = self.client.get("/api/v1/me").json()["csrf_token"]
            self.assertEqual(self.post().status_code, 200)
        self.session_verify.return_value = {**self.claims, "uid": "other-uid"}
        self.assertIsNone(self.client.get("/api/v1/me").json()["user"])

    def test_session_provider_outage_fails_closed_without_destroying_session(self):
        self.post()
        self.session_verify.side_effect = exceptions.UnavailableError("unavailable")
        self.assertEqual(self.client.get("/api/v1/recipes").status_code, 503)
        self.session_verify.side_effect = None
        self.assertIsNotNone(self.client.get("/api/v1/me").json()["user"])

    def test_logout_works_during_provider_outage(self):
        self.csrf = self.post().json()["csrf_token"]
        self.session_verify.side_effect = exceptions.UnavailableError("unavailable")
        self.assertEqual(self.post({}, "logout").status_code, 200)
        self.assertIsNone(self.client.get("/api/v1/me").json()["user"])

    def test_local_account_endpoints_disabled(self):
        for action in ("login", "register", "reset", "reset-confirm"):
            self.assertEqual(
                self.post(
                    {"email": "cook@example.com", "password": "password"}, action
                ).status_code,
                400,
            )
        self.verify.assert_not_called()

    @override_settings(LOCAL_AUTH_ENABLED=True)
    def test_link_invalidates_old_reset_tokens_and_cannot_reset_linked_account(self):
        user = User.objects.create_user(
            "cook@example.com",
            email="cook@example.com",
            password="Original-password-123!",
        )
        old_token = default_token_generator.make_token(user)
        self.post(
            {"id_token": "provider-token", "legacy_password": "Original-password-123!"}
        )
        self.csrf = self.client.get("/api/v1/me").json()["csrf_token"]
        user.refresh_from_db()
        for token in (old_token, default_token_generator.make_token(user)):
            result = self.post(
                {
                    "uid": urlsafe_base64_encode(force_bytes(user.pk)),
                    "token": token,
                    "password": "New-password-123!",
                },
                "reset-confirm",
            )
            self.assertEqual(result.status_code, 400)

    def test_disabled_local_account_cannot_be_linked_or_signed_in(self):
        user = User.objects.create_user(
            "cook@example.com",
            email="cook@example.com",
            password="Original-password-123!",
            is_active=False,
        )
        self.assertEqual(
            self.post(
                {
                    "id_token": "provider-token",
                    "legacy_password": "Original-password-123!",
                }
            ).status_code,
            403,
        )
        FirebaseIdentity.objects.create(
            user=user, project_id="demo-flavorbuddy", uid="google-cook"
        )
        self.assertEqual(self.post().status_code, 403)


class FirebaseSettingsTests(SimpleTestCase):
    def test_emulator_cannot_be_used_in_production_or_with_real_project(self):
        base = {
            **os.environ,
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "DJANGO_DEBUG": "false",
            "DJANGO_SECRET_KEY": "settings-test-only-abcdefghijklmnopqrstuvwxyz-0123456789",
            "DJANGO_ALLOWED_HOSTS": "alpha.example.com",
            "PROJECT_URL": "https://alpha.example.com",
            "FIREBASE_API_KEY": "test-key",
            "FIREBASE_APP_ID": "test-app",
            "FIREBASE_AUTH_DOMAIN": "demo-flavorbuddy.firebaseapp.com",
            "FIREBASE_AUTH_EMULATOR_HOST": "127.0.0.1:9099",
        }
        for environment, project, message in (
            ("production", "demo-flavorbuddy", "forbidden in production"),
            ("test", "real-project", "requires an isolated demo- project"),
        ):
            result = subprocess.run(
                [sys.executable, "-c", "import django; django.setup()"],
                env={**base, "DJANGO_ENV": environment, "FIREBASE_PROJECT_ID": project},
                capture_output=True,
                text=True,
                timeout=10,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(message, result.stderr)
