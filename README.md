# FlavorBuddy private alpha

A Django/PostgreSQL backend and React/TypeScript frontend for **import → review →
save privately → find → edit → cook**. Website imports use controlled HTTP fetching
and recipe-scrapers; optional pasted-text extraction uses metered Replicate calls.
AI is disabled by default. Unsupported sources always have a manual path.

## Run locally

Requirements: Python 3.13, Node 22+, Docker Desktop, and uv (or pip).

```bash
# From this repository; do not overwrite an existing .env.
test -f .env || cp .env.example .env
docker compose up -d db
uv venv --python python3.13 .venv
uv pip sync requirements.lock
.venv/bin/python manage.py migrate
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/python manage.py collectstatic --noinput
.venv/bin/python manage.py runserver
```

Open [FlavorBuddy](http://127.0.0.1:8000). Register an account locally. No API key is
needed for URL imports, manual recipes, or the sample. Admin is at `/admin/` after
`.venv/bin/python manage.py createsuperuser`. PostgreSQL data persists in Compose's
named `postgres_data` volume; do not remove it to restart the app.

For frontend development, run `npm run dev --prefix frontend` alongside Django.
Vite proxies `/api` to Django at port 8000. Production uses the same origin and
hash-based frontend routes, so detail/edit/cook refresh and browser back work
without a separate SPA fallback service. Font files are bundled (OFL-licensed DM
Sans and Libre Caslon Display); source images load directly with no referrer.

## Verify

```bash
.venv/bin/python manage.py test scrape_me integrations kitchen --noinput
.venv/bin/python manage.py makemigrations --check --dry-run
npm run build --prefix frontend
.venv/bin/python manage.py collectstatic --noinput
npx --prefix frontend playwright install chromium
npm run test:e2e --prefix frontend
.venv/bin/python scripts/restore_drill.py
```

Backend tests create `test_flavorbuddy`. Browser tests create a separate
`test_flavorbuddy_browser` database, run real Django sessions and APIs, and replace
only outbound fetching with a deterministic HTML fixture. No paid AI or external
source requests run in CI. Stop an old browser test server before rerunning it.
The restore drill creates and removes two disposable synthetic databases; it never
backs up or overwrites your recipe database.

GitHub Actions installs the exact Python lock and npm lock, runs PostgreSQL tests,
checks migrations, builds assets, runs Chromium desktop/mobile flows and accessibility
checks, and checks production settings. Regenerate Python dependencies with
`uv pip compile requirements.txt -o requirements.lock`. Use `uv pip sync` to install
the lock, or `.venv/bin/python -m pip install -r requirements.lock` in a pip venv.

## Account and API contract

Django sessions with CSRF on every mutation, including login. `GET /api/v1/me`
returns a CSRF token and the current user (or null); send `X-CSRFToken` on POST,
PATCH, and DELETE. The token rotates on login. Email is the normalized unique
username in the existing Django User model. Email verification is not enabled for
this local alpha. SMTP recovery is exposed only when configured; Django's expiring,
single-use reset tokens and password validators are used. Account mutations are
rate-limited in PostgreSQL by address and account identity.

| Route | Behavior |
| --- | --- |
| `GET /api/v1/me` | Session identity, CSRF bootstrap, recovery availability |
| `POST /api/v1/auth/register`, `/login`, `/logout` | Account/session lifecycle |
| `POST /api/v1/auth/reset`, `/reset-confirm` | SMTP password recovery |
| `POST /api/v1/imports` | `{key: UUID, mode: url/text/manual, input: string}`; synchronous owned preview |
| `GET /api/v1/imports/{id}` | Owned preview state/content/error |
| `GET/POST /api/v1/recipes` | Private paginated title search / validated save |
| `GET/PATCH/DELETE /api/v1/recipes/{id}` | Owned detail / versioned edit / permanent delete |
| `GET /api/v1/recipes/export` | Owned structured JSON with source attribution |
| `POST /api/v1/recipes/{id}/cook` | Idempotent self-reported completion and personal note |

Recipe fields: title, description, author, total_time (minutes or null), yields,
source_url, image, ingredients and instructions (arrays of strings), notes, favorite.
Drafts may be incomplete and remain private. Finalization requires title, ingredients,
and instructions and permanently locks content. PATCH edits draft content; notes and
favorites remain mutable after finalization. PATCH and visibility changes require the
last-read `version` for conflict detection. Make a variation to change a finalized recipe:
it creates a private draft with a new UUID and `inspired_by` link. Source URLs are not unique.

Additional routes: `POST /api/v1/recipes/{id}/finalize`, `/visibility`, `/variations`;
`GET /api/v1/shared-recipes` and `/shared-recipes/{public_id}`. Sharing changes visibility
without replacing the UUID. Draft deletion is permanent; finalized deletion archives the
identity. Public archived links return 410. Personal notes/favorites/photos stay private.

Save a preview by including its `import_id`; repeated saves reuse its recipe identity.
Ownership is assigned by the server. List parameters include `q`, `favorite=true`,
`page`, and `page_size` (1–100). Exports use `schema_version: 1`.

Old `/parse-recipe-url`, `/get-recipes`, and `/convert-raw-recipe` routes return 410.
`/test-example` is removed. Ownerless legacy records retain their IDs/content and
are available only through staff administration, never consumer APIs.

## Import limits and recovery

- HTTP/HTTPS only, standard ports, public DNS answers only, numeric-IP socket
  pinning with original-host TLS verification; redirects are revalidated.
- At most five redirects, five-second socket timeout, 15-second fetch deadline,
  2 MiB HTML. Compressed responses are rejected (identity encoding requested).
- Pasted text: 50,000 characters. JSON request bodies: 256 KiB.
- 100 new imports per account/day. AI additionally requires `AI_ENABLED=true`, a
  `REPLICATE_API_TOKEN`, and positive `AI_USER_DAILY_LIMIT` and
  `AI_GLOBAL_DAILY_LIMIT`. These are **call limits**, not dollar budgets.
- Paid calls reserve counters atomically before dispatch. Failed/uncertain calls
  still consume their reservation. Provider outputs are validated. No automatic
  AI fallback, automatic paid retry, or unmanaged background thread is used.
- Schedule `python manage.py expire_imports` daily with your deployment scheduler:
  abandoned previews expire after seven days; interrupted requests become failed.
  Saved idempotency records remain, with raw pasted input cleared. This command
  is prepared; no external scheduler has been provisioned.

Drafts and cooking progress are stored on the device under account-specific keys.
They survive ordinary errors and session expiry. This is not offline synchronization;
saved recipes still require a connection. Timers need the page open; wake-lock is
best-effort. Cooking completion is self-reported. Deletion requires confirmation; drafts are deleted and finalized recipes are archived. Export your library before destructive changes.

## Configuration and deployment

Compose defaults: database/user/password `flavorbuddy`, host `localhost`, port 5432.
Override with `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`,
`POSTGRES_PORT`, and optionally `POSTGRES_SSLMODE` (default `prefer`; use appropriate
verified TLS/private connector settings for managed databases).

Production requires `DJANGO_ENV=production`, `DJANGO_DEBUG=false`, a unique
50+ character `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, and HTTPS
`PROJECT_URL`. `TRUST_PROXY_HTTPS=true` is only for an ingress that overwrites
forwarded HTTPS headers and prevents direct application access. Secure cookies,
HTTPS redirection, HSTS, and static serving are enabled in production.

`Dockerfile` builds frontend assets and runs Gunicorn as a non-root user. The image
defaults to production and fails without required configuration. Use a single release
migration command before replacing workers. `/health/live` checks the process;
`/health/ready` checks PostgreSQL with bounded database timeouts. Private uploads require a separate private bucket in production. See the protected GCP staging configuration.

See [deployment operations](docs/operations/deployment.md) and the
[execution evidence and unfinished release gates](docs/execution/README.md).
Protected staging and remote CI are authorized in the September 7 increment. Current
hosted evidence and unresolved inputs are in [release status](docs/execution/07-release-and-v2.md).
Live AI, billing, voting, households and full offline synchronization remain deferred.

## Starter recipe collection

Browse `/#/starters` without an account, then sign in to save independent private
copies. Load the bundled catalog with:

```bash
.venv/bin/python manage.py seed_starter_recipes
```

The accepted collection size is **415 valid recipe entries**, all included from the pinned Public Domain Recipes repository. No duplicate padding or second
source was used. See `data/starter/README.md` for license, revision, provenance and
rebuild instructions. Seeding can be repeated without changing private copies.

Starter images support Google Cloud Storage. Set `STARTER_IMAGE_STORAGE=gcs` and
`GS_STARTER_BUCKET_NAME` with Application Default Credentials, then run
`python manage.py store_starter_images --source-directory /path/to/source/static/pix`.
Development uses ignored `media/` files by default. See
[storage deployment instructions](docs/operations/deployment.md#google-cloud-storage-starter-images).

## Pantry, private photos and owned-app integrations

The alpha now includes manual pantry/preferences/matching and private recipe-cover
and cooking-result photos. The latest private cover appears on recipe cards. User
images are session-protected and stored separately from public starter images.
Private photo storage defaults to local development storage; configure a dedicated
private bucket before enabling it in production.

The separate catalog integration uses registered OAuth clients and explicit starter
grants. See [expansion execution](docs/execution/05-expansion.md) for commands,
limits, the OpenAPI contract, local client and durable fixture capture demo. Real
visual detection, paid plan lifecycle and managed staging are not claimed complete.

## FlavorGirls catalog v2

Read-only `GET /api/integrations/v2/catalogs/{catalog}/recipes` supports phrase search
across title, description and ingredient source text, relevance/newest/quickest sorts,
`limit`/signed `cursor`, and `max_total_minutes`. Unknown/repeated parameters fail with 400.
`GET /api/integrations/v2/recipes/{uuid}` returns `{document, status}`. RecipeDocumentV1
preserves source strings, adds recipe-scoped stable ingredient/step IDs and leaves unknown
quantities, timers, equipment and references null. It does not infer cooking facts.

Obtain tokens at the existing `/api/integrations/v1/oauth/token`, requesting `catalog:read`
and resource `<PROJECT_URL>/api/integrations/v2/`. Tokens are restricted to the requested
version; v1 and v2 share grants, revocation and quotas. Protected staging additionally
requires Google IAM invocation credentials in `X-Serverless-Authorization`; see
[operator access](docs/operations/staging-release.md). Only explicit starter catalog
membership is eligible; public sharing never automatically grants an app access.

Private/archived granted identities return 410 with a null document; unknown/ungranted
identities return 404. Feedback is null because it is not implemented. See the
[OpenAPI contract](docs/api/catalog-v2.openapi.json) and [document schema](docs/api/RecipeDocumentV1.schema.json).
