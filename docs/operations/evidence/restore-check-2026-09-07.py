"""Exact synthetic verification run in the isolated September 7 restore job.

Historical operator evidence; requires the recorded private fixture manifest and
refuses the serving database. No credentials are embedded.
"""

import json, hashlib, io
from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import connection, transaction, IntegrityError
from django.core.files.storage import storages
from google.cloud import storage
from rest_framework.test import APIClient
from scrape_me.models import Recipe, StarterRecipe, CookingCompletion
from kitchen.models import PantryItem, PrivatePhoto
from integrations.models import Catalog, AppGrant
from integrations.documents import recipe_document
from PIL import Image

expected = json.loads(
    storage.Client()
    .bucket("flavorbuddy-20260906-staging-private-photos")
    .blob("_release/restore-expected.json")
    .download_as_text()
)
assert "fb-restore-20260907" in connection.settings_dict["HOST"]
assert Recipe.objects.count() == expected["recipes"]
assert StarterRecipe.objects.count() == 415
assert CookingCompletion.objects.count() == expected["completions"]
assert PantryItem.objects.count() == expected["pantry"]
assert PrivatePhoto.objects.count() == expected["photos"]
assert Catalog.objects.get(slug="licensed-starters").recipes.count() == 415
assert AppGrant.objects.filter(
    application__name="flavorgirls-staging-smoke", enabled=True
).exists()
recipe = Recipe.objects.get(public_id=expected["recipe_uuid"])
assert recipe.state == "finalized" and recipe.visibility == "private"
assert recipe.notes == "Synthetic private cooked note"
try:
    with transaction.atomic():
        Recipe.objects.filter(pk=recipe.pk).update(title="Must fail")
except IntegrityError:
    pass
else:
    raise AssertionError("Immutability trigger missing after restore")
for index, email in enumerate(expected["accounts"]):
    client = APIClient()
    client.force_authenticate(get_user_model().objects.get(username=email))
    kw = {
        "secure": True,
        "HTTP_HOST": "flavorbuddy-staging-560489769953.us-central1.run.app",
    }
    export = client.get("/api/v1/recipes/export", **kw)
    assert export.status_code == 200
    assert len(export.json()["recipes"]) == 1
    photo = client.get(f"/api/v1/photos/{expected['photo_id']}/content", **kw)
    assert photo.status_code == (200 if index == 0 else 404)
    if index == 0:
        data = b"".join(photo.streaming_content)
        assert hashlib.sha256(data).hexdigest() == expected["photo_sha256"]
        Image.open(io.BytesIO(data)).load()
    assert len(client.get("/api/v1/pantry", **kw).json()["items"]) == (
        1 if index == 0 else 0
    )
for r in Recipe.objects.filter(state="finalized", visibility="public"):
    recipe_document(r)
print(
    json.dumps(
        {
            "managed_restore": "passed",
            "recipe_count": Recipe.objects.count(),
            "starters": 415,
            "immutable_trigger": True,
            "two_user_exports": True,
            "private_gcs_object_hash_decode_and_ownership": True,
            "pantry_isolation": True,
            "catalog_grant": True,
        }
    )
)
