from django.db import models


class RecipeType(models.TextChoices):
    URL = "url", "URL"
    IMAGE_UPLOAD = "image_upload", "Image Upload"
    USER_INPUT = "user_input", "User Input"
    AI_GENERATED = "ai_generated", "AI Generated"


class Recipe(models.Model):
    """Persisted recipe data captured from external sources."""

    source_url = models.URLField(unique=True, blank=True, null=True)
    description = models.TextField(blank=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    total_time = models.PositiveIntegerField(null=True, blank=True)
    yields = models.CharField(max_length=255, blank=True)
    image = models.URLField(blank=True)
    ingredients = models.JSONField(default=list, blank=True)
    instructions = models.JSONField(default=list, blank=True)
    views = models.PositiveIntegerField(default=0)
    type = models.CharField(
        max_length=32,
        choices=RecipeType.choices,
        default=RecipeType.USER_INPUT,
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:  # pragma: no cover - trivial representation
        if self.title:
            return self.title
        if self.source_url:
            return self.source_url
        if self.pk:
            return f"Recipe {self.pk}"
        return "Recipe"

    def save(self, *args, **kwargs):
        self.description = (self.description or "").strip()
        if self.source_url:
            if not self.type or self.type == RecipeType.USER_INPUT:
                self.type = RecipeType.URL
        elif not self.type:
            self.type = RecipeType.USER_INPUT
        super().save(*args, **kwargs)
