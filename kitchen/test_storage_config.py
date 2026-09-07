"""Validate the real deployment configuration, without contacting cloud services."""

import os
import subprocess
import sys
from django.conf import settings
from django.test import SimpleTestCase


class StorageConfigurationTests(SimpleTestCase):
    def test_real_gcs_backend_accepts_production_options(self):
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                """
import django
django.setup()
from django.core.files.storage import storages
backend = storages['private_photos']
assert backend.bucket_name == 'configuration-test-private'
assert backend.get_object_parameters('test.webp')['cache_control'] == 'private, no-store'
print('configured')
""",
            ],
            cwd=settings.BASE_DIR,
            env={
                **os.environ,
                "DJANGO_SETTINGS_MODULE": "config.settings",
                "DJANGO_ENV": "production",
                "DJANGO_DEBUG": "false",
                "DJANGO_SECRET_KEY": "storage-config-test-only-" + "a" * 50,
                "PROJECT_URL": "https://storage-test.example",
                "DJANGO_ALLOWED_HOSTS": "storage-test.example",
                "PRIVATE_PHOTO_BACKEND": "gcs",
                "GS_PRIVATE_BUCKET_NAME": "configuration-test-private",
            },
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "configured")
