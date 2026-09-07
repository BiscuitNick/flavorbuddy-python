"""Disposable PostgreSQL browser-test server; never use as a deployment entrypoint."""

import os
import sys
import signal
import subprocess
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ["CAPTURE_PROVIDER"] = "fixture"
import django

django.setup()
from django.core.management import call_command
from django.test.runner import DiscoverRunner
from scrape_me.services.fetching import FetchFailure
from django.db import connection

connection.settings_dict["TEST"]["NAME"] = "test_flavorbuddy_browser"
signal.signal(signal.SIGTERM, lambda *args: sys.exit(0))
runner = DiscoverRunner(interactive=False)
old_config = runner.setup_databases()
call_command("seed_starter_recipes")
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from kitchen.models import CapabilityGrant
from django.conf import settings
from django.test import override_settings


def test_capability(sender, instance, created, **kwargs):
    if created:
        CapabilityGrant.objects.create(owner=instance, capture_enabled=True)


post_save.connect(test_capability, sender=get_user_model())
private_directory = tempfile.TemporaryDirectory()
private_override = override_settings(
    STORAGES={
        **settings.STORAGES,
        "private_photos": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
            "OPTIONS": {"location": private_directory.name},
        },
    }
)
private_override.enable()
if settings.FIREBASE_ENABLED:
    from scrape_me.models import Recipe

    for viewport in ("desktop", "mobile"):
        email = f"legacy-{viewport}@example.com"
        user = get_user_model().objects.create_user(
            username=email, email=email, password="Legacy-test-password-892!"
        )
        Recipe.objects.create(owner=user, title="Existing family recipe")
# Independent worker process uses the same disposable DB and private test directory.
worker = subprocess.Popen(
    [
        sys.executable,
        "-c",
        "import os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','config.settings'); import django; django.setup(); from django.conf import settings; settings.STORAGES['private_photos']['OPTIONS']['location']=os.environ['FB_TEST_MEDIA']; from django.core.management import call_command; call_command('run_capture_jobs')",
    ],
    cwd=Path(__file__).resolve().parent.parent,
    env={
        **os.environ,
        "POSTGRES_DB": connection.settings_dict["NAME"],
        "FB_TEST_MEDIA": private_directory.name,
    },
)
html = (
    Path(__file__).resolve().parent.parent / "scrape_me/fixtures/pasta.html"
).read_text()


def fixture(url):
    if url != "https://fixture.flavorbuddy.test/pasta":
        raise FetchFailure()
    return html, url


try:
    with patch("scrape_me.services.extraction.fetch_html", side_effect=fixture):
        call_command("runserver", "127.0.0.1:8001", use_reloader=False)
finally:
    worker.terminate()
    worker.wait(timeout=10)
    private_override.disable()
    private_directory.cleanup()
    runner.teardown_databases(old_config)
