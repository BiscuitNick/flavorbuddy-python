from django.db import models


class Recipe(models.Model):
    """Persisted recipe data captured from external sources."""

    source_url = models.URLField(unique=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    total_time = models.PositiveIntegerField(null=True, blank=True)
    yields = models.CharField(max_length=255, blank=True)
    image = models.URLField(blank=True)
    ingredients = models.JSONField(default=list, blank=True)
    instructions = models.JSONField(default=list, blank=True)
    extra = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        return self.title or self.source_url
