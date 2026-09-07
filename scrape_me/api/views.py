import logging
import hashlib
import json
from uuid import UUID
from datetime import timedelta
from django.db import transaction, IntegrityError
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError, APIException
from scrape_me.models import Recipe, ImportDraft
from scrape_me.api.serializers import RecipeSerializer
from scrape_me.services.budgets import reserve

logger = logging.getLogger("flavorbuddy")


class Conflict(APIException):
    status_code = 409
    default_code = "conflict"
    default_detail = "This recipe changed. Your edits are preserved; reload the latest version before saving."


def object_body(request):
    if not isinstance(request.data, dict):
        raise ValidationError("Send a JSON object.")
    return request.data


def owned(request):
    return Recipe.objects.filter(
        owner=request.user, archived_at__isnull=True
    ).prefetch_related("private_photos")


class RecipesView(APIView):
    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
            size = int(request.query_params.get("page_size", 24))
            if page < 1 or not 1 <= size <= 100:
                raise ValueError
        except ValueError:
            raise ValidationError(
                "Use a positive page and a page_size between 1 and 100."
            )
        recipes = owned(request).filter(
            title__icontains=request.query_params.get("q", "")[:255]
        )
        if request.query_params.get("favorite") == "true":
            recipes = recipes.filter(favorite=True)
        count = recipes.count()
        return Response(
            {
                "results": RecipeSerializer(
                    recipes[(page - 1) * size : page * size], many=True
                ).data,
                "count": count,
                "page": page,
                "has_next": page * size < count,
            }
        )

    def post(self, request):
        body = object_body(request)
        with transaction.atomic():
            draft = None
            if body.get("import_id") is not None:
                draft = get_object_or_404(
                    ImportDraft.objects.select_for_update(),
                    pk=serializers.IntegerField(min_value=1).run_validation(
                        body["import_id"]
                    ),
                    owner=request.user,
                )
                if draft.state == "saved":
                    if draft.recipe_id is None or draft.recipe.archived_at is not None:
                        raise Conflict(
                            "This saved recipe was deleted. Start a new draft."
                        )
                    return Response(RecipeSerializer(draft.recipe).data)
                if draft.state not in ("ready", "failed"):
                    raise Conflict("The import is still processing. Try again shortly.")
            state = body.get("state", "draft")
            if (
                state not in ("draft", "finalized")
                or body.get("visibility", "private") != "private"
            ):
                raise ValidationError(
                    "Create a private draft or finalized recipe. Share it separately."
                )
            serializer = RecipeSerializer(
                data=body, context={"require_complete": state == "finalized"}
            )
            serializer.is_valid(raise_exception=True)
            data = serializer.validated_data
            data["source_url"] = data.get("source_url") or None
            try:
                with transaction.atomic():
                    recipe = Recipe.objects.create(
                        owner=request.user, state=state, **data
                    )
            except IntegrityError:
                raise Conflict(
                    "You already saved this source. Open the existing recipe to edit it."
                )
            if draft:
                draft.recipe = recipe
                draft.state = "saved"
                draft.save(update_fields=["recipe", "state", "updated_at"])
            return Response(RecipeSerializer(recipe).data, status=201)


class RecipeView(APIView):
    def get(self, request, pk):
        return Response(RecipeSerializer(get_object_or_404(owned(request), pk=pk)).data)

    def patch(self, request, pk):
        body = object_body(request)
        with transaction.atomic():
            recipe = get_object_or_404(owned(request).select_for_update(), pk=pk)
            if body.get("version") != recipe.version:
                raise Conflict()
            if any(
                key in body
                for key in (
                    "state",
                    "visibility",
                    "inspired_by_recipe_id",
                    "public_id",
                    "provenance",
                    "finalized_at",
                )
            ):
                raise ValidationError(
                    "Use the finalize, visibility, or variation action to change recipe state."
                )
            if recipe.state == "finalized" and any(
                key not in ("version", "notes", "favorite") for key in body
            ):
                raise Conflict(
                    "This recipe is finalized. Make a variation to change its content."
                )
            serializer = RecipeSerializer(
                recipe,
                data=body,
                partial=True,
                context={"require_complete": recipe.state == "finalized"},
            )
            serializer.is_valid(raise_exception=True)
            for key, value in serializer.validated_data.items():
                setattr(recipe, key, value)
            recipe.source_url = recipe.source_url or None
            recipe.version += 1
            try:
                with transaction.atomic():
                    recipe.save()
            except IntegrityError:
                raise Conflict("You already have a recipe with this source URL.")
        return Response(RecipeSerializer(recipe).data)

    def delete(self, request, pk):
        with transaction.atomic():
            recipe = get_object_or_404(owned(request).select_for_update(), pk=pk)
            if recipe.state == "draft":
                recipe.delete()
            else:
                recipe.archived_at = timezone.now()
                recipe.save(update_fields=["archived_at"])
        return Response(status=204)


class ExportView(APIView):
    def get(self, request):
        response = Response(
            {
                "schema_version": 1,
                "recipes": RecipeSerializer(owned(request), many=True).data,
            }
        )
        response["Content-Disposition"] = (
            'attachment; filename="flavorbuddy-recipes.json"'
        )
        return response


def draft_data(draft):
    return {
        "id": draft.pk,
        "state": draft.state,
        "content": draft.content,
        "error_code": draft.error_code,
        "recipe_id": draft.recipe_id,
    }


class ImportsView(APIView):
    def get(self, request, pk):
        draft = get_object_or_404(
            ImportDraft,
            pk=pk,
            owner=request.user,
            created_at__gte=timezone.now() - timedelta(days=7),
        )
        return Response(draft_data(draft))

    def post(self, request):
        from scrape_me.services.extraction import extract_url, validate_preview
        from scrape_me.services.ai_extraction import extract_text

        body = object_body(request)
        try:
            key = UUID(str(body.get("key", "")))
        except ValueError:
            raise ValidationError({"key": "Provide a UUID idempotency key."})
        mode = body.get("mode")
        if mode not in ("url", "text", "manual"):
            raise ValidationError({"mode": "Choose url, text, or manual."})
        value = body.get("input", "")
        if (
            not isinstance(value, str)
            or len(value) > (2000 if mode == "url" else 50000)
            or (mode != "manual" and not value.strip())
        ):
            raise ValidationError(
                {"input": "Provide a recipe URL or up to 50,000 characters of text."}
            )
        canonical_input = {"mode": mode, "input": value}
        digest = hashlib.sha256(
            json.dumps(canonical_input, sort_keys=True).encode()
        ).hexdigest()
        draft = ImportDraft.objects.filter(owner=request.user, key=key).first()
        created = False
        if draft is None:
            reserve([(f"import:{request.user.pk}:{timezone.now().date()}", 100)])
            draft, created = ImportDraft.objects.get_or_create(
                owner=request.user,
                key=key,
                defaults={"input_hash": digest, "input": canonical_input},
            )
        if not created:
            if draft.input_hash != digest:
                raise Conflict(
                    "This request key was used for different input. Start a new import."
                )
            return Response(
                draft_data(draft), status=409 if draft.state == "processing" else 200
            )
        try:
            content = (
                extract_url(value)
                if mode == "url"
                else (
                    extract_text(draft, value)
                    if mode == "text"
                    else validate_preview({})
                )
            )
            draft.content = content
            draft.state = "ready"
        except APIException as exc:
            draft.state = "failed"
            draft.error_code = exc.default_code
        draft.save(update_fields=["content", "state", "error_code", "updated_at"])
        logger.info(
            "import_finished draft_id=%s state=%s code=%s",
            draft.pk,
            draft.state,
            draft.error_code or "none",
        )
        return Response(draft_data(draft), status=201)


class CookView(APIView):
    def post(self, request, pk):
        from scrape_me.models import CookingCompletion

        body = object_body(request)
        key = serializers.UUIDField().run_validation(body.get("key"))
        notes = serializers.CharField(
            max_length=10000, allow_blank=True
        ).run_validation(body.get("notes", ""))
        with transaction.atomic():
            recipe = get_object_or_404(owned(request).select_for_update(), pk=pk)
            if recipe.state != "finalized":
                raise Conflict("Save this draft as a finalized recipe before cooking.")
            if CookingCompletion.objects.filter(recipe=recipe, key=key).exists():
                return Response(RecipeSerializer(recipe).data)
            if body.get("version") != recipe.version:
                raise Conflict()
            try:
                with transaction.atomic():
                    CookingCompletion.objects.create(
                        recipe=recipe,
                        key=key,
                        recipe_version=recipe.version,
                        recipe_snapshot={
                            "title": recipe.title,
                            "ingredients": recipe.ingredients,
                            "instructions": recipe.instructions,
                        },
                    )
            except IntegrityError:
                raise Conflict("Start a new cooking session.")
            recipe.notes = notes
            recipe.version += 1
            recipe.save(update_fields=["notes", "version", "updated_at"])
        return Response(RecipeSerializer(recipe).data)
