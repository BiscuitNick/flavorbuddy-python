from django.db.models.signals import post_delete
from django.contrib.auth import get_user_model
from django.dispatch import receiver
from .models import PrivatePhoto, PhotoCleanup, CaptureJob


@receiver(post_delete, sender=PrivatePhoto)
def queue_photo_cleanup(sender, instance, **kwargs):
    # Persist in the same transaction as deletion, including recipe cascades.
    PhotoCleanup.objects.get_or_create(
        key=instance.key,
        defaults={
            "owner_id": cleanup_owner(instance, kwargs.get("origin")),
            "size": instance.size,
        },
    )


@receiver(post_delete, sender=CaptureJob)
def queue_capture_cleanup(sender, instance, **kwargs):
    if instance.image_key:
        PhotoCleanup.objects.get_or_create(
            key=instance.image_key,
            defaults={
                "owner_id": cleanup_owner(instance, kwargs.get("origin")),
                "size": instance.image_size,
            },
        )


def cleanup_owner(instance, origin):
    User = get_user_model()
    if isinstance(origin, User) or getattr(origin, "model", None) is User:
        return None
    return instance.owner_id
