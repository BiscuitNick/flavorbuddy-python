import json

from collections.abc import Iterable
from typing import Any, Dict, List
from urllib.parse import urlparse

import math

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from recipe_scrapers import scrape_me

from .models import Recipe


def normalize_recipe_url(url: str) -> str:
    """Return the recipe URL without any trailing slash."""

    return url.strip().rstrip("/")


def normalize_instructions(raw_instructions: Any) -> List[str]:
    """Convert instructions payload into a list of cleaned steps."""

    if not raw_instructions:
        return []

    if isinstance(raw_instructions, str):
        normalized = raw_instructions.replace("\r\n", "\n")
        steps = [step.strip() for step in normalized.split("\n") if step.strip()]
        return steps or [raw_instructions.strip()]

    if isinstance(raw_instructions, Iterable):
        cleaned_steps: List[str] = []
        for step in raw_instructions:
            if isinstance(step, str):
                trimmed = step.strip()
                if trimmed:
                    cleaned_steps.append(trimmed)
        return cleaned_steps

    return []


def serialize_recipe(recipe: Recipe) -> Dict[str, Any]:
    """Convert a Recipe instance into a JSON-serializable dict."""

    return {
        "id": recipe.id,
        "source_url": recipe.source_url,
        "title": recipe.title,
        "author": recipe.author,
        "total_time": recipe.total_time,
        "yields": recipe.yields,
        "image": recipe.image,
        "ingredients": recipe.ingredients,
        "instructions": recipe.instructions,
        "extra": recipe.extra,
        "created_at": recipe.created_at.isoformat(),
        "updated_at": recipe.updated_at.isoformat(),
    }

@require_GET
def test_scrape(request):
    """Fetch recipe data and return the scraper payload as JSON."""
    scraper = scrape_me("https://www.allrecipes.com/recipe/16954/chinese-chicken-fried-rice-ii/")
    data = scraper.to_json()
    if isinstance(data, str):
        data = json.loads(data)
    return JsonResponse(data)


@require_GET
def parse_recipe_url(request):
    """Scrape a recipe URL provided via the `url` query parameter."""
    recipe_url = request.GET.get("url")
    if not recipe_url:
        return JsonResponse({"error": "Missing required 'url' query parameter."}, status=400)

    normalized_url = normalize_recipe_url(recipe_url)

    parsed = urlparse(normalized_url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return JsonResponse({"error": "Invalid URL provided."}, status=400)

    existing_recipe = Recipe.objects.filter(source_url=normalized_url).first()
    if existing_recipe:
        return JsonResponse(serialize_recipe(existing_recipe))

    try:
        scraper = scrape_me(normalized_url)
        data = scraper.to_json()
        if isinstance(data, str):
            data = json.loads(data)
    except Exception as exc:  # recipe_scrapers raises various exceptions per site
        return JsonResponse({"error": str(exc)}, status=400)

    ingredients = data.get("ingredients") or []
    if isinstance(ingredients, str):
        ingredients = [line.strip() for line in ingredients.splitlines() if line.strip()]

    instructions = normalize_instructions(data.get("instructions"))

    total_time = data.get("total_time")
    try:
        total_time_value = int(total_time) if total_time is not None else None
    except (TypeError, ValueError):
        total_time_value = None

    known_keys = {
        "title",
        "author",
        "total_time",
        "yields",
        "image",
        "ingredients",
        "instructions",
    }
    extra = {
        key: value
        for key, value in data.items()
        if key not in known_keys
    }

    recipe = Recipe.objects.create(
        source_url=normalized_url,
        title=data.get("title", ""),
        author=data.get("author", ""),
        total_time=total_time_value,
        yields=data.get("yields", ""),
        image=data.get("image", ""),
        ingredients=ingredients,
        instructions=instructions,
        extra=extra,
    )

    return JsonResponse(serialize_recipe(recipe))


@require_GET
def home(request):
    return render(request, "scrape_me/home.html")


@require_GET
def get_recipes(request):
    """Return a JSON list of stored recipes with optional search and pagination."""

    query = (request.GET.get("q") or "").strip()
    page_raw = request.GET.get("page", "1")
    page_size_raw = request.GET.get("page_size", "10")

    try:
        page = int(page_raw)
        if page < 1:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid 'page' parameter. Must be a positive integer."}, status=400)

    try:
        page_size = int(page_size_raw)
        if page_size < 1 or page_size > 100:
            raise ValueError
    except (TypeError, ValueError):
        return JsonResponse({"error": "Invalid 'page_size' parameter. Must be between 1 and 100."}, status=400)

    recipes_qs = Recipe.objects.all()
    if query:
        recipes_qs = recipes_qs.filter(title__icontains=query)

    total_items = recipes_qs.count()
    total_pages = math.ceil(total_items / page_size) if total_items else 0

    offset = (page - 1) * page_size
    recipes_slice = list(recipes_qs[offset : offset + page_size])

    payload = {
        "query": query,
        "results": [serialize_recipe(recipe) for recipe in recipes_slice],
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "total_pages": total_pages,
            "has_next": offset + page_size < total_items,
            "has_previous": page > 1 and total_items > 0,
        },
    }

    return JsonResponse(payload)
