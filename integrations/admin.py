from django.contrib import admin
from .models import AppGrant, Catalog, AppAudit

admin.site.register(Catalog)
admin.site.register(AppGrant)


@admin.register(AppAudit)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("created_at", "application_id", "action", "status", "request_id")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
