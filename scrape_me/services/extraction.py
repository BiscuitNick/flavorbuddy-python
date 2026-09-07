import json
from recipe_scrapers import scrape_html
from rest_framework.exceptions import ValidationError
from scrape_me.api.serializers import ContentSerializer
from scrape_me.api.errors import ImportFailure
from scrape_me.services.fetching import fetch_html
from scrape_me.views import normalize_description, normalize_instructions


def validate_preview(data):
    serializer = ContentSerializer(data=data)
    try:
        serializer.is_valid(raise_exception=True)
    except ValidationError:
        raise ImportFailure(
            "The extracted content was invalid. Enter or correct the recipe manually."
        ) from None
    return serializer.validated_data


def extract_url(url):
    html, final_url = fetch_html(url)
    try:
        scraper = scrape_html(html, org_url=final_url, supported_only=False)
        raw = scraper.to_json()
        if isinstance(raw, str):
            raw = json.loads(raw)
        for field in ("title", "author", "yields", "image"):
            if raw.get(field) is None:
                raw[field] = ""
        raw["instructions"] = normalize_instructions(raw.get("instructions"))
        raw["description"] = normalize_description(raw.get("description"))
        raw["source_url"] = final_url
        return validate_preview(raw)
    except ImportFailure:
        raise
    except Exception:
        raise ImportFailure() from None
