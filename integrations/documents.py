"""Lossless, deterministic projection of immutable content; no inferred cooking facts."""

import json
from functools import lru_cache
from uuid import uuid5
from django.conf import settings
from jsonschema import Draft202012Validator, FormatChecker


@lru_cache(maxsize=1)
def document_validator():
    schema = json.loads(
        (settings.BASE_DIR / "docs/api/RecipeDocumentV1.schema.json").read_text()
    )
    return Draft202012Validator(schema, format_checker=FormatChecker())


def recipe_document(recipe):
    provenance = recipe.provenance
    source_url = recipe.source_url or provenance.get("source_url") or None
    sources = []
    if source_url or provenance:
        sources.append(
            {
                "id": "src-original",
                "url": source_url,
                "author": recipe.author or None,
                "repository_url": provenance.get("repository") or None,
                "repository_revision": provenance.get("revision") or None,
                "path": provenance.get("path") or None,
                "source_sha256": provenance.get("sha256") or None,
                "license": {
                    "identifier": provenance.get("license") or None,
                    "url": provenance.get("license_url") or None,
                    "rights_basis": "source_license"
                    if provenance.get("license")
                    else "unknown",
                },
                "legacy_locator": None,
            }
        )

    def refs(field, index):
        return (
            [{"source_id": "src-original", "locator": f"{field}[{index}]"}]
            if sources
            else []
        )

    images = None
    image = provenance.get("image_storage", {})
    if image.get("sha256") and recipe.image:
        images = [
            {
                "id": "img-cover",
                "asset_id": str(uuid5(recipe.public_id, "image:" + image["sha256"])),
                "sha256": image["sha256"],
                "alt_text": None,
                "origin": "source",
                "source_url": recipe.image,
                "license": provenance.get("license") or None,
            }
        ]
    document = {
        "schema_version": "1.0.0",
        "recipe_id": str(recipe.public_id),
        "finalized_at": recipe.finalized_at.isoformat(),
        "title": recipe.title,
        "description": recipe.description or None,
        "language": None,
        "yield": {
            "original_text": recipe.yields or None,
            "quantity": None,
            "unit": None,
        },
        "provenance": {
            "origin": "derived"
            if recipe.inspired_by_id
            else "ai_generated"
            if recipe.type == "ai_generated"
            else "imported"
            if sources
            else "manual",
            "sources": sources,
            "inspired_by_recipe_id": str(recipe.inspired_by.public_id)
            if recipe.inspired_by_id
            else None,
            "original_notes": provenance.get("source_notes") or None,
        },
        "ingredient_groups": None,
        "ingredients": [
            {
                "id": f"ing-{i + 1}",
                "original_text": text,
                "name": None,
                "quantity": None,
                "unit": None,
                "preparation": None,
                "group_id": None,
                "optional": None,
                "source_refs": refs("ingredients", i),
            }
            for i, text in enumerate(recipe.ingredients)
        ],
        "step_groups": None,
        "steps": [
            {
                "id": f"step-{i + 1}",
                "position": i + 1,
                "original_text": text,
                "instruction": text,
                "group_id": None,
                "ingredient_refs": None,
                "unresolved_ingredient_text": None,
                "equipment_refs": None,
                "unresolved_equipment_text": None,
                "timers": None,
                "source_refs": refs("instructions", i),
            }
            for i, text in enumerate(recipe.instructions)
        ],
        "equipment": None,
        "timing": {
            "original_text": None,
            "prep": None,
            "cook": None,
            "rest": None,
            "total": None
            if recipe.total_time is None
            else {
                "minimum_seconds": recipe.total_time * 60,
                "maximum_seconds": recipe.total_time * 60,
                "original_text": None,
                "basis": "source_explicit" if source_url else "editor_authored",
            },
        },
        "images": images,
        "tags": None,
    }
    document_validator().validate(document)
    return document
