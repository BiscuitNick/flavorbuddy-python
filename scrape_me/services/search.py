"""Shared literal phrase search; callers must apply their visibility/grants first."""

from django.db.models import Case, IntegerField, Q, Value, When


def search_recipes(recipes, query):
    if not query:
        return recipes.annotate(search_rank=Value(0, output_field=IntegerField()))
    return recipes.filter(
        Q(title__icontains=query)
        | Q(description__icontains=query)
        | Q(ingredients__icontains=query)
    ).annotate(
        search_rank=Case(
            When(title__iexact=query, then=Value(3)),
            When(title__icontains=query, then=Value(2)),
            When(description__icontains=query, then=Value(1)),
            default=Value(0),
            output_field=IntegerField(),
        )
    )
