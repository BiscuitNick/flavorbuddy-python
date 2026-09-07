# Plan 1: Establish a verified foundation

**Outcome:** The backend installs reproducibly, runs against PostgreSQL, and has a clear production configuration and deployment path.  
**Change sets:** A1, A2, A3  
**Dependencies:** None for local baseline; complete the product flow before A3 pilot deployment.

## Starting facts

The repository has a PostgreSQL Compose service and environment-driven database values. The previous review passed 17 existing tests and exercised imports with temporary SQLite, but did not verify PostgreSQL. Docker was not running. Requirements are broad version ranges. Production debug, secret, hosts, static serving, and process configuration need work.

Existing uncommitted changes in settings, views, README, requirements, environment configuration, and prompts belong to the working baseline. Do not reset or overwrite them.

## A1: Verify PostgreSQL and reproducibility

1. Inspect the working tree and record Python, Django, scraper, and driver versions.
2. Start the local Docker database; preserve existing volumes and use a dedicated test database for test execution.
3. Create `.env` only if missing. Run migrations and Django checks against PostgreSQL.
4. Run the existing tests and add database-backed tests for first import, cached import, title search, page boundaries, and serialization.
5. Use deterministic scraper fixtures in CI; keep a small live-source smoke test opt-in and separate from blocking tests.
6. Verify migration state with `makemigrations --check --dry-run`.
7. Create a lockfile using a chosen dependency workflow; suggested minimal change is a compiled lock from declared requirements, with exact versions installed in CI and deployment.
8. Add a GitHub Actions workflow with a PostgreSQL service and database readiness checks. No AI credentials or live paid calls in CI.
9. Correct stale SQLite/no-external-service documentation in `.github/copilot-instructions.md`.

### Files to touch

- `requirements.txt` and a new dependency lockfile.
- `docker-compose.yml` only if database readiness/test isolation needs changes.
- `scrape_me/tests.py` initially; split tests into a package deliberately if necessary, removing the conflicting module in the same change.
- New fixture files under `scrape_me/tests/fixtures/` if tests become a package, otherwise a distinct fixture directory.
- New `.github/workflows/backend.yml`.
- `README.md` and `.github/copilot-instructions.md`.

### Validation

```bash
docker compose up -d db
docker compose ps
python manage.py migrate
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test scrape_me
```

Run these in the selected virtual environment from the repository root. CI must use PostgreSQL explicitly; a passing suite of only `SimpleTestCase` tests does not establish database coverage.

**A1 completion:** Clean install succeeds, CI is green, PostgreSQL-backed tests actually create/read/update records, and the verified setup is documented.

## A2: Production configuration and deployment packaging

1. Introduce strict environment parsing for secret, debug, hosts, canonical origin, and trusted CSRF origins.
2. Keep safe development defaults local; production must fail clearly if required secrets/hosts are missing. An insecure fallback must not activate silently.
3. Configure secure session/CSRF cookies, HTTPS redirects, and trusted proxy headers for the selected hosting topology. Set proxy trust only for a proxy that controls those headers.
4. Add a production WSGI server dependency and start command. Suggested server: Gunicorn, with worker count based on instance memory and measured traffic.
5. Configure `STATIC_ROOT`, asset collection, and static serving. Include Django admin assets; reserve frontend asset/routing integration for D2.
6. Add separate liveness and readiness endpoints. Liveness reports process health; readiness performs a bounded database check without revealing credentials or internals.
7. Define staging database/secret separation, logging redaction, error reporting, and release migration commands.
8. Prepare deployment configuration locally. Default proposal is Render; a GCP preference changes packaging details, not API design.

### Files to touch

- `config/settings.py`, `config/urls.py`, and a small health-check module.
- `.env.example`, dependency manifests/lockfile, and `README.md`.
- New `render.yaml` or equivalent reviewed deployment configuration; do not provision services just to write the configuration.
- New operational notes under `docs/operations/` when implementing deployment.

### Required checks

- Production configuration cannot start with a missing secret or empty allowed hosts.
- `check --deploy` passes or documented hosting-specific dispositions explain remaining warnings.
- Correct host accepted; unexpected host rejected; proxy HTTPS handling does not cause a redirect loop.
- Admin and frontend assets load under production-like static settings.
- Readiness returns a controlled failure when the database is unavailable.
- Logs exclude tokens, database passwords, private recipe bodies, and sensitive query strings.

**A2 completion:** Production-like local startup and reviewed deployment configuration work; public provisioning is a distinct action.

## A3: Stage and verify the complete alpha

After B2/C2/D2, deploy to staging with real managed PostgreSQL and protected access. Run the complete two-user product smoke test, apply migrations as a controlled release step, restore a backup into an isolated database, and verify representative records and account boundaries.

Record deployment ID, migration state, tested routes, restore time, and rollback compatibility. Do not claim a restore test after merely confirming backups exist. Roll back application code only when compatible with the current schema; use additive migrations through the alpha.

**A3 completion:** The first-alpha release gate in the execution index passes on staging, and known limitations are recorded.

## Implementation evidence — September 6, 2026

Owner: Codex working session; changes are uncommitted for review (no PR pushed).

- **A1 implemented locally.** Started Docker Desktop and Compose PostgreSQL 16;
  retained the named volume. Created project `.venv` with Python 3.13.9. Initial
  17 tests passed, then 18 including real database import/cache/search/pagination
  coverage. Those legacy-route tests were superseded by private API coverage when
  the old endpoints were retired. Final suite: **42 passing PostgreSQL tests**,
  including concurrent saves/quotas and migration of a representative ownerless row.
- Exact `requirements.lock` resolved Django 5.2.17, recipe-scrapers 15.12.0,
  psycopg2-binary 2.9.12, DRF 3.18.0, Replicate 1.0.7, Gunicorn 23.0.0, WhiteNoise
  6.12.0, and dnspython 2.8.0. Fresh project install succeeded. `npm ci`/lock and
  TypeScript/Vite build are reproducible. CI workflow is implemented; **remote
  GitHub Actions has not been run/pushed**, so no remote green status is claimed.
- **A2 implemented locally.** Strict environment settings, secure production
  cookies/HTTPS/HSTS, opt-in proxy trust, bounded PostgreSQL connection/statements,
  private API cache policy, health probes, self-hosted fonts, static assets, and
  non-root multi-stage Docker/Gunicorn image. `check --deploy`: **zero warnings**.
  Image build succeeded. Production-style native Gunicorn and Docker smoke tests
  returned 200 for process/database health, homepage, frontend JS/CSS and admin CSS;
  unexpected host returned 400 and HTTP redirected with 301. Required secrets are
  injected at runtime; the image defaults to production and fails without them.
- **A3 remains the next release gate.** No managed staging service was provisioned
  and no pilot users were contacted. Local `scripts/restore_drill.py` successfully
  dumped/restored a synthetic three-recipe database, checked two independent owners
  sharing one URL, retained an unowned legacy row, and verified scoped exports.
  Measured restore: **0.181 s**, complete drill **1.226 s**. Disposable source/target
  databases were removed. This is local rehearsal evidence, not a managed-backup
  or staging recovery claim.

Resume with the [deployment runbook](../operations/deployment.md). Production data
was not available/modified. Before a real migration, inspect and back up that
instance. Do not reverse migration 0006 after owner-scoped source copies exist.

## Continuation: protected staging preparation

See [staging-release.md](../operations/staging-release.md) for verified cloud/API/ADC
state, a validated Terraform proposal, cost assumptions, secret/SMTP preparation,
and exact managed restore/rollback procedure. Local recovery is repeated successfully;
managed recovery, email delivery and remote CI remain unverified. Expansion tests
now include integrations/kitchen: do not run only `test scrape_me` for release.
