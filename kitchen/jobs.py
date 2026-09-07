"""Durable fixture-only visual capture. No paid provider can be selected here."""

import hashlib
import uuid
from datetime import timedelta
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from django.core.files.storage import storages
from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import PermissionDenied, Throttled
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView
from scrape_me.api.views import Conflict
from scrape_me.services.budgets import reserve
from .models import (
    CaptureJob,
    JobUsage,
    CapabilityGrant,
    PhotoCleanup,
    PrivatePhoto,
    PantryItem,
)
from .photos import clean_image
from .pantry import PantrySerializer


def describe(job):
    return {
        "id": job.pk,
        "state": job.state,
        "attempts": job.attempts,
        "preview": job.preview,
        "approved_ids": job.approved_ids,
        "error_code": job.error_code,
        "provider": "fixture",
        "notice": "Demo detections only: this fixture does not analyze your photo. Edit and approve each item. No freshness or hidden contents are inferred.",
    }


class CaptureView(APIView):
    parser_classes = [MultiPartParser]

    def get(self, request):
        return Response(
            {
                "jobs": [
                    describe(job)
                    for job in CaptureJob.objects.filter(owner=request.user).order_by(
                        "-id"
                    )[:30]
                ]
            }
        )

    def post(self, request):
        if settings.CAPTURE_PROVIDER != "fixture" or settings.PRODUCTION:
            raise PermissionDenied(
                "Visual capture is not enabled. Manual pantry remains available."
            )
        key = serializers.UUIDField().run_validation(request.data.get("key"))
        content = clean_image(request.FILES.get("photo"))
        digest = hashlib.sha256(content).hexdigest()
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            existing = CaptureJob.objects.filter(owner=request.user, key=key).first()
            if existing:
                if existing.input_hash != digest:
                    raise Conflict("Use a new key for a different photo.")
                return Response(describe(existing))
            grant = CapabilityGrant.objects.filter(
                owner=request.user, capture_enabled=True
            ).first()
            if not grant:
                raise PermissionDenied(
                    "Capture is not enabled for this account. Manual pantry remains available."
                )
            day = timezone.now().date().isoformat()
            # Reserved exactly once per job; failures retain their reservation.
            reserve(
                [
                    (
                        f"capture:user:{request.user.pk}:{day}",
                        grant.capture_daily_limit,
                    ),
                    (f"capture:global:{day}", settings.CAPTURE_GLOBAL_DAILY_LIMIT),
                ]
            )
            photos = PrivatePhoto.objects.filter(owner=request.user)
            jobs = CaptureJob.objects.filter(owner=request.user).exclude(image_key="")
            pending = PhotoCleanup.objects.filter(owner=request.user)
            used = sum(
                q.aggregate(n=Sum(field))["n"] or 0
                for q, field in [
                    (photos, "size"),
                    (jobs, "image_size"),
                    (pending, "size"),
                ]
            )
            if (
                used + len(content) > settings.PRIVATE_PHOTO_STORAGE_BYTES
                or photos.count() + jobs.count() + pending.count()
                >= settings.PRIVATE_PHOTO_COUNT
            ):
                raise Throttled(
                    detail="Photo storage is full. Delete photos or discard old captures."
                )
            image_key = f"{request.user.pk}/capture-{uuid.uuid4().hex}.webp"
            # Persist a staging state and object reservation before the external write.
            job = CaptureJob.objects.create(
                owner=request.user,
                key=key,
                input_hash=digest,
                image_key=image_key,
                image_size=len(content),
                state="uploading",
                lease_expires=timezone.now() + timedelta(minutes=5),
            )
            JobUsage.objects.create(job=job)
        try:
            actual = storages["private_photos"].save(image_key, ContentFile(content))
            if actual != image_key:
                PhotoCleanup.objects.create(
                    key=actual, owner=request.user, size=len(content)
                )
                raise ValueError("Unexpected object key")
            with transaction.atomic():
                job = CaptureJob.objects.select_for_update().get(pk=job.pk)
                if job.state != "uploading":
                    raise ValueError("Upload expired")
                job.state = "queued"
                job.lease_expires = None
                job.save()
        except Exception:
            CaptureJob.objects.filter(pk=job.pk, state="uploading").update(
                state="failed", error_code="upload_failed"
            )
            return Response(describe(CaptureJob.objects.get(pk=job.pk)), status=201)
        return Response(describe(job), status=201)


class JobView(APIView):
    def get(self, request, pk):
        return Response(
            describe(get_object_or_404(CaptureJob, pk=pk, owner=request.user))
        )

    def delete(self, request, pk):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            job = get_object_or_404(
                CaptureJob.objects.select_for_update(), pk=pk, owner=request.user
            )
            if job.image_key:
                PhotoCleanup.objects.get_or_create(
                    key=job.image_key,
                    defaults={
                        "owner": request.user,
                        "size": job.image_size,
                        "not_before": timezone.now() + timedelta(minutes=10)
                        if job.state == "uploading"
                        else timezone.now(),
                    },
                )
            job.image_key = ""
            job.image_size = 0
            job.preview = []
            job.state = "cancelled"
            job.lease = None
            job.save()
            JobUsage.objects.filter(job=job).update(state="cancelled")
        return Response(status=204)

    def post(self, request, pk):
        with transaction.atomic():
            get_user_model().objects.select_for_update().get(pk=request.user.pk)
            job = get_object_or_404(
                CaptureJob.objects.select_for_update(), pk=pk, owner=request.user
            )
            if job.state == "approved":
                return Response(describe(job))
            if job.state != "preview":
                raise Conflict("Wait for the editable preview before approving.")
            raw = request.data.get("items") if isinstance(request.data, dict) else None
            if not isinstance(raw, list) or not 1 <= len(raw) <= 50:
                raise serializers.ValidationError("Approve 1–50 edited items.")
            serializer = PantrySerializer(data=raw, many=True)
            serializer.is_valid(raise_exception=True)
            if PantryItem.objects.filter(owner=request.user).count() + len(raw) > 500:
                raise serializers.ValidationError(
                    "Pantry limit reached; delete used-up items first."
                )
            names = [
                (
                    x["name"].strip().casefold(),
                    x.get("location", "Pantry").strip().casefold(),
                )
                for x in serializer.validated_data
            ]
            if len(set(names)) != len(names):
                raise serializers.ValidationError(
                    "Remove duplicate names in the same location before approving."
                )
            items = serializer.save(owner=request.user)
            job.approved_ids = [i.pk for i in items]
            job.state = "approved"
            job.save()
            JobUsage.objects.filter(job=job).update(state="settled")
        return Response(describe(job))


def work_one():
    """Claim with a lease; stale workers cannot overwrite a newer result or cancellation."""
    if settings.CAPTURE_PROVIDER != "fixture" or settings.PRODUCTION:
        return False
    now = timezone.now()
    with transaction.atomic():
        expired = CaptureJob.objects.select_for_update(skip_locked=True).filter(
            state__in=["running", "uploading"], lease_expires__lt=now
        )
        for job in expired:
            job.state = (
                "failed" if job.state == "uploading" or job.attempts >= 3 else "queued"
            )
            job.error_code = "worker_interrupted"
            job.lease = None
            job.lease_expires = None
            job.save()
        job = (
            CaptureJob.objects.select_for_update(skip_locked=True)
            .filter(state="queued", available_at__lte=now)
            .order_by("id")
            .first()
        )
        if not job:
            return False
        # A downgrade/revocation blocks dispatch, but read/approve/delete stay available.
        if not CapabilityGrant.objects.filter(
            owner_id=job.owner_id, capture_enabled=True
        ).exists():
            job.state = "failed"
            job.error_code = "capability_disabled"
            job.save()
            return True
        job.state = "running"
        job.attempts += 1
        job.lease = uuid.uuid4()
        job.lease_expires = now + timedelta(minutes=2)
        job.save()
        lease = job.lease
    try:
        preview = detect_fixture(job)
        # Fixture schema is still treated as untrusted provider output.
        validator = PantrySerializer(data=preview, many=True)
        validator.is_valid(raise_exception=True)
        if len(preview) > 50:
            raise ValueError("Too many items")
        with transaction.atomic():
            changed = CaptureJob.objects.filter(
                pk=job.pk, state="running", lease=lease
            ).update(
                state="preview",
                preview=validator.data,
                lease=None,
                lease_expires=None,
                error_code="",
            )
            if changed:
                JobUsage.objects.filter(job=job).update(state="completed")
    except Exception:
        with transaction.atomic():
            CaptureJob.objects.filter(pk=job.pk, state="running", lease=lease).update(
                state="failed" if job.attempts >= 3 else "queued",
                available_at=timezone.now() + timedelta(seconds=30 * job.attempts),
                lease=None,
                lease_expires=None,
                error_code="detection_failed",
            )
    return True


def detect_fixture(job):
    with storages["private_photos"].open(job.image_key, "rb") as content:
        from PIL import Image

        Image.open(content).verify()
    return [
        {"name": "Tomato", "quantity": "", "location": "Fridge"},
        {"name": "Rice", "quantity": "", "location": "Pantry"},
    ]
