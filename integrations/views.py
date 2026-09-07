import hashlib
import json
from django.conf import settings
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from oauth2_provider.contrib.rest_framework import OAuth2Authentication
from oauth2_provider.models import AccessToken
from oauth2_provider.views import TokenView
from rest_framework.exceptions import (
    AuthenticationFailed,
    PermissionDenied,
    Throttled,
    ValidationError,
)
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView
from scrape_me.api.starter import serialize
from scrape_me.services.budgets import reserve
from .models import AppGrant


class LimitedTokenView(TokenView):
    def post(self, request, *args, **kwargs):
        # Every attempt is charged, including invalid clients and rotated secrets.
        # A global bound is independent of spoofable forwarding headers.
        minute = int(timezone.now().timestamp()) // 60
        try:
            reserve([(f"app:tokens:global:{minute}", settings.APP_TOKEN_MINUTE_LIMIT)])
        except Throttled:
            response = JsonResponse({"error": "temporarily_unavailable"}, status=429)
            response["Retry-After"] = "60"
            return response
        response = super().post(request, *args, **kwargs)
        if response.status_code == 200:
            checksum = hashlib.sha256(
                json.loads(response.content)["access_token"].encode()
            ).hexdigest()
            request.app_id = AccessToken.objects.get(
                token_checksum=checksum
            ).application_id
        return response


class CatalogPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.auth:
            raise AuthenticationFailed("A valid app token is required.")
        token = request.auth
        if not token.allow_scopes(["catalog:read"]):
            raise PermissionDenied("catalog:read is required.")
        # Recheck the kill switch while serializing quota changes per app.
        with transaction.atomic():
            grant = (
                AppGrant.objects.select_for_update()
                .filter(
                    application=token.application,
                    enabled=True,
                    environment=settings.ENVIRONMENT,
                    expires_at__gt=timezone.now(),
                )
                .first()
            )
            if not grant or not AccessToken.objects.filter(pk=token.pk).exists():
                raise AuthenticationFailed("The app is unavailable.")
            request._request.app_id = token.application_id
            day = timezone.now().date().isoformat()
            minute = int(timezone.now().timestamp()) // 60
            reserve(
                [
                    (f"app:day:{day}:{grant.pk}", grant.daily_limit),
                    (f"app:minute:{minute}:{grant.pk}", grant.minute_limit),
                    (f"app:global:{day}", settings.APP_GLOBAL_DAILY_LIMIT),
                ]
            )
            request.catalog_grant = grant
        return True


class CatalogView(APIView):
    authentication_classes = [OAuth2Authentication]
    permission_classes = [CatalogPermission]
    http_method_names = ["get", "head", "options"]

    def get(self, request, catalog=None, pk=None):
        catalogs = request.catalog_grant.catalogs.filter(enabled=True)
        if catalog is None:
            return Response(
                {"catalogs": list(catalogs.order_by("slug").values("slug", "title"))}
            )
        collection = get_object_or_404(catalogs, slug=catalog)
        from scrape_me.api.starter import available_starters

        recipes = available_starters().filter(catalog=collection).order_by("id")
        if pk is not None:
            return Response(serialize(get_object_or_404(recipes, pk=pk)))
        try:
            after = int(request.query_params.get("after", 0))
            limit = int(request.query_params.get("limit", 24))
            if after < 0 or not 1 <= limit <= 100:
                raise ValueError
        except ValueError:
            raise ValidationError("after must be nonnegative; limit must be 1–100.")
        rows = list(recipes.filter(pk__gt=after)[: limit + 1])
        return Response(
            {
                "results": [serialize(row) for row in rows[:limit]],
                "next_after": rows[limit - 1].pk if len(rows) > limit else None,
            }
        )


class ContractView(APIView):
    authentication_classes = []
    from rest_framework.permissions import AllowAny

    permission_classes = [AllowAny]

    def get(self, request):
        return Response(
            json.loads(
                (settings.BASE_DIR / "docs/api/catalog-v1.openapi.json").read_text()
            )
        )
