"""Legacy starter aliases point to the same immutable Recipe used everywhere else."""

from django.db import transaction
from scrape_me.models import Recipe, StarterRecipe


@transaction.atomic
def attach_recipe(starter):
    starter = StarterRecipe.objects.select_for_update().get(pk=starter.pk)
    if starter.recipe_id:
        return starter.recipe
    fields = (
        "title",
        "description",
        "author",
        "total_time",
        "yields",
        "source_url",
        "image",
        "ingredients",
        "instructions",
    )
    provenance = dict(starter.provenance)
    if starter.content.get("notes"):
        provenance["source_notes"] = starter.content["notes"]
    recipe = Recipe.objects.create(
        state="finalized",
        visibility="public",
        provenance=provenance,
        source_markdown=starter.source_markdown,
        **{k: v for k, v in starter.content.items() if k in fields}
    )
    starter.recipe = recipe
    starter.save(update_fields=["recipe"])
    return recipe
