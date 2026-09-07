# Deployment runbook (prepared; no public services provisioned)

Current managed staging status and operator instructions are in
[staging-release.md](staging-release.md). Dated implementation/storage notes below
are historical; they do not override the current release evidence.


Use the application Docker image with PostgreSQL 16 (Cloud SQL is compatible with
the existing GCP direction). Keep staging and production databases, secrets, and
SMTP credentials separate. Inject POSTGRES_* via the host secret manager.
Set DJANGO_ENV=production, DJANGO_DEBUG=false, a random DJANGO_SECRET_KEY of at
least 50 characters, DJANGO_ALLOWED_HOSTS to the exact hostname, PROJECT_URL to its
HTTPS origin. Set TRUST_PROXY_HTTPS=true only behind an ingress that overwrites
X-Forwarded-Proto and disallows direct access to the application port.
HSTS includes subdomains: use a dedicated domain with HTTPS on all subdomains.

Release: back up first, run `python manage.py migrate --noinput` in a single
release process, then replace application instances. Do not run migrations in
every web worker. Configure /health/live and /health/ready probes over HTTPS (or
trusted forwarded HTTPS). Database connect and statement timeouts are bounded.
Gunicorn listens on port 8000; map the platform port to it. Access logs are disabled
because URLs may contain private source queries. API logs contain error codes and
request IDs only. Never enable HTTP/provider debug logging in production.

Build: `docker build -t flavorbuddy-alpha .`. Run `check --deploy` with deployment
environment before rollout. AI is disabled by default; a credential alone cannot
enable it. Configure SMTP to enable recovery; local email stays in memory.

Backups: `pg_dump -Fc` using secret-injected PG* values, encrypt/store outside the
application. Restore into an isolated database with `pg_restore --no-owner`, run
migrations/checks and verify record counts and two-user isolation. Record actual
restore duration and evidence before the A3 gate. Never restore over live data.
Application rollback must support the current schema; after owner-scoped copies
exist, reversing the old global source uniqueness constraint is unsafe.

## Local validation evidence (September 6, 2026)

The non-root multi-stage image built successfully. Native Gunicorn and the Docker
container passed HTTP smoke tests with a trusted-forwarded HTTPS header: live/ready,
homepage, frontend JS/CSS, admin CSS, and CSRF bootstrap all returned 200. The native
host rejection test returned 400; an unforwarded HTTP request returned 301.
Production `check --deploy` reported no warnings. These requests were local only.

`deploy/compose.production.yml` is a reviewable local production-style override.
It requires production secret/host/origin values and publishes only on loopback.
Set up a TLS ingress before browser login with secure cookies. It does not provision
cloud services or perform release migrations automatically. Do not use the Compose
example database password in a real deployment.

The root `.env.example` describes development settings; production values override
these. No `.env` is copied into the image. The image defaults to production and
refuses to start without required secret/host/origin settings. Build-time static
collection explicitly uses development settings and does not connect to a database.

Run `scripts/restore_drill.py` for a reproducible local synthetic restore. The
September 6 rehearsal restored three recipes in 0.181 seconds (1.226 seconds end to
end), verified two users' independent copies and scoped exports, and retained the
legacy ownerless row. It cleaned up both temporary databases. A managed-staging
restore and rollback exercise is still required; this does not establish a recovery
SLA. SMTP delivery, forwarded-address handling, external request limits and ingress
CSRF behavior require verification on the actual host before a pilot.

## Google Cloud Storage starter images

`STARTER_IMAGE_STORAGE=gcs` and `GS_STARTER_BUCKET_NAME=<existing bucket>` enable
Django's Google Cloud Storage backend for licensed public starter images. Use a
dedicated bucket with uniform bucket-level access and public object read access;
the application deliberately does not change bucket IAM or create infrastructure.
The uploader needs object read/create permissions. Use Application Default
Credentials locally (`gcloud auth application-default login`) or an attached
service identity in production. Do not put service-account key files in the repo.
Private uploads must never use this public storage alias.

With the catalog seeded, obtain the pinned source checkout (revision recorded in
`data/starter/public-domain-recipes.json`), then run:

```sh
python manage.py store_starter_images --source-directory /path/to/public-domain-recipes/static/pix
```

The command reads only curated image filenames from the snapshot, validates and
re-encodes images as WebP (maximum 1200px), strips embedded metadata, and uses
content hashes as immutable object names. It records keys, source URLs, hashes,
dimensions and sizes in starter provenance. Database references change only after
storage succeeds. Failures are reported per recipe and the command can be rerun;
unchanged files are reused. Catalog reseeding preserves managed references.
Existing personal copies with an unchanged starter image are repointed; custom
images are preserved. No general image upload endpoint is added by this increment.

Development defaults to `STARTER_IMAGE_STORAGE=local`, with ignored `media/` files
served by Django only with DEBUG enabled. These files are excluded from Docker
builds. Production must use the GCS backend for managed images; local development
URLs must not be imported into a production database. To move an existing database
between storage environments, rerun the image command under the destination
configuration before serving it. Keep media backups separately from database dumps.

September 6 validation: 49 PostgreSQL tests pass, including image decoding,
upload failure recovery, repeated migration, preservation of user edits and
catalog reseeding. Live cloud upload remains pending: no GCP project, account or
bucket is configured locally. No bucket or public IAM grant was created.

Follow-up: CLI authentication and user-authorized project creation completed:
`flavorbuddy-20260906`, project number `560489769953`. Billing account selection,
bucket creation, runtime ADC/identity configuration and cloud upload remain
pending. Local migration and repeat run both stored 140 images with no failures;
live local image HTTP 200 and WebP decoding verified. No billing account linked.

Cloud activation: Biscuit Land billing linked with user approval. Bucket
`gs://flavorbuddy-20260906-starter-images` in `us-central1` now holds all 140
starter images, with uniform bucket-level access and public object viewing.
All 140 cloud files passed anonymous HTTP GET, SHA256 and WebP decode checks.
The app's stored image URLs now point to this bucket. Initial upload used gcloud
CLI credentials; finish the pending ADC browser login for future Django uploads.
This public bucket must not receive private user uploads.

## Current continuation status

Protected managed staging was authorized and provisioned September 7. Follow
[staging operations](staging-release.md) and [release evidence](../execution/07-release-and-v2.md).
Local ADC remains optional pending sign-in; the host uses its attached runtime identity.
Private photos use the separate protected bucket. The fixture capture worker is not a
production inference service; live capture and paid AI remain disabled.
