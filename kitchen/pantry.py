from scrape_me.api.starter import available_starters
import re
import unicodedata
from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from scrape_me.api.views import Conflict, object_body
from scrape_me.models import Recipe, StarterRecipe
from .models import PantryItem, Preferences


class PantrySerializer(serializers.ModelSerializer):
    class Meta:
        model = PantryItem
        fields = [
            "id",
            "name",
            "quantity",
            "location",
            "running_low",
            "use_soon",
            "used_up",
            "version",
        ]
        read_only_fields = ["id", "version"]


class PantryView(APIView):
    def get(self, request):
        return Response(
            {
                "items": PantrySerializer(
                    PantryItem.objects.filter(owner=request.user).order_by(
                        "used_up", "location", "name", "id"
                    ),
                    many=True,
                ).data
            }
        )

    def post(self, request):
        serializer = PantrySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            from django.contrib.auth import get_user_model

            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            if PantryItem.objects.filter(owner=request.user).count() >= 500:
                raise serializers.ValidationError(
                    "Your pantry can hold 500 items. Delete used-up items to make room."
                )
            serializer.save(owner=request.user)
        return Response(serializer.data, status=201)

    def patch(self, request, pk):
        with transaction.atomic():
            item = get_object_or_404(
                PantryItem.objects.select_for_update(), pk=pk, owner=request.user
            )
            body = object_body(request)
            if type(body.get("version")) is not int or body["version"] != item.version:
                raise Conflict("This pantry item changed. Reload before saving.")
            serializer = PantrySerializer(item, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            serializer.save(version=item.version + 1)
        return Response(serializer.data)

    def delete(self, request, pk):
        get_object_or_404(PantryItem, pk=pk, owner=request.user).delete()
        return Response(status=204)


class PreferenceSerializer(serializers.ModelSerializer):
    exclusions = serializers.ListField(
        child=serializers.CharField(max_length=80), max_length=50
    )
    diet = serializers.ChoiceField(choices=["", "vegetarian", "vegan"])

    class Meta:
        model = Preferences
        fields = ["exclusions", "diet"]


class PreferenceView(APIView):
    def get(self, request):
        prefs, _ = Preferences.objects.get_or_create(owner=request.user)
        return Response(PreferenceSerializer(prefs).data)

    def put(self, request):
        prefs, _ = Preferences.objects.get_or_create(owner=request.user)
        serializer = PreferenceSerializer(prefs, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


UNITS = {
    "g",
    "kg",
    "gram",
    "grams",
    "ml",
    "l",
    "oz",
    "lb",
    "lbs",
    "cup",
    "cups",
    "tsp",
    "tbsp",
    "teaspoon",
    "teaspoons",
    "tablespoon",
    "tablespoons",
    "pound",
    "pounds",
}
ALIASES = {
    "tomatoes": "tomato",
    "potatoes": "potato",
    "onions": "onion",
    "eggs": "egg",
    "chickpeas": "chickpea",
    "carrots": "carrot",
    "lemons": "lemon",
    "cloves": "clove",
}
MEAT = {
    "beef",
    "pork",
    "chicken",
    "bacon",
    "ham",
    "turkey",
    "lamb",
    "fish",
    "salmon",
    "tuna",
    "shrimp",
    "prawn",
    "gelatin",
    "anchovy",
    "lard",
    "sausage",
    "chorizo",
}
DAIRY = {
    "milk",
    "cheese",
    "butter",
    "cream",
    "yogurt",
    "whey",
    "casein",
    "ghee",
    "egg",
    "honey",
}


def normalize(value):
    value = unicodedata.normalize("NFKC", value).lower()
    value = value.split(",")[0]
    words = re.findall(r"[a-z]+", value)
    # Only remove units at the start; retain ambiguous preparation/variety words.
    while words and words[0] in UNITS:
        words.pop(0)
    return " ".join(ALIASES.get(word, word) for word in words)


def contains_term(text, term):
    return bool(term and re.search(r"(?<!\w)" + re.escape(term) + r"(?!\w)", text))


class MatchView(APIView):
    def get(self, request):
        inventory = list(PantryItem.objects.filter(owner=request.user, used_up=False))
        names = {
            normalize(item.name): item for item in inventory if normalize(item.name)
        }
        prefs, _ = Preferences.objects.get_or_create(owner=request.user)
        exclusions = [normalize(term) for term in prefs.exclusions]
        if prefs.diet in {"vegetarian", "vegan"}:
            exclusions += list(MEAT)
        if prefs.diet == "vegan":
            exclusions += list(DAIRY)
        candidates = []
        excluded = 0
        # Bounded to the newest 500 private recipes plus the curated catalog.
        rows = [
            ("private", r.pk, r.title, r.ingredients)
            for r in Recipe.objects.filter(
                owner=request.user, state="finalized", archived_at__isnull=True
            )[:500]
        ]
        rows += [
            ("starter", r.pk, r.recipe.title, r.recipe.ingredients)
            for r in available_starters()[:1000]
        ]
        for kind, pk, title, ingredients in rows:
            if any(
                contains_term(normalize(raw), term)
                for raw in ingredients
                for term in exclusions
            ):
                excluded += 1
                continue
            found = []
            missing = []
            uncertain = []
            for raw in ingredients:
                name = normalize(raw)
                item = names.get(name)
                if item:
                    found.append(
                        {
                            "ingredient": raw,
                            "pantry_item_id": item.pk,
                            "name": item.name,
                            "explanation": f"Name matches {item.name} in {item.location}; check quantity.",
                            "use_soon": item.use_soon,
                        }
                    )
                else:
                    missing.append(raw)
                    possible = [
                        i.name for term, i in names.items() if contains_term(name, term)
                    ]
                    if possible:
                        uncertain.append(
                            {
                                "ingredient": raw,
                                "possible_items": possible,
                                "explanation": "Partial name match only; confirm the ingredient and variety.",
                            }
                        )
            candidates.append(
                {
                    "kind": kind,
                    "id": pk,
                    "title": title,
                    "matched": found,
                    "missing": missing,
                    "uncertain": uncertain,
                }
            )
        candidates.sort(
            key=lambda r: (
                -sum(x["use_soon"] for x in r["matched"]),
                -len(r["matched"]),
                len(r["missing"]),
                r["title"],
            )
        )
        return Response(
            {
                "matches": candidates[:24],
                "excluded_count": excluded,
                "notice": "Name matches do not confirm quantities, freshness or dietary safety. Check the full recipe and ingredient labels. Partial matches remain in the missing list.",
                "coverage": "Newest 500 private recipes and up to 1,000 starters.",
            }
        )


class CapabilitiesView(APIView):
    def get(self, request):
        from django.conf import settings
        from .models import CapabilityGrant

        return Response(
            {
                "manual_pantry": True,
                "matching": True,
                "private_photos": settings.PRIVATE_PHOTO_BACKEND != "disabled",
                "capture_demo": not settings.PRODUCTION
                and settings.CAPTURE_PROVIDER == "fixture"
                and CapabilityGrant.objects.filter(
                    owner=request.user, capture_enabled=True
                ).exists(),
            }
        )


class KitchenExportView(APIView):
    def get(self, request):
        from .models import PrivatePhoto, CaptureJob
        from .photos import representation
        from .jobs import describe

        prefs, _ = Preferences.objects.get_or_create(owner=request.user)
        response = Response(
            {
                "pantry": PantrySerializer(
                    PantryItem.objects.filter(owner=request.user).order_by("id"),
                    many=True,
                ).data,
                "preferences": PreferenceSerializer(prefs).data,
                "photos": [
                    representation(photo)
                    for photo in PrivatePhoto.objects.filter(owner=request.user)
                ],
                "captures": [
                    describe(job)
                    for job in CaptureJob.objects.filter(owner=request.user)
                ],
            }
        )
        response["Content-Disposition"] = (
            'attachment; filename="flavorbuddy-kitchen.json"'
        )
        return response
