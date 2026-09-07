import io
import uuid
import warnings
from datetime import timedelta
from django.utils import timezone
from PIL import Image, ImageOps, UnidentifiedImageError
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Sum
from django.http import FileResponse
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import ValidationError, Throttled, APIException
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from scrape_me.models import Recipe, CookingCompletion
from .models import PrivatePhoto, PhotoCleanup, CaptureJob


def representation(photo):
    return {
        "id": photo.pk,
        "kind": photo.kind,
        "recipe_version": photo.recipe_version,
        "completion_id": photo.completion_id,
        "size": photo.size,
        "url": f"/api/v1/photos/{photo.pk}/content",
        "created_at": photo.created_at,
    }


def clean_image(upload):
    if not upload or upload.size > settings.PRIVATE_PHOTO_UPLOAD_BYTES:
        raise ValidationError("Choose a JPEG, PNG or WebP image no larger than 8 MiB.")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(upload) as source:
                if (
                    source.format not in {"JPEG", "PNG", "WEBP"}
                    or getattr(source, "n_frames", 1) != 1
                ):
                    raise ValueError
                if source.width * source.height > 20_000_000:
                    raise ValueError
                source.load()
                result = ImageOps.exif_transpose(source).convert("RGB")
                result.thumbnail((1600, 1600))
                output = io.BytesIO()
                result.save(
                    output, format="WEBP", quality=82
                )  # no EXIF, ICC or original filename
                return output.getvalue()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombError,
        Image.DecompressionBombWarning,
    ):
        raise ValidationError(
            "Use a single still JPEG, PNG or WebP up to 20 megapixels."
        )


class PhotosView(APIView):
    parser_classes = [MultiPartParser]

    def get(self, request, recipe_id):
        recipe = get_object_or_404(Recipe, pk=recipe_id, owner=request.user)
        return Response(
            {
                "photos": [
                    representation(p)
                    for p in recipe.private_photos.order_by("-created_at")
                ],
                "completions": list(
                    recipe.cooking_completions.filter(recipe_version__isnull=False)
                    .order_by("-created_at")
                    .values("id", "created_at", "recipe_version")
                ),
            }
        )

    def post(self, request, recipe_id):
        if settings.PRIVATE_PHOTO_BACKEND == "disabled":
            raise ValidationError(
                "Private photo storage is not configured for this instance."
            )
        # Authorize before parsing/decoding any file.
        get_object_or_404(Recipe, pk=recipe_id, owner=request.user)
        kind = request.data.get("kind", "cover")
        if kind not in {"cover", "result"}:
            raise ValidationError("Choose cover or result.")
        content = clean_image(request.FILES.get("photo"))
        storage = storages["private_photos"]
        # Reserve storage durably before writing any object. Crashes leave a cleanup
        # record; completion removes it only after the photo row is committed.
        key = f"{request.user.pk}/{uuid.uuid4().hex}.webp"
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            photos = PrivatePhoto.objects.filter(owner=request.user)
            pending = PhotoCleanup.objects.filter(owner=request.user)
            jobs = CaptureJob.objects.filter(owner=request.user).exclude(image_key="")
            used = (
                (photos.aggregate(n=Sum("size"))["n"] or 0)
                + (pending.aggregate(n=Sum("size"))["n"] or 0)
                + (jobs.aggregate(n=Sum("image_size"))["n"] or 0)
            )
            if (
                used + len(content) > settings.PRIVATE_PHOTO_STORAGE_BYTES
                or photos.count() + pending.count() + jobs.count()
                >= settings.PRIVATE_PHOTO_COUNT
            ):
                raise Throttled(
                    detail="Your photo storage is full. Delete photos to make room; existing photos remain readable."
                )
            reservation = PhotoCleanup.objects.create(
                key=key,
                owner=request.user,
                size=len(content),
                not_before=timezone.now() + timedelta(hours=1),
            )
        try:
            saved_key = storage.save(key, ContentFile(content))
            if saved_key != key:
                PhotoCleanup.objects.create(
                    key=saved_key, owner=request.user, size=len(content)
                )
                raise ValidationError(
                    "Upload could not be completed. Please try again."
                )
            with transaction.atomic():
                get_user_model().objects.select_for_update().get(pk=request.user.pk)
                reservation = PhotoCleanup.objects.select_for_update().get(
                    pk=reservation.pk
                )
                recipe = get_object_or_404(
                    Recipe.objects.select_for_update(), pk=recipe_id, owner=request.user
                )
                completion = None
                if kind == "result":
                    try:
                        completion_id = int(request.data.get("completion_id", ""))
                    except (ValueError, TypeError):
                        raise ValidationError(
                            "Choose a cooking completion for the result photo."
                        )
                    completion = get_object_or_404(
                        CookingCompletion,
                        pk=completion_id,
                        recipe=recipe,
                        recipe_version__isnull=False,
                    )
                photo = PrivatePhoto.objects.create(
                    owner=request.user,
                    recipe=recipe,
                    completion=completion,
                    recipe_version=completion.recipe_version
                    if completion
                    else recipe.version,
                    recipe_snapshot=completion.recipe_snapshot
                    if completion
                    else {
                        "title": recipe.title,
                        "ingredients": recipe.ingredients,
                        "instructions": recipe.instructions,
                    },
                    kind=kind,
                    key=key,
                    size=len(content),
                )
                reservation.delete()
            return Response(representation(photo), status=201)
        except Exception as error:
            PhotoCleanup.objects.filter(key=key).update(not_before=timezone.now())
            if isinstance(error, APIException):
                raise
            raise APIException(
                "Photo storage is temporarily unavailable. Please try again."
            ) from None


class PhotoView(APIView):
    def get(self, request, pk):
        photo = get_object_or_404(PrivatePhoto, pk=pk, owner=request.user)
        try:
            content = storages["private_photos"].open(photo.key, "rb")
        except FileNotFoundError:
            from rest_framework.exceptions import NotFound

            raise NotFound("This photo is unavailable.")
        response = FileResponse(content, content_type="image/webp")
        response["X-Content-Type-Options"] = "nosniff"
        response["Content-Disposition"] = 'inline; filename="photo.webp"'
        return response

    def delete(self, request, pk):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            get_object_or_404(PrivatePhoto, pk=pk, owner=request.user).delete()
        return Response(status=204)
