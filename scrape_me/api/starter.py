from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from scrape_me.models import StarterRecipe, Recipe
from .serializers import RecipeSerializer


def serialize(starter):
    from .lifecycle import public_data

    if starter.recipe_id:
        return {**public_data(starter.recipe), "id": starter.pk, "slug": starter.slug}
    raise ValueError("Starter alias must be attached to a finalized recipe before publishing.")


def available_starters():
    return StarterRecipe.objects.select_related("recipe").filter(
        recipe__state="finalized",
        recipe__visibility="public",
        recipe__archived_at__isnull=True,
    )


class StarterView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, pk=None):
        if pk is not None:
            return Response(serialize(get_object_or_404(available_starters(), pk=pk)))
        try:
            page = int(request.query_params.get("page", 1))
            if page < 1:
                raise ValueError
        except ValueError:
            raise ValidationError("Use a positive page number.")
        from scrape_me.services.search import search_recipes

        matches = search_recipes(
            Recipe.objects.all(), request.query_params.get("q", "")[:200].strip()
        )
        recipes = available_starters().filter(recipe__in=matches)
        count = recipes.count()
        return Response(
            {
                "results": [serialize(r) for r in recipes[(page - 1) * 24 : page * 24]],
                "count": count,
                "page": page,
                "has_next": page * 24 < count,
            }
        )


class SaveStarterView(APIView):
    permission_classes = [IsAuthenticated]

    @transaction.atomic
    def post(self, request, pk):
        starter = get_object_or_404(available_starters(), pk=pk)
        from scrape_me.services.starter_identity import attach_recipe
        from .lifecycle import make_variation

        source = attach_recipe(starter)
        # Legacy save action keeps retry behavior, matching identity rather than source URL.
        recipe = (
            Recipe.objects.filter(
                owner=request.user, inspired_by=source, archived_at__isnull=True
            )
            .order_by("id")
            .first()
        )
        created = recipe is None
        if created:
            recipe = make_variation(source, request.user)
        return Response(RecipeSerializer(recipe).data, status=201 if created else 200)
