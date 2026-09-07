"""Database-backed limits shared by every worker; reservations are never refunded."""

import hashlib
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import Throttled
from scrape_me.models import UsageCounter


def reserve(limits):
    with transaction.atomic():
        counters = []
        for key, maximum in sorted(limits):
            UsageCounter.objects.get_or_create(key=key)
            counter = UsageCounter.objects.select_for_update().get(key=key)
            if counter.count >= maximum:
                raise Throttled(
                    detail="This limit has been reached. Try again later; manual recipes and your library remain available."
                )
            counters.append(counter)
        for counter in counters:
            counter.count += 1
            counter.save(update_fields=["count"])


def auth_limit(request, identity=""):
    # REMOTE_ADDR is supplied by the trusted application ingress, never a client XFF.
    bucket = int(timezone.now().timestamp()) // 900
    ip = hashlib.sha256(request.META.get("REMOTE_ADDR", "").encode()).hexdigest()
    identity = hashlib.sha256(identity.lower().encode()).hexdigest()
    reserve(
        [(f"auth:ip:{bucket}:{ip}", 60), (f"auth:identity:{bucket}:{identity}", 15)]
    )
