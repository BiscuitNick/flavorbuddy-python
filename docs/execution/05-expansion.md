# Expansion implementation and exact resume instructions

Updated September 6, 2026 (America/Chicago). Original uncommitted changes were
inspected and preserved. No reset, commit, push, public deployment, paid AI call,
additional cloud infrastructure or outreach was performed.

## A3: local preparation complete; external release gate remains open

See [protected staging proposal](../operations/staging-release.md) and
`deploy/staging/`. Terraform validation passes, including protected Cloud Run,
managed PostgreSQL backup/PITR settings, separate private storage, version-pinned
secret references and a controlled migration job. API enablement is not performed.
The public bucket was verified; SQL/Run list operations were blocked by disabled
APIs and must be repeated before provisioning. ADC is not yet available; Google
sign-in is still required. GitHub reports no workflow runs. CI now includes all
three app suites and manual workflow dispatch; it remains local/unpushed.

The clean Python 3.13 environment installed all 64 pinned dependencies. The current
suite has 70 PostgreSQL tests; 14 desktop/360px mobile Playwright scenarios pass.
Production check, TypeScript/Vite build, OpenAPI validation and Terraform validation
are part of this increment's checks. The local synthetic restore passed (0.267 s
restore; 2.677 s total); it is not managed staging evidence. Browser tests run their
own disposable PostgreSQL database, private-media directory and separate fixture
worker process. They do not modify the developer's accounts or media.

## E1: controlled owned-app catalog API implemented locally

Django OAuth Toolkit 3.4.1 provides confidential client credentials, five-minute
opaque tokens, hashed secrets/tokens at rest, resource/audience validation and
revocation. Only `/api/integrations/v1/` accepts these tokens. Session/CSRF APIs
retain their existing authentication and do not accept app tokens. No anonymous
OAuth registration, authorization-code flow, user impersonation, writes or paid
AI is enabled for apps.

`AppGrant` binds a registered app to this environment, expiry, enabled state,
explicit catalogs, and daily/minute quotas. `Catalog.recipes` is an explicit
membership list; newly seeded starters do not automatically enter app catalogs.
Grants and kill switches are checked on every request. Database reservations
coordinate per-app and global limits across workers and token rotation; changing
query parameters, source headers or issuing another token cannot reset quotas.
Every integration response gets a request ID and a metadata-only audit record.
Successful issuance and reads identify the registered application. Failed/unknown
requests and revocations may have no associated application; no request body,
raw URL, credential or token is stored in audit records.

The [OpenAPI 1.0 contract](../api/catalog-v1.openapi.json) is served at
`/api/integrations/v1/openapi.json`. Reads have bounded cursor pagination and keep
license/source provenance. Existing public starter APIs and GCS images remain
public; app credentials do not make this content exclusive or recall downloads.

A real local HTTP smoke using `scripts/catalog_client.py` registered a local-only
client, obtained a token, read all 415 explicitly granted recipes and revoked the
token. The secret was written to a mode-0600 file outside the repository and never
printed. Local identity: `flavorbuddy-local-test`; catalog: `starter-local`.
The smoke client file is `/tmp/flavorbuddy-local-client.json` (temporary, not a
production credential). Its audience is `http://127.0.0.1:8012/api/integrations/v1/`.
A server must use that exact PROJECT_URL to repeat the test. Rotate the secret for
any further environment; this file may disappear on restart.

Operator commands, from the repository root:

```sh
.venv/bin/python manage.py prepare_local_catalog
.venv/bin/python manage.py catalog_app register another-local-test --catalog starter-local --credentials-file /tmp/new-flavorbuddy-client.json
.venv/bin/python manage.py catalog_app rotate flavorbuddy-local-test --credentials-file /tmp/rotated-flavorbuddy-client.json
.venv/bin/python manage.py catalog_app disable flavorbuddy-local-test
```

Registration defaults to 90 days and requires explicit existing catalogs. Rotation
revokes all tokens but does not reenable a disabled client. The real other app's
identity, environment, operator, server URL and desired collection remain unknown;
no second app was built or contacted.

## E2: private covers and cooking-result photos implemented locally

The session API accepts bounded still JPEG/PNG/WebP files, checks ownership before
decoding, rejects animation and over-20-megapixel images, applies orientation,
re-encodes to WebP at up to 1600px and strips metadata/filenames. Original bytes are
not retained. File upload handling stops oversized files; default upload cap is
8 MiB. Default shared private photo/capture storage is 25 MiB and 25 objects per
account. Reservations include pending deletion and capture images, preventing
concurrent writes or cleanup failures from bypassing storage allowance.

Images live outside public MEDIA_URL in `private-media/` for development. Production
requires a distinct private GCS bucket or leaves uploads disabled. Serving always
checks the session owner and uses `private, no-store`; no public URLs or signed URL
sharing is offered. The proposed bucket enforces public-access prevention.

The latest cover is used on private recipe cards/details. Result photos select a
completed cooking event and retain its recipe version/content snapshot. Cover
changes do not rewrite cooking history. Completions made before migration 0009
have no trustworthy snapshot, so result uploads require a newly recorded completion.
There is no public-sharing toggle or automatic publication.

Photo deletion, recipe deletion and account deletion create durable cleanup records.
`cleanup_private_photos` retries storage deletion; failed cleanup continues consuming
allowance. Upload reservations survive process failure, with one-hour deferred
cleanup for uncommitted photo uploads. Captures retain their image until explicitly
discarded; incomplete capture upload cancellation waits ten minutes before cleanup.
Schedule cleanup at least hourly on the eventual host. Download/export/deletion
are independent of new-upload and capture eligibility.

## E3: manual pantry, preferences and matching implemented locally

UI and owned APIs support Pantry/Fridge/Freezer/custom text locations, optional
free-text quantities, running-low/use-soon flags, edit conflicts, used-up actions
and undo. Permanent deletion is confirmed. Maximum 500 pantry rows per account.
Cooking completion never deducts inventory. Private kitchen JSON export includes
pantry, preferences and photo/capture references without storage keys or counters;
photo bytes can be downloaded through their authenticated content route.

Matching uses conservative name normalization with a small unit/plural mapping.
It retains each recipe ingredient's source string. Exact normalized names are
explained with pantry location and a quantity-check reminder. Partial names are
explicitly uncertain and remain in the missing list (rice does not establish that
rice vinegar is available). Use-soon matches rank first. Coverage is bounded to
500 newest private recipes and 1,000 starters, with 24 suggestions returned.

Explicit exclusions and vegetarian/vegan keyword filters remove known conflicts.
They are **not comprehensive ingredient classification or an allergy guarantee**.
UI explains incomplete ingredient/label uncertainty. No hidden learned preferences,
quantity sufficiency, expiry/freshness inference or dietary certification is claimed.

## E4 foundations and E5 fixture review path implemented locally

`CapabilityGrant` enables capture per user with a per-user daily allowance;
server-wide daily caps apply before queuing. App identities cannot submit captures.
This is a free/manual capability foundation plus fixture usage accounting, not
paid subscription lifecycle or dollar-cost metering. Photo/capture storage caps and
E1 per-app/global read quotas are independently enforced on the server.

`CaptureJob` is durable PostgreSQL work with uploading/queued/running/preview/
approved/failed/cancelled states, lease recovery, three bounded attempts, retry
delays and a claim token that prevents stale workers from publishing results.
`JobUsage` is unique per job. Same-key submissions reuse the job; different bytes
conflict. Failed or cancelled attempts retain the daily reservation conservatively.
Retries cannot charge another usage unit. Read/export/delete and approval of an
existing preview remain available after capture is disabled. A separate management
worker performs dispatch; no in-process application thread does background work.

**Only fixture detection is implemented.** `CAPTURE_PROVIDER=fixture` plus an explicit
user grant enables the development demo. Production rejects fixture dispatch and
there is no live provider implementation. It returns clearly labeled fixed example
items, empty quantities, and no freshness/hidden-content guesses. The photo review
UI lets users edit/remove/add/deduplicate items before atomic approval adds any rows.
Retrying approval does not duplicate inventory. Discard removes the capture image
and preview while retaining already approved pantry items. No AI evaluation spend
has occurred; this demonstrates the workflow, not image-recognition quality.

## Resume locally

```sh
cd /Users/nickkenkel/code/flavorbuddy/flavorbuddy-python
uv pip sync requirements.lock
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py test scrape_me integrations kitchen --noinput
npm ci --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
.venv/bin/python manage.py runserver
```

For a fixture demonstration, set `CAPTURE_PROVIDER=fixture` for both the server
and a second terminal running `.venv/bin/python manage.py run_capture_jobs`.
Use Django admin's CapabilityGrant to enable the chosen local account (no account
is enabled by default). `--once` processes at most one eligible job. Keep the same
DB and private storage configuration in both processes. Run
`.venv/bin/python manage.py cleanup_private_photos` to reclaim deleted objects.
Restart an existing development server to pick up new settings and app models.

## Next unfinished change sets and external inputs

1. **A3 actual managed release evidence remains first:** finish ADC sign-in, approve
   the concrete additional staging footprint/cost, select SMTP/sender and protected
   HTTPS operator access, authorize the reviewed CI push, then run actual managed
   restore, rollback, two-user smoke and authorized usability observations.
2. Connect E1 to the other app only after its details and catalog grant are supplied.
3. Evaluate E2 private GCS lifecycle/restore and quotas on real staging; expand
   ingredient matching with reviewed dictionaries/fixtures before making stronger
   dietary or quantity claims.
4. Before any live E5 evaluation, implement the selected provider adapter, validated
   output/uncertainty contract and actual provider cost settlement, then obtain a
   separately bounded spend approval. Current fixture accounting is not proof of
   live provider exactly-once billing or visual detection quality.
5. Paid plan lifecycle/checkout, recipe/image generation, sharing, voting and
   household access remain deferred. No prices or subscription promises were added.
