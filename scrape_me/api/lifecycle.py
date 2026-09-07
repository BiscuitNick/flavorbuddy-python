"""Recipe content lifecycle; visibility is independent of finalization."""

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.exceptions import ValidationError, APIException
from scrape_me.models import Recipe
from .serializers import ContentSerializer, RecipeSerializer
from .views import owned, object_body, Conflict


def public_recipes():
    return Recipe.objects.filter(
        state="finalized", visibility="public", archived_at__isnull=True
    )


def public_data(recipe):
    # Never serialize notes, favorites, owner identity, or private photos publicly.
    return {
        **ContentSerializer(recipe).data,
        "id": recipe.pk,
        "public_id": str(recipe.public_id),
        "state": recipe.state,
        "visibility": recipe.visibility,
        "finalized_at": recipe.finalized_at,
        "inspired_by_recipe_id": (
            str(recipe.inspired_by.public_id) if recipe.inspired_by_id else None
        ),
        "provenance": recipe.provenance,
    }


class FinalizeView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        recipe = get_object_or_404(owned(request).select_for_update(), pk=pk)
        if recipe.state == "finalized":
            return Response(RecipeSerializer(recipe).data)
        if object_body(request).get("version") != recipe.version:
            raise Conflict()
        validator = RecipeSerializer(
            recipe, data={}, partial=True, context={"require_complete": True}
        )
        validator.is_valid(raise_exception=True)
        recipe.state = "finalized"
        recipe.version += 1
        recipe.save()
        return Response(RecipeSerializer(recipe).data)


class VisibilityView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        recipe = get_object_or_404(owned(request).select_for_update(), pk=pk)
        body = object_body(request)
        if recipe.state != "finalized":
            raise Conflict("Finalize your recipe before sharing it.")
        if body.get("version") != recipe.version:
            raise Conflict()
        visibility = body.get("visibility")
        if visibility not in ("private", "public"):
            raise ValidationError({"visibility": "Choose private or public."})
        recipe.visibility = visibility
        recipe.version += 1
        recipe.save(update_fields=["visibility", "version", "updated_at"])
        return Response(RecipeSerializer(recipe).data)


def make_variation(source, owner):
    fields = [
        f for f in Recipe.CONTENT_FIELDS if f not in ("public_id", "inspired_by_id")
    ]
    return Recipe.objects.create(
        owner=owner, inspired_by=source, **{f: getattr(source, f) for f in fields}
    )


class VariationView(APIView):
    @transaction.atomic
    def post(self, request, pk):
        source = get_object_or_404(
            Recipe.objects.select_for_update()
            .filter(archived_at__isnull=True)
            .filter(Q(owner=request.user) | Q(state="finalized", visibility="public")),
            pk=pk,
        )
        if source.state != "finalized":
            raise Conflict("This recipe is still a draft; edit it directly.")
        recipe = make_variation(source, request.user)
        return Response(RecipeSerializer(recipe).data, status=201)


class SharedView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, public_id=None):
        if public_id:
            visible = Q(visibility="public")
            if request.user.is_authenticated:
                visible |= Q(owner=request.user)
            recipe = get_object_or_404(
                Recipe.objects.filter(visible), public_id=public_id, state="finalized"
            )
            if recipe.archived_at:
                error = APIException("This recipe is no longer available.")
                error.status_code = 410
                raise error
            return Response(public_data(recipe))
        try:
            page = int(request.query_params.get("page", 1))
            if page < 1:
                raise ValueError
        except ValueError:
            raise ValidationError("Use a positive page number.")
        from scrape_me.services.search import search_recipes

        recipes = search_recipes(
            public_recipes(), request.query_params.get("q", "")[:200].strip()
        ).order_by("-search_rank", "title", "id")
        count = recipes.count()
        return Response(
            {
                "results": [
                    public_data(r) for r in recipes[(page - 1) * 24 : page * 24]
                ],
                "count": count,
                "page": page,
                "has_next": page * 24 < count,
            }
        )
