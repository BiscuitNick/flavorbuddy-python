from django.db import models
from django.utils import timezone


class PantryItem(models.Model):
    owner = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    name = models.CharField(max_length=120)
    quantity = models.CharField(max_length=80, blank=True)
    location = models.CharField(max_length=80, default="Pantry")
    running_low = models.BooleanField(default=False)
    use_soon = models.BooleanField(default=False)
    used_up = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)


class Preferences(models.Model):
    owner = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    exclusions = models.JSONField(default=list)
    diet = models.CharField(max_length=20, blank=True)


class PrivatePhoto(models.Model):
    owner = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    recipe = models.ForeignKey(
        "scrape_me.Recipe", on_delete=models.CASCADE, related_name="private_photos"
    )
    completion = models.ForeignKey(
        "scrape_me.CookingCompletion", null=True, on_delete=models.CASCADE
    )
    recipe_version = models.PositiveIntegerField()
    recipe_snapshot = models.JSONField()
    kind = models.CharField(
        max_length=12, choices=[("cover", "Recipe cover"), ("result", "Cooking result")]
    )
    origin = models.CharField(max_length=20, default="user_upload", editable=False)
    key = models.CharField(max_length=200, unique=True)
    size = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class PhotoCleanup(models.Model):
    not_before = models.DateTimeField(default=timezone.now)
    key = models.CharField(max_length=200, unique=True)
    owner = models.ForeignKey("auth.User", null=True, on_delete=models.SET_NULL)
    size = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)


class CapabilityGrant(models.Model):
    owner = models.OneToOneField("auth.User", on_delete=models.CASCADE)
    capture_enabled = models.BooleanField(default=False)
    capture_daily_limit = models.PositiveIntegerField(default=3)


class CaptureJob(models.Model):
    owner = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    key = models.UUIDField()
    input_hash = models.CharField(max_length=64)
    image_key = models.CharField(max_length=200)
    image_size = models.PositiveIntegerField()
    state = models.CharField(max_length=20, default="queued")
    attempts = models.PositiveSmallIntegerField(default=0)
    lease = models.UUIDField(null=True)
    lease_expires = models.DateTimeField(null=True)
    available_at = models.DateTimeField(default=timezone.now)
    preview = models.JSONField(default=list)
    approved_ids = models.JSONField(default=list)
    error_code = models.CharField(max_length=40, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "key"], name="owned_capture_key")
        ]


class JobUsage(models.Model):
    job = models.OneToOneField(CaptureJob, on_delete=models.CASCADE)
    state = models.CharField(max_length=20, default="reserved")
    units = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
