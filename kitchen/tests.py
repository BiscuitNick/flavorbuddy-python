import io
import tempfile
import uuid
from unittest.mock import patch
from PIL import Image
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import storages
from django.core.management import call_command
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from scrape_me.models import Recipe, StarterRecipe, CookingCompletion
from .models import PrivatePhoto, PhotoCleanup, PantryItem


def upload():
    content = io.BytesIO()
    Image.new("RGB", (20, 20), "red").save(content, "PNG")
    return SimpleUploadedFile(
        "private-name.png", content.getvalue(), content_type="image/png"
    )


class KitchenTests(TestCase):
    def setUp(self):
        self.alice = get_user_model().objects.create_user("alice")
        self.bob = get_user_model().objects.create_user("bob")
        self.client = APIClient()
        self.client.force_login(self.alice)
        self.recipe = Recipe.objects.create(
            owner=self.alice,
            title="Dinner",
            ingredients=["2 cups rice", "1 onion"],
            instructions=["Cook"],
        )
        self.directory = tempfile.TemporaryDirectory()
        from django.conf import settings

        self.storage_override = override_settings(
            PRIVATE_PHOTO_BACKEND="local",
            STORAGES={
                **settings.STORAGES,
                "private_photos": {
                    "BACKEND": "django.core.files.storage.FileSystemStorage",
                    "OPTIONS": {"location": self.directory.name},
                },
            },
        )
        self.storage_override.enable()
        self.addCleanup(self.storage_override.disable)
        self.addCleanup(self.directory.cleanup)

    def test_private_photos_reencoded_isolated_deleted_and_quota(self):
        response = self.client.post(
            f"/api/v1/recipes/{self.recipe.pk}/photos",
            {"photo": upload(), "kind": "cover"},
        )
        self.assertEqual(response.status_code, 201, response.content)
        photo = PrivatePhoto.objects.get()
        with storages["private_photos"].open(photo.key, "rb") as file:
            image = Image.open(file)
            self.assertEqual(image.format, "WEBP")
            self.assertFalse(image.getexif())
        self.assertEqual(PhotoCleanup.objects.count(), 0)
        self.assertEqual(
            self.client.get(response.json()["url"])["Cache-Control"],
            "private, no-store",
        )
        with override_settings(PRIVATE_PHOTO_COUNT=1):
            self.assertEqual(
                self.client.post(
                    f"/api/v1/recipes/{self.recipe.pk}/photos", {"photo": upload()}
                ).status_code,
                429,
            )
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get(response.json()["url"]).status_code, 404)
        self.assertEqual(
            self.client.delete(f"/api/v1/photos/{photo.pk}").status_code, 404
        )
        self.assertEqual(
            self.client.post(
                f"/api/v1/recipes/{self.recipe.pk}/photos", {"photo": upload()}
            ).status_code,
            404,
        )
        self.client.force_login(self.alice)
        self.assertEqual(
            self.client.delete(f"/api/v1/photos/{photo.pk}").status_code, 204
        )
        self.assertTrue(PhotoCleanup.objects.exists())
        call_command("cleanup_private_photos")
        self.assertFalse(storages["private_photos"].exists(photo.key))
        self.assertFalse(PhotoCleanup.objects.exists())

    def test_invalid_photos_failure_cleanup_cascade_and_snapshot(self):
        endpoint = f"/api/v1/recipes/{self.recipe.pk}/photos"
        bad = SimpleUploadedFile("fake.png", b"<svg/>", content_type="image/png")
        self.assertEqual(self.client.post(endpoint, {"photo": bad}).status_code, 400)
        with override_settings(PRIVATE_PHOTO_UPLOAD_BYTES=10):
            self.assertEqual(
                self.client.post(endpoint, {"photo": upload()}).status_code, 400
            )
        with patch.object(
            storages["private_photos"], "save", side_effect=OSError("offline")
        ):
            self.assertEqual(
                self.client.post(endpoint, {"photo": upload()}).status_code, 500
            )
        self.assertTrue(PhotoCleanup.objects.exists())
        call_command("cleanup_private_photos")
        self.recipe.state = "finalized"
        self.recipe.save()
        self.client.post(
            f"/api/v1/recipes/{self.recipe.pk}/cook",
            {"key": str(uuid.uuid4()), "version": 1, "notes": "Done"},
            format="json",
        )
        completion = CookingCompletion.objects.get()
        from django.core.exceptions import ValidationError

        self.recipe.title = "Changed"
        with self.assertRaises(ValidationError):
            self.recipe.save()
        self.recipe.refresh_from_db()
        result = self.client.post(
            endpoint,
            {"photo": upload(), "kind": "result", "completion_id": completion.pk},
        )
        self.assertEqual(result.status_code, 201, result.content)
        photo = PrivatePhoto.objects.get()
        self.assertEqual(photo.recipe_snapshot["title"], "Dinner")
        self.assertEqual(photo.recipe_version, 1)
        photo.delete()
        self.assertTrue(PhotoCleanup.objects.exists())
        call_command("cleanup_private_photos")
        self.assertFalse(storages["private_photos"].exists(photo.key))

    def test_session_photo_upload_requires_csrf(self):
        client = APIClient(enforce_csrf_checks=True)
        client.force_login(self.alice)
        self.assertEqual(
            client.post(
                f"/api/v1/recipes/{self.recipe.pk}/photos", {"photo": upload()}
            ).status_code,
            403,
        )

    def test_account_deletion_queues_media_without_dangling_owner(self):
        result = self.client.post(
            f"/api/v1/recipes/{self.recipe.pk}/photos", {"photo": upload()}
        )
        self.assertEqual(result.status_code, 201)
        key = PrivatePhoto.objects.get().key
        self.alice.delete()
        self.assertIsNone(PhotoCleanup.objects.get().owner_id)
        call_command("cleanup_private_photos")
        self.assertFalse(storages["private_photos"].exists(key))

    def test_nonobject_pantry_patch_is_controlled(self):
        item = PantryItem.objects.create(owner=self.alice, name="Rice")
        self.assertEqual(
            self.client.patch(
                f"/api/v1/pantry/{item.pk}", [], format="json"
            ).status_code,
            400,
        )

    def test_manual_pantry_undo_ownership_and_conflicts(self):
        result = self.client.post(
            "/api/v1/pantry",
            {
                "name": "Rice",
                "location": "Freezer",
                "quantity": "one bag",
                "use_soon": True,
            },
            format="json",
        )
        self.assertEqual(result.status_code, 201, result.content)
        item = result.json()
        path = f"/api/v1/pantry/{item['id']}"
        result = self.client.patch(path, {"version": 1, "used_up": True}, format="json")
        self.assertTrue(result.json()["used_up"])
        self.assertEqual(
            self.client.patch(
                path, {"version": 1, "used_up": False}, format="json"
            ).status_code,
            409,
        )
        self.assertFalse(
            self.client.patch(
                path, {"version": 2, "used_up": False}, format="json"
            ).json()["used_up"]
        )
        self.client.force_login(self.bob)
        self.assertEqual(self.client.get("/api/v1/pantry").json()["items"], [])
        self.assertEqual(
            self.client.patch(
                path, {"version": 3, "name": "Steal"}, format="json"
            ).status_code,
            404,
        )
        self.assertEqual(self.client.delete(path).status_code, 404)

    def test_matching_exclusions_uncertainty_and_no_cooking_deduction(self):
        self.recipe.state = "finalized"
        self.recipe.save()
        item = PantryItem.objects.create(owner=self.alice, name="rice", use_soon=True)
        Recipe.objects.create(owner=self.bob, title="Private Bob", ingredients=["rice"])
        StarterRecipe.objects.create(
            slug="vinegar",
            title="Vinegar",
            content={
                "title": "Vinegar",
                "ingredients": ["rice vinegar"],
                "instructions": ["Mix"],
            },
            provenance={},
        )
        StarterRecipe.objects.create(
            slug="pork",
            title="Pork",
            content={
                "title": "Pork",
                "ingredients": ["bacon"],
                "instructions": ["Cook"],
            },
            provenance={},
        )
        from scrape_me.services.starter_identity import attach_recipe

        for starter in StarterRecipe.objects.all():
            attach_recipe(starter)
        response = self.client.get("/api/v1/pantry/matches").json()
        dinner = next(r for r in response["matches"] if r["title"] == "Dinner")
        self.assertEqual(dinner["matched"][0]["ingredient"], "2 cups rice")
        self.assertEqual(dinner["missing"], ["1 onion"])
        vinegar = next(r for r in response["matches"] if r["title"] == "Vinegar")
        self.assertTrue(vinegar["uncertain"])
        self.assertEqual(vinegar["matched"], [])
        self.assertNotIn("Private Bob", str(response))
        self.client.put(
            "/api/v1/preferences",
            {"diet": "vegetarian", "exclusions": ["onion"]},
            format="json",
        )
        response = self.client.get("/api/v1/pantry/matches").json()
        self.assertEqual(response["excluded_count"], 2)
        self.client.post(
            f"/api/v1/recipes/{self.recipe.pk}/cook",
            {"key": str(uuid.uuid4()), "version": 1},
            format="json",
        )
        item.refresh_from_db()
        self.assertFalse(item.used_up)


@override_settings(CAPTURE_PROVIDER="fixture", CAPTURE_GLOBAL_DAILY_LIMIT=30)
class CaptureTests(TestCase):
    setUp = KitchenTests.setUp

    # Reuse storage/account setup without rerunning KitchenTests' inherited tests.
    def start(self, key=None):
        from .models import CapabilityGrant

        CapabilityGrant.objects.update_or_create(
            owner=self.alice,
            defaults={"capture_enabled": True, "capture_daily_limit": 3},
        )
        return self.client.post(
            "/api/v1/pantry/captures",
            {"photo": upload(), "key": key or str(uuid.uuid4())},
        )

    def test_approval_is_editable_atomic_idempotent_and_owned(self):
        from .models import CaptureJob, JobUsage
        from .jobs import work_one

        key = str(uuid.uuid4())
        result = self.start(key)
        self.assertEqual(result.status_code, 201, result.content)
        job = CaptureJob.objects.get()
        self.assertEqual(job.state, "queued")
        self.assertEqual(PantryItem.objects.count(), 0)
        self.assertEqual(self.start(key).json()["id"], job.pk)
        self.assertEqual(JobUsage.objects.count(), 1)
        work_one()
        job.refresh_from_db()
        self.assertEqual(job.state, "preview")
        self.assertEqual(job.preview[0]["quantity"], "")
        self.client.force_login(self.bob)
        self.assertEqual(
            self.client.get(f"/api/v1/pantry/captures/{job.pk}").status_code, 404
        )
        self.client.force_login(self.alice)
        body = {
            "items": [{"name": "My tomatoes", "location": "Fridge", "quantity": "2"}]
        }
        first = self.client.post(
            f"/api/v1/pantry/captures/{job.pk}", body, format="json"
        )
        self.assertEqual(first.status_code, 200, first.content)
        self.client.post(f"/api/v1/pantry/captures/{job.pk}", body, format="json")
        self.assertEqual(PantryItem.objects.count(), 1)
        self.assertEqual(PantryItem.objects.get().name, "My tomatoes")
        self.assertEqual(JobUsage.objects.get().state, "settled")

    def test_lease_recovery_retry_does_not_charge_twice_and_cancel_wins(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import CaptureJob, JobUsage
        from .jobs import work_one

        self.start()
        job = CaptureJob.objects.get()
        job.state = "running"
        job.attempts = 1
        job.lease = uuid.uuid4()
        job.lease_expires = timezone.now() - timedelta(seconds=1)
        job.save()
        work_one()
        job.refresh_from_db()
        self.assertEqual(job.state, "preview")
        self.assertEqual(job.attempts, 2)
        self.assertEqual(JobUsage.objects.count(), 1)
        key = job.image_key
        self.client.delete(f"/api/v1/pantry/captures/{job.pk}")
        call_command("cleanup_private_photos")
        self.assertFalse(storages["private_photos"].exists(key))
        self.assertEqual(
            self.client.post(
                f"/api/v1/pantry/captures/{job.pk}",
                {"items": [{"name": "Rice"}]},
                format="json",
            ).status_code,
            409,
        )

    def test_disabled_capability_blocks_new_work_but_keeps_preview_readable(self):
        from .models import CaptureJob, CapabilityGrant
        from .jobs import work_one

        self.start()
        job = CaptureJob.objects.get()
        CapabilityGrant.objects.filter(owner=self.alice).update(capture_enabled=False)
        work_one()
        job.refresh_from_db()
        self.assertEqual(job.state, "failed")
        self.assertEqual(
            self.client.get(f"/api/v1/pantry/captures/{job.pk}").status_code, 200
        )
        self.assertEqual(
            self.client.post(
                "/api/v1/pantry/captures", {"photo": upload(), "key": str(uuid.uuid4())}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.delete(f"/api/v1/pantry/captures/{job.pk}").status_code, 204
        )

    def test_global_quota_and_invalid_provider_retries(self):
        from .models import CaptureJob, JobUsage
        from .jobs import work_one

        with override_settings(CAPTURE_GLOBAL_DAILY_LIMIT=1):
            self.assertEqual(self.start().status_code, 201)
            self.assertEqual(self.start().status_code, 429)
        job = CaptureJob.objects.get()
        with patch("kitchen.jobs.detect_fixture", return_value=[{"name": ""}]):
            work_one()
        job.refresh_from_db()
        self.assertEqual(job.state, "queued")
        self.assertEqual(job.attempts, 1)
        self.assertEqual(JobUsage.objects.count(), 1)
        self.assertFalse(PantryItem.objects.exists())
