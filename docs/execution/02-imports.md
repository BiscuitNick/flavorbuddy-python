# Plan 2: Make imports safe, dependable, and useful

**Outcome:** A supported URL or pasted recipe becomes an editable private preview; failure is recoverable and paid work is bounded.  
**Change sets:** B1, B2  
**Dependencies:** A1 for baseline; C1/C2 for owned imports and saved recipes.

## B1: Extract services and define contracts

The current view combines fetching, parsing, normalization, persistence, and responses. Split these responsibilities into small services without rewriting unrelated behavior.

### Proposed files

- `scrape_me/services/fetching.py`: URL policy and controlled HTML retrieval.
- `scrape_me/services/extraction.py`: deterministic parsing and normalized recipe drafts.
- `scrape_me/services/ai_extraction.py`: provider adapter, bounded invocation, output validation.
- `scrape_me/api/serializers.py` and `scrape_me/api/views.py`: request/response validation and endpoints.
- `scrape_me/views.py`: temporary compatibility adapters, with legacy access controlled.
- `scrape_me/prompts/raw-text-system-prompt.md`: extraction instructions reviewed alongside schema.

### Draft contract

Require an object containing title, author, description, total time, yield, image URL, ingredients, and instructions. Define field lengths and item limits; validate HTTP/HTTPS image/source URLs before use. A preview may be incomplete, but saving requires a nonempty title, ingredient list, and instruction list for the first release. Return field-level validation errors and preserve the incomplete preview for correction.

Preserve source text and distinguish missing values from inferred ones. Do not accept arbitrary provider dictionaries directly as stored content. Inputs such as `[]`, `null`, numbers, malformed JSON, invalid UTF-8, and oversized content must produce controlled errors.

Use an error envelope such as:

```json
{
  "error": {
    "code": "unsupported_source",
    "message": "We could not extract this page. Paste the recipe text to continue.",
    "fields": {},
    "request_id": "generated-request-id"
  }
}
```

Do not expose raw provider exceptions, stack traces, credentials, or internal destination details.

### Controlled fetch requirements

1. Accept HTTP/HTTPS URLs only; reject embedded credentials and nonstandard ports initially.
2. Resolve and validate all candidate addresses; block loopback, private, link-local, reserved, unspecified, and other non-public targets in IPv4 and IPv6.
3. Ensure the network connection uses the validated destination. A preflight DNS lookup followed by an unrelated client lookup is insufficient against rebinding. Select a reviewed transport or enforce public-only egress at the network boundary; retain hostname-based TLS verification.
4. Disable automatic redirects and reapply the URL/address policy at every redirect, with a small hop limit.
5. Enforce connect/read and total deadlines, a streamed body-size limit including decompressed content, and accepted content types.
6. Return bounded HTML to `scrape_html`; do not use uncontrolled convenience fetching inside the parser.
7. Avoid retries for validation errors and unsupported sources. Bound retries for transient failures and obey upstream rate-limit signals where applicable.

Initial proposed limits for testing: 5 redirects, 5-second connect timeout, 15-second total fetch deadline, 2 MiB decoded HTML, and 50,000 characters of pasted text. These are configurable starting values; verify against the supported-source fixture set before fixing product limits.

### B1 tests

- Public fixture succeeds; private/localhost/metadata-style destinations never receive a connection.
- Redirects into blocked ranges fail; DNS/connection handling cannot bypass validation.
- Oversized/decompression-heavy responses, timeouts, unexpected content types, and excessive redirects return stable errors.
- Fixture extraction preserves ingredients and ordered instructions.
- Invalid request shapes and malformed AI outputs fail validation without a 500.

Use simulated transport/DNS fixtures; tests must not probe real internal services.

## B2: Owned previews, saving, and AI budgets

1. Add an owned `ImportDraft` record with state, normalized content, source metadata, timestamps, idempotency key, and structured failure code. Expire abandoned drafts on a documented schedule.
2. Introduce `POST /api/v1/imports` and `GET /api/v1/imports/{id}`. Keep the state contract compatible with future queued jobs.
3. For the earliest private alpha, bounded synchronous extraction is acceptable if the request finishes within platform limits. Do not return `202 Accepted` and rely on an unmanaged in-process thread. Introduce the durable worker/queue before claiming asynchronous execution or adding automatic background retries.
4. URL parsing failures offer paste/manual input. Automatically using AI on fetched HTML requires explicit product configuration, authenticated quota, successful safe fetch, and schema validation.
5. Save through the recipe API with an `import_id` owned by the caller. Accept reviewed edits, validate again, and atomically mark the draft as saved so a repeated action cannot create duplicate recipes.
6. Keep canonical source metadata separate from each user's saved content. Two users importing one URL must never receive each other's edits or notes.
7. Meter AI calls with an atomic reservation before dispatch and settlement afterward. Use per-account and global limits; a process-local counter is insufficient with multiple workers.
8. Record provider request identifiers and invocation outcomes. Uncertain failures must not trigger unlimited retries or release reservations in a way that bypasses budgets.
9. Add domain/error metrics and redact raw content from logs. Keep AI disabled when credentials or budget configuration is missing, with a clear recoverable response.

### B2 acceptance scenarios

- Alice imports and edits a preview, saves once, refreshes, and sees one recipe.
- Bob cannot inspect Alice's import ID or save it into his account.
- Concurrent save requests return the existing owned result or an explicit conflict, not duplicate records.
- A source failure preserves input and lets the user continue with pasted text.
- A schema-invalid AI response cannot become a saved recipe.
- Concurrent AI requests cannot exceed reserved quotas; requests beyond the limit return 429 or an explicit quota response without calling the provider.
- Paid calls remain mocked in CI. A bounded live evaluation is recorded separately when provider credentials are configured.

## Completion and rollback

B1 is complete when extraction and fetching boundaries pass tests. B2 is complete when the frontend can consume owned previews and save them safely through real APIs. Preserve existing data; disable the new import entry point if problems occur. Never roll back by reopening anonymous legacy endpoints to all stored content.

## Implementation evidence — September 6, 2026

Owner: Codex; uncommitted implementation for review.

**B1 implemented and locally validated.** `services/fetching.py` connects its socket
to a validated numeric address and verifies TLS against the original hostname.
Bounded DNS A/AAAA resolution rejects any non-public answer, including mapped and
transition IPv6 addresses. Every redirect revalidates the policy. Timeouts, a total
watchdog deadline, five redirects and 2 MiB streaming limits apply. Identity
encoding is requested; compressed responses are deliberately rejected, avoiding
decompression expansion. Controlled HTML goes to the offline scraper.

Tests cover numeric socket/TLS identity, mixed public/private DNS answers,
localhost/private/link-local/metadata targets, redirect escapes/loops, timeouts,
content types, compressed/oversized streams, real JSON-LD fixture extraction,
non-object/malformed/invalid-UTF-8/oversized requests and invalid previews. A manual
live safe-fetch smoke on Allrecipes' Banana Banana Bread succeeded in **0.51 s**
with **7 ingredients, 6 steps, and an image URL**. No paid AI was called.

**B2 implemented and locally validated.** Authenticated synchronous previews have
owned IDs, UUID idempotency keys, input hashes, input preservation and structured
failure states. Saves lock drafts and return one recipe under concurrent retries.
Per-user source uniqueness never shares edits between users. Failed previews may
be manually corrected. HTTP success for an import means the draft was created:
clients must inspect `state` and `error_code`, as the frontend does.

Database reservations cap per-account/global daily AI calls; failures and unknown
provider outcomes retain reservations. No automatic AI fallback/retry or local
background execution is enabled. Provider IDs/outcomes are stored separately from
exports. Credentials alone cannot enable paid work; both positive caps and
`AI_ENABLED=true` are required. Caps count calls, not currency. A provider prediction
that outlives the bounded synchronous wait is recorded as uncertain; it is not
advertised as a recoverable background job.

`expire_imports` marks interrupted processing after two minutes, expires abandoned
drafts after seven days and removes pasted input from saved idempotency records.
Schedule it in deployment; no external scheduler is active. Errors and import-state
logs omit raw recipes, credentials and source query strings. Tests include invalid
AI output, retained reservations, quota contention, abandoned-draft cleanup, and
concurrent idempotent saves. Browser tests exercise source failure/manual recovery
and an uncertain network save without losing the draft.

Limitations: no worker queue, upload support, source refresh/cache, AI dollar-cost
accounting or paid live quality evaluation. Unsupported/blocked/encoded sources
use manual recovery. Review limits against more source fixtures before a pilot.
