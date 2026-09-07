from rest_framework import serializers
from scrape_me.services.fetching import canonical_url
from scrape_me.api.errors import ImportFailure


class StrictTextField(serializers.CharField):
    def to_internal_value(self, data):
        if not isinstance(data, str):
            raise serializers.ValidationError("Use text.")
        return super().to_internal_value(data)


class PublicURLField(StrictTextField):
    def to_internal_value(self, data):
        value = super().to_internal_value(data)
        if not value:
            return value
        try:
            return canonical_url(value)
        except ImportFailure:
            raise serializers.ValidationError(
                "Use an HTTP or HTTPS URL without credentials or a custom port."
            )


class ContentSerializer(serializers.Serializer):
    title = StrictTextField(max_length=255, allow_blank=True, default="")
    description = StrictTextField(max_length=10000, allow_blank=True, default="")
    author = StrictTextField(max_length=255, allow_blank=True, default="")
    total_time = serializers.IntegerField(
        min_value=0, max_value=100000, allow_null=True, default=None
    )
    yields = StrictTextField(max_length=255, allow_blank=True, default="")
    source_url = PublicURLField(
        max_length=2000, allow_blank=True, allow_null=True, default=None
    )
    image = PublicURLField(max_length=2000, allow_blank=True, default="")
    ingredients = serializers.ListField(
        child=StrictTextField(max_length=2000), max_length=200, default=list
    )
    instructions = serializers.ListField(
        child=StrictTextField(max_length=10000), max_length=200, default=list
    )


class RecipeSerializer(ContentSerializer):
    public_id = serializers.UUIDField(read_only=True)
    state = serializers.CharField(read_only=True)
    visibility = serializers.CharField(read_only=True)
    finalized_at = serializers.DateTimeField(read_only=True)
    inspired_by_recipe_id = serializers.UUIDField(
        source="inspired_by.public_id", read_only=True, allow_null=True
    )
    private_cover = serializers.SerializerMethodField()

    def get_private_cover(self, obj):
        photos = getattr(obj, "private_photos", None)
        if photos is None:
            return None
        covers = [photo for photo in photos.all() if photo.kind == "cover"]
        if not covers:
            return None
        return f"/api/v1/photos/{max(covers, key=lambda photo: photo.pk).pk}/content"

    provenance = serializers.JSONField(read_only=True)
    id = serializers.IntegerField(read_only=True)
    notes = StrictTextField(max_length=10000, allow_blank=True, default="")
    favorite = serializers.BooleanField(default=False)
    version = serializers.IntegerField(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    updated_at = serializers.DateTimeField(read_only=True)

    def validate(self, data):
        if not self.context.get("require_complete", True):
            return data
        for field in ("title", "ingredients", "instructions"):
            if not data.get(field, getattr(self.instance, field, None)):
                raise serializers.ValidationError({field: "Add this before saving."})
        # An explicitly empty PATCH must also fail.
        for field in ("title", "ingredients", "instructions"):
            if field in data and not data[field]:
                raise serializers.ValidationError({field: "Add this before saving."})
        return data
