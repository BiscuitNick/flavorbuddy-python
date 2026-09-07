"""Normalization helpers retained for compatibility; customer APIs live in api/."""

from collections.abc import Iterable
from pathlib import Path
from typing import Any, List
from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.http import require_GET


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


class RecipeStructError(RuntimeError):
    """Raised when the RecipeStruct integration cannot complete."""


def _load_system_prompt() -> str:
    prompt_path = (
        Path(__file__).resolve().parent / "prompts" / "raw-text-system-prompt.md"
    )
    if not prompt_path.exists():
        raise RecipeStructError("System prompt file not found.")

    return prompt_path.read_text(encoding="utf-8").strip()


_RECIPE_SYSTEM_PROMPT = None


def get_recipe_system_prompt() -> str:
    global _RECIPE_SYSTEM_PROMPT
    if _RECIPE_SYSTEM_PROMPT is None:
        _RECIPE_SYSTEM_PROMPT = _load_system_prompt()
    return _RECIPE_SYSTEM_PROMPT


@require_GET
def home(request):
    index = settings.BASE_DIR / "frontend" / "dist" / "index.html"
    if not index.exists():
        return HttpResponse(
            "Frontend assets are not built. Run npm ci and npm run build in frontend/.",
            status=503,
            content_type="text/plain",
        )
    response = HttpResponse(index.read_text(), content_type="text/html")
    response["Cache-Control"] = "no-store"
    return response
