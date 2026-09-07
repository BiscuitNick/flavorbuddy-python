"""Read-only UUID catalog contract with its own version-specific OAuth audience."""

import json
from django.conf import settings
from django.core import signing
from django.db.models import Case, IntegerField, Max, Q, Value, When
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from django.utils import timezone
from jsonschema.exceptions import ValidationError as DocumentError
from rest_framework.exceptions import ValidationError, APIException
from rest_framework.response import Response
from scrape_me.models import Recipe
from scrape_me.services.search import search_recipes
from .documents import recipe_document
from .views import CatalogView, ContractView


def granted_recipes(request, catalog=None):
    catalogs = request.catalog_grant.catalogs.filter(enabled=True)
    if catalog is not None:
        catalogs = catalogs.filter(pk=get_object_or_404(catalogs, slug=catalog).pk)
    # Subquery deduplicates overlapping catalogs before pagination.
    return Recipe.objects.filter(
        legacy_starter__in=catalogs.values("recipes"), state="finalized"
    ).select_related("inspired_by")


def card(recipe):
    return {
        "recipe_id": str(recipe.public_id),
        "title": recipe.title,
        "description": recipe.description or None,
        "image_url": recipe.image or None,
        "yield_text": recipe.yields or None,
        "total_minutes": recipe.total_time,
        "feedback": None,
    }


class SearchView(CatalogView):
    def get(self, request, catalog):
        params = request.query_params
        allowed = {"q", "sort", "limit", "cursor", "max_total_minutes"}
        if set(params) - allowed or any(len(params.getlist(k)) != 1 for k in params):
            raise ValidationError("Unsupported or repeated query parameter.")
        query = params.get("q", "").strip()
        sort = params.get("sort", "relevance" if query else "newest")
        if len(query) > 200 or sort not in {"relevance", "newest", "quickest"}:
            raise ValidationError(
                "q is limited to 200 characters; sort is relevance, newest or quickest."
            )
        try:
            limit = int(params.get("limit", 24))
            maximum = (
                int(params["max_total_minutes"])
                if "max_total_minutes" in params
                else None
            )
            if not 1 <= limit <= 100 or (
                maximum is not None and not 1 <= maximum <= 100000
            ):
                raise ValueError
        except ValueError:
            raise ValidationError(
                "limit must be 1–100; max_total_minutes must be 1–100000."
            )
        recipes = granted_recipes(request, catalog).filter(
            visibility="public", archived_at__isnull=True
        )
        binding = [request.catalog_grant.pk, catalog, query, sort, limit, maximum]
        cursor = params.get("cursor")
        boundary = None
        if cursor:
            try:
                if len(cursor) > 4096:
                    raise ValueError
                payload = signing.loads(cursor, salt="catalog-v2", max_age=3600)
                if payload["binding"] != binding:
                    raise ValueError
                ceiling, boundary, started = (
                    payload["ceiling"],
                    payload["last"],
                    payload["started"],
                )
            except (signing.BadSignature, ValueError, KeyError, TypeError):
                raise ValidationError("Invalid or expired cursor; restart this search.")
        else:
            ceiling = Recipe.objects.aggregate(n=Max("pk"))["n"] or 0
            started = timezone.now().isoformat()
        recipes = search_recipes(
            recipes.filter(pk__lte=ceiling, finalized_at__lte=started), query
        )
        if maximum is not None:
            recipes = recipes.filter(total_time__lte=maximum)
        if sort == "quickest":
            recipes = recipes.annotate(
                time_unknown=Case(
                    When(total_time__isnull=True, then=Value(1)),
                    default=Value(0),
                    output_field=IntegerField(),
                ),
                sort_time=Coalesce("total_time", Value(0)),
            )
            order = ["time_unknown", "sort_time", "-id"]
        else:
            order = (["-search_rank"] if sort == "relevance" else []) + [
                "-finalized_at",
                "-id",
            ]
        if boundary:
            after, prefix = Q(pk__in=[]), Q()
            for field, value in zip(order, boundary, strict=True):
                name = field.lstrip("-")
                after |= prefix & Q(
                    **{name + ("__lt" if field.startswith("-") else "__gt"): value}
                )
                prefix &= Q(**{name: value})
            recipes = recipes.filter(after)
        rows = list(recipes.order_by(*order)[: limit + 1])
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            values = [getattr(last, f.lstrip("-")) for f in order]
            values = [v.isoformat() if hasattr(v, "isoformat") else v for v in values]
            next_cursor = signing.dumps(
                {
                    "binding": binding,
                    "ceiling": ceiling,
                    "started": started,
                    "last": values,
                },
                salt="catalog-v2",
                compress=True,
            )
        return Response(
            {"results": [card(r) for r in rows[:limit]], "next_cursor": next_cursor}
        )


class RecipeView(CatalogView):
    def get(self, request, public_id):
        recipe = get_object_or_404(granted_recipes(request), public_id=public_id)
        if recipe.archived_at or recipe.visibility != "public":
            return Response(
                {
                    "document": None,
                    "status": {
                        "recipe_id": str(public_id),
                        "availability": "unavailable",
                        "feedback": None,
                    },
                },
                status=410,
            )
        try:
            document = recipe_document(recipe)
        except DocumentError:
            error = APIException(
                "This recipe document is temporarily unavailable.",
                code="document_unavailable",
            )
            error.status_code = 503
            raise error
        return Response(
            {
                "document": document,
                "status": {
                    "recipe_id": str(public_id),
                    "availability": "available",
                    "feedback": None,
                },
            }
        )


class V2ContractView(ContractView):
    def get(self, request):
        return Response(
            json.loads(
                (settings.BASE_DIR / "docs/api/catalog-v2.openapi.json").read_text()
            )
        )


class DocumentSchemaView(ContractView):
    def get(self, request):
        return Response(
            json.loads(
                (
                    settings.BASE_DIR / "docs/api/RecipeDocumentV1.schema.json"
                ).read_text()
            )
        )
