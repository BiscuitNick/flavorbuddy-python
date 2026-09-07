from django.contrib import admin

from .models import Recipe


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "owner", "state", "visibility", "created_at", "updated_at")
    search_fields = ("title", "source_url", "author")
    list_filter = ("created_at", "owner")

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.state == "finalized":
            return tuple(
                f for f in obj.CONTENT_FIELDS if f not in ("inspired_by_id",)
            ) + ("inspired_by", "state", "finalized_at")
        return ("public_id", "finalized_at", "archived_at")

    def has_delete_permission(self, request, obj=None):
        return (obj is None or obj.state == "draft") and super().has_delete_permission(
            request, obj
        )

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions
