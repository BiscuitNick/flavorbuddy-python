from django.core.management.base import BaseCommand
from django.core.files.storage import storages
from django.db import transaction
from django.utils import timezone
from kitchen.models import PhotoCleanup, PrivatePhoto, CaptureJob


class Command(BaseCommand):
    help = "Retry private object deletion after photo/recipe removal. Schedule at least hourly."

    def handle(self, *args, **kwargs):
        removed = 0
        for item in PhotoCleanup.objects.filter(
            not_before__lte=timezone.now()
        ).order_by("id")[:1000]:
            try:
                with transaction.atomic():
                    locked = (
                        PhotoCleanup.objects.select_for_update()
                        .filter(pk=item.pk)
                        .first()
                    )
                    if (
                        not locked
                        or PrivatePhoto.objects.filter(key=item.key).exists()
                        or CaptureJob.objects.filter(image_key=item.key).exists()
                    ):
                        continue
                    storages["private_photos"].delete(item.key)
                    locked.delete()
            except Exception:
                self.stderr.write(f"Cleanup pending: {item.pk}")
                continue
            removed += 1
        self.stdout.write(f"Removed {removed} private objects.")
