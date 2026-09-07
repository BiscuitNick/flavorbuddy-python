"""Explicitly enabled, metered, synchronous extraction. No automatic paid retries."""

import json
import os
import time
import httpx
from django.conf import settings
from django.utils import timezone
from scrape_me.models import AIInvocation
from scrape_me.services.budgets import reserve
from scrape_me.services.extraction import validate_preview
from scrape_me.api.errors import ImportFailure
from scrape_me.views import get_recipe_system_prompt


class AIDisabled(ImportFailure):
    default_code = "ai_unavailable"
    default_detail = (
        "Text extraction is unavailable. Enter the recipe manually instead."
    )


def invoke(text):
    # No SDK polling/retry loop. A prediction still running after the bounded wait
    # is not represented as a durable local background job.
    headers = {
        "Authorization": f"Bearer {os.environ['REPLICATE_API_TOKEN']}",
        "Prefer": "wait=10",
    }
    deadline = time.monotonic() + 20
    with httpx.Client(
        timeout=httpx.Timeout(15, connect=3), transport=httpx.HTTPTransport(retries=0)
    ) as client:
        with client.stream(
            "POST",
            "https://api.replicate.com/v1/models/openai/gpt-5-nano/predictions",
            headers=headers,
            json={
                "input": {
                    "prompt": json.dumps({"source_url": None, "raw_text": text}),
                    "system_prompt": get_recipe_system_prompt(),
                    "reasoning_effort": "minimal",
                    "verbosity": "low",
                }
            },
        ) as response:
            response.raise_for_status()
            body = bytearray()
            for chunk in response.iter_bytes():
                body.extend(chunk)
                if len(body) > 262144 or time.monotonic() > deadline:
                    raise ImportFailure()
            return json.loads(body)


def extract_text(draft, text):
    if (
        not settings.AI_ENABLED
        or not os.environ.get("REPLICATE_API_TOKEN")
        or min(settings.AI_USER_DAILY_LIMIT, settings.AI_GLOBAL_DAILY_LIMIT) <= 0
    ):
        raise AIDisabled()
    day = timezone.now().date()
    reserve(
        [
            (f"ai:global:{day}", settings.AI_GLOBAL_DAILY_LIMIT),
            (f"ai:user:{draft.owner_id}:{day}", settings.AI_USER_DAILY_LIMIT),
        ]
    )
    invocation = AIInvocation.objects.create(draft=draft)
    try:
        result = invoke(text)
        invocation.provider_id = str(result.get("id", ""))[:255]
        if result.get("status") != "succeeded":
            raise ImportFailure(
                "Extraction did not finish in time. Your input is preserved; continue manually."
            )
        output = result.get("output")
        if isinstance(output, list):
            output = "".join(output)
        if isinstance(output, str):
            output = json.loads(output)
        preview = validate_preview(output)
        invocation.state = "succeeded"
        return preview
    except Exception:
        invocation.state = "failed_or_uncertain"
        raise ImportFailure(
            "Text extraction could not finish. Your input is preserved; enter the recipe manually."
        ) from None
    finally:
        invocation.save(update_fields=["state", "provider_id"])
