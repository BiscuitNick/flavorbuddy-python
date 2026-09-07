"""Copy licensed starter images from a local source checkout into managed storage."""

import hashlib
import io
import json
import warnings
from pathlib import Path
from urllib.parse import urlsplit

from PIL import Image, ImageOps
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from scrape_me.models import StarterRecipe, Recipe


class Command(BaseCommand):
    help = "Store starter images from a source checkout; safely retry after failures."

    def add_arguments(self, parser):
        parser.add_argument(
            "--source-directory",
            type=Path,
            required=True,
            help="Directory containing the upstream static/pix files",
        )

    def handle(self, *args, **options):
        root = options["source_directory"].resolve()
        catalog = json.loads(
            (settings.BASE_DIR / "data/starter/public-domain-recipes.json").read_text()
        )
        storage = storages["starter_images"]
        completed, failures = 0, []
        for row in catalog["recipes"]:
            source = row["content"].get("image")
            if not source:
                continue
            starter = StarterRecipe.objects.filter(slug=row["slug"]).first()
            if starter is None:
                failures.append(f"{row['slug']}: seed catalog first")
                continue
            if starter.recipe_id:
                if starter.provenance.get("image_storage"):
                    completed += 1
                    continue
                failures.append(
                    f"{row['slug']}: finalized image is immutable; prepare managed images in a new draft before finalizing"
                )
                continue
            try:
                # Only the curated snapshot is input, never an arbitrary remote fetch.
                url = urlsplit(source)
                if url.netloc != "publicdomainrecipes.com" or not url.path.startswith(
                    "/pix/"
                ):
                    raise ValueError("Unexpected source image URL")
                path = (root / Path(url.path).name).resolve()
                if path.parent != root or path.stat().st_size > 10 * 1024 * 1024:
                    raise ValueError("Invalid file or image exceeds 10 MiB")
                original = path.read_bytes()
                with warnings.catch_warnings():
                    warnings.simplefilter("error", Image.DecompressionBombWarning)
                    with Image.open(io.BytesIO(original)) as opened:
                        if opened.width * opened.height > 20_000_000:
                            raise ValueError("Image exceeds 20 megapixels")
                        picture = ImageOps.exif_transpose(opened).convert("RGB")
                        picture.thumbnail((1200, 1200))
                        output = io.BytesIO()
                        picture.save(output, format="WEBP", quality=85)
                data = output.getvalue()
                digest = hashlib.sha256(data).hexdigest()
                key = f"starters/{digest}.webp"
                if not storage.exists(key):
                    key = storage.save(key, ContentFile(data))
                managed_url = storage.url(key)
                metadata = {
                    "key": key,
                    "source_url": source,
                    "sha256": digest,
                    "source_sha256": hashlib.sha256(original).hexdigest(),
                    "width": picture.width,
                    "height": picture.height,
                    "bytes": len(data),
                }
                # Upload first: a failed upload never replaces a working reference.
                with transaction.atomic():
                    starter = StarterRecipe.objects.select_for_update().get(
                        pk=starter.pk
                    )
                    old_url = starter.content.get("image")
                    starter.content = {**starter.content, "image": managed_url}
                    starter.provenance = {
                        **starter.provenance,
                        "image_storage": metadata,
                    }
                    starter.save(update_fields=["content", "provenance"])
                    # Preserve edited images and avoid touching unrelated private recipes.
                    Recipe.objects.filter(
                        state="draft",
                        source_url=row["content"]["source_url"],
                        provenance__repository=row["provenance"]["repository"],
                        image__in=list({source, old_url} - {None, "", managed_url}),
                    ).update(
                        image=managed_url,
                        version=F("version") + 1,
                        updated_at=timezone.now(),
                    )
                completed += 1
            except Exception as error:
                failures.append(f"{row['slug']}: {type(error).__name__}: {error}")
        self.stdout.write(f"Stored {completed} images; {len(failures)} failed.")
        if failures:
            raise CommandError("\n".join(failures))
