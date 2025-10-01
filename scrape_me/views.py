import json
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Dict, List
from urllib.parse import urlparse

import math

from django.conf import settings
from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.db.models import F
from django.utils import timezone
from recipe_scrapers import scrape_me

from .models import Recipe, RecipeType


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


def normalize_description(raw_description: Any) -> str:
    """Convert description payload to a cleaned string."""

    if not raw_description:
        return ""

    if isinstance(raw_description, str):
        return raw_description.strip()

    if isinstance(raw_description, dict):
        for key in ("text", "description", "value"):
            value = raw_description.get(key)
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
        return ""

    if isinstance(raw_description, Iterable):
        parts: List[str] = []
        for item in raw_description:
            if isinstance(item, str):
                trimmed = item.strip()
                if trimmed:
                    parts.append(trimmed)
            elif isinstance(item, dict):
                nested = normalize_description(item)
                if nested:
                    parts.append(nested)
            else:
                nested = normalize_description(item)
                if nested:
                    parts.append(nested)

        return " ".join(parts)

    coerced = str(raw_description).strip()
    return coerced if coerced else ""


def serialize_recipe(recipe: Recipe) -> Dict[str, Any]:
    """Convert a Recipe instance into a JSON-serializable dict."""

    return {
        "id": recipe.id,
        "source_url": recipe.source_url,
        "description": recipe.description,
        "title": recipe.title,
        "author": recipe.author,
        "total_time": recipe.total_time,
        "yields": recipe.yields,
        "image": recipe.image,
        "ingredients": recipe.ingredients,
        "instructions": recipe.instructions,
        "views": recipe.views,
        "type": recipe.type,
        "created_at": recipe.created_at.isoformat(),
        "updated_at": recipe.updated_at.isoformat(),
    }

@require_GET
def test_scrape(request):
    """Fetch recipe data and return the scraper payload as JSON."""
    scraper = scrape_me("https://cooking.nytimes.com/recipes/1022664-slow-cooker-lasagna")
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
        Recipe.objects.filter(pk=existing_recipe.pk).update(
            views=F("views") + 1,
            updated_at=timezone.now(),
        )
        existing_recipe.refresh_from_db(fields=["views", "updated_at"])
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

    description_value = normalize_description(data.get("description"))

    recipe = Recipe.objects.create(
        source_url=normalized_url,
        description=description_value,
        title=data.get("title", ""),
        author=data.get("author", ""),
        total_time=total_time_value,
        yields=data.get("yields", ""),
        image=data.get("image", ""),
        ingredients=ingredients,
        instructions=instructions,
        views=1,
        type=RecipeType.URL,
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


class RecipeStructError(RuntimeError):
    """Raised when the RecipeStruct integration cannot complete."""


def _load_system_prompt() -> str:
    prompt_path = Path(settings.BASE_DIR).parent / "raw-text-system-prompt.md"
    if not prompt_path.exists():
        raise RecipeStructError("System prompt file not found.")

    return prompt_path.read_text(encoding="utf-8").strip()


_RECIPE_SYSTEM_PROMPT = None


def get_recipe_system_prompt() -> str:
    global _RECIPE_SYSTEM_PROMPT
    if _RECIPE_SYSTEM_PROMPT is None:
        _RECIPE_SYSTEM_PROMPT = _load_system_prompt()
    return _RECIPE_SYSTEM_PROMPT


def _invoke_recipe_struct_model(source_url: str | None, raw_text: str) -> Dict[str, Any]:
    try:
        import replicate
    except ImportError as exc:  # pragma: no cover - environment specific
        raise RecipeStructError("replicate package is not installed.") from exc

    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        raise RecipeStructError("Missing REPLICATE_API_TOKEN environment variable.")

    prompt_payload = json.dumps(
        {
            "source_url": source_url,
            "raw_text": raw_text,
        },
        ensure_ascii=False,
    )

    input_payload = {
        "prompt": prompt_payload,
        "messages": [],
        "verbosity": "low",
        "image_input": [],
        "system_prompt": get_recipe_system_prompt(),
        "reasoning_effort": "minimal",
    }

    try:
        raw_output = replicate.run(
            "openai/gpt-5-nano",
            input=input_payload,
            api_token=api_token,
        )
    except Exception as exc:  # pragma: no cover - network/library specific
        raise RecipeStructError(f"Failed to invoke Replicate: {exc}") from exc

    def normalize_output(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, bytes):
            return value.decode('utf-8', errors='replace').strip()
        if isinstance(value, list):
            parts = [normalize_output(item) for item in value]
            return ''.join(part for part in parts if part)
        if isinstance(value, dict):
            return json.dumps(value)
        return str(value).strip()

    output_text = normalize_output(raw_output)
    if not output_text:
        raise RecipeStructError("Empty response from Replicate model.")

    try:
        parsed = json.loads(output_text)
    except json.JSONDecodeError as exc:
        raise RecipeStructError("Invalid JSON returned by Replicate model.") from exc

    if not isinstance(parsed, dict):
        raise RecipeStructError("Replicate response must be a JSON object.")

    return parsed


def _coerce_optional_string(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return str(value)


@csrf_exempt
@require_POST
def convert_raw_recipe(request):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    raw_text = payload.get("raw_text")
    if not isinstance(raw_text, str) or not raw_text.strip():
        return JsonResponse({"error": "Field 'raw_text' is required."}, status=400)

    source_url = _coerce_optional_string(payload.get("source_url"))

    try:
        result = _invoke_recipe_struct_model(source_url, raw_text)
    except RecipeStructError as exc:
        return JsonResponse({"error": str(exc)}, status=502)

    return JsonResponse(result)
