import uuid
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class RecipeType(models.TextChoices):
    URL = "url", "URL"
    IMAGE_UPLOAD = "image_upload", "Image Upload"
    USER_INPUT = "user_input", "User Input"
    AI_GENERATED = "ai_generated", "AI Generated"


class Recipe(models.Model):
    """Persisted recipe data captured from external sources."""

    owner = models.ForeignKey(
        "auth.User", null=True, blank=True, on_delete=models.CASCADE
    )
    public_id = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    state = models.CharField(
        max_length=12,
        choices=[("draft", "Draft"), ("finalized", "Finalized")],
        default="draft",
    )
    visibility = models.CharField(
        max_length=10,
        choices=[("private", "Private"), ("public", "Public")],
        default="private",
    )
    finalized_at = models.DateTimeField(null=True, blank=True, editable=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    inspired_by = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="variations",
    )
    source_markdown = models.TextField(blank=True)
    provenance = models.JSONField(default=dict, blank=True)
    notes = models.TextField(blank=True)
    favorite = models.BooleanField(default=False)
    version = models.PositiveIntegerField(default=1)
    source_url = models.URLField(max_length=2000, blank=True, null=True)
    description = models.TextField(blank=True)
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255, blank=True)
    total_time = models.PositiveIntegerField(null=True, blank=True)
    yields = models.CharField(max_length=255, blank=True)
    image = models.URLField(max_length=2000, blank=True)
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
        ordering = ["-created_at", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    state="draft", visibility="private", finalized_at__isnull=True
                )
                | models.Q(
                    state="finalized",
                    finalized_at__isnull=False,
                    visibility__in=["private", "public"],
                ),
                name="recipe_lifecycle",
            ),
            models.CheckConstraint(
                condition=~models.Q(inspired_by=models.F("id")),
                name="recipe_not_self_inspired",
            ),
        ]

    CONTENT_FIELDS = (
        "public_id",
        "title",
        "description",
        "author",
        "total_time",
        "yields",
        "source_url",
        "image",
        "ingredients",
        "instructions",
        "provenance",
        "source_markdown",
        "type",
        "inspired_by_id",
    )

    def clean(self):
        super().clean()
        if self.state == "draft" and self.visibility != "private":
            raise ValidationError("Drafts must remain private.")
        if self.pk:
            old = type(self).objects.get(pk=self.pk)
            if old.state == "finalized" and (
                self.state != "finalized"
                or any(getattr(old, f) != getattr(self, f) for f in self.CONTENT_FIELDS)
            ):
                raise ValidationError(
                    "This recipe is finalized. Make a variation to change its content."
                )
        if self.state == "finalized":
            from scrape_me.api.serializers import RecipeSerializer

            validator = RecipeSerializer(
                data={
                    f: getattr(self, f)
                    for f in ("title", "ingredients", "instructions")
                },
                context={"require_complete": True},
            )
            if not validator.is_valid():
                raise ValidationError(str(validator.errors))

    def delete(self, *args, **kwargs):
        if self.state == "finalized":
            raise ValidationError(
                "Archive finalized recipes instead of deleting their identity."
            )
        return super().delete(*args, **kwargs)

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
        self.clean()
        if self.state == "finalized" and self.finalized_at is None:
            self.finalized_at = timezone.now()
        super().save(*args, **kwargs)


class ImportDraft(models.Model):
    owner = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    key = models.UUIDField()
    input_hash = models.CharField(max_length=64)
    input = models.JSONField(default=dict)
    content = models.JSONField(default=dict)
    state = models.CharField(max_length=20, default="processing")
    error_code = models.CharField(max_length=64, blank=True)
    recipe = models.OneToOneField(
        Recipe, null=True, blank=True, on_delete=models.SET_NULL
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["owner", "key"], name="owned_import_key")
        ]


class UsageCounter(models.Model):
    key = models.CharField(max_length=200, unique=True)
    count = models.PositiveIntegerField(default=0)


class AIInvocation(models.Model):
    draft = models.OneToOneField(ImportDraft, on_delete=models.CASCADE)
    state = models.CharField(max_length=32, default="reserved")
    provider_id = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CookingCompletion(models.Model):
    recipe_version = models.PositiveIntegerField(null=True)
    recipe_snapshot = models.JSONField(default=dict)
    recipe = models.ForeignKey(
        Recipe, on_delete=models.CASCADE, related_name="cooking_completions"
    )
    key = models.UUIDField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)


class StarterRecipe(models.Model):
    """Explicitly public catalog; never exposes ownerless legacy Recipe records."""

    recipe = models.OneToOneField(
        Recipe,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="legacy_starter",
    )
    slug = models.SlugField(max_length=255, unique=True)
    title = models.CharField(max_length=255, db_index=True)
    content = models.JSONField()
    provenance = models.JSONField()
    source_markdown = models.TextField()

    class Meta:
        ordering = ["title", "id"]
