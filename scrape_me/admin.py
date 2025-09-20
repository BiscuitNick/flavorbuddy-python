from django.contrib import admin

from .models import Recipe


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("title", "source_url", "created_at", "updated_at")
    search_fields = ("title", "source_url", "author")
    list_filter = ("created_at",)
