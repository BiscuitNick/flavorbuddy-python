from django.db import models


class Catalog(models.Model):
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=200)
    enabled = models.BooleanField(default=True)
    recipes = models.ManyToManyField("scrape_me.StarterRecipe", blank=True)


class AppGrant(models.Model):
    application = models.OneToOneField(
        "oauth2_provider.Application", on_delete=models.CASCADE
    )
    enabled = models.BooleanField(default=True)
    environment = models.CharField(max_length=20)
    expires_at = models.DateTimeField()
    catalogs = models.ManyToManyField(Catalog, blank=True)
    daily_limit = models.PositiveIntegerField(default=1000)
    minute_limit = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)


class AppAudit(models.Model):
    application = models.ForeignKey(
        "oauth2_provider.Application", null=True, on_delete=models.SET_NULL
    )
    action = models.CharField(max_length=30)
    resource_id = models.PositiveBigIntegerField(null=True)
    status = models.PositiveSmallIntegerField()
    request_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
