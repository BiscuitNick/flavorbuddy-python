# Protected staging operations

Updated September 7, 2026. Staging was authorized and provisioned in the current
increment. See [original release evidence](../execution/07-release-and-v2.md) and
[the current Firebase increment](../execution/08-firebase-auth.md) for checks and unfinished gates. The [original proposal](../history/staging-proposal-2026-09-06.md)
is retained as historical cost/architecture context.

## Environment

- Project: `flavorbuddy-20260906`, region `us-central1`; existing Biscuit Land billing.
- Service: `flavorbuddy-staging`; canonical application origin:
  `https://flavorbuddy-staging-560489769953.us-central1.run.app`.
- IAM invocation remains enforced. The explicit operator is `nickkenkel@gmail.com`.
  Anonymous invocation is denied. There is no public app release or IAP pilot login yet.
- Cloud SQL: `fb-staging-pg`, PostgreSQL 16 Enterprise `db-f1-micro`, 10 GiB SSD,
  growth capped at 20 GiB, seven backups and seven-day PITR, deletion protection.
  No authorized database networks; the app uses the Cloud SQL Unix-socket connector.
- Runtime: `fb-staging-runtime@flavorbuddy-20260906.iam.gserviceaccount.com`.
  It uses an attached service identity; local ADC sign-in is not needed by the host.
- Public starter images: existing `flavorbuddy-20260906-starter-images` bucket.
- Private photos: `flavorbuddy-20260906-staging-private-photos`, public access
  prevention enforced. Session ownership checks protect application delivery.
- Hourly cleanup: Cloud Scheduler `flavorbuddy-staging-housekeeping` at :17 UTC,
  invoking the same-named Cloud Run job through a dedicated scheduler identity.
  It runs `expire_imports`, `cleanup_private_photos`, and `cleartokens`.
- AI/capture remain disabled. Firebase Google sign-in replaces SMTP recovery; see
  [Firebase activation](firebase-auth.md) for the remaining provider-console step.

A project-filtered $30 monthly budget alert is configured at 50%, 90%, and 100%.
It is a notification, not a spending cap. The original $15–30/month GCP estimate
remains an estimate; review Firebase usage limits before expanding beyond the pilot.
The temporary restore instance/job must be removed after the recorded drill.

## Operator access and secrets

To inspect the protected host through CLI requests, obtain a Google identity token
without printing it and send it only to this service in `X-Serverless-Authorization`.
Reserve `Authorization` for the application OAuth token when exercising integrations.
Do not attach Google credentials to third-party starter image requests.
The live browser smoke adds the Google header only for the exact application origin;
normal browser visits still need an operator proxy or a separately configured IAP flow.

The public API origin above is distinct from Cloud Run's additional hashed `a.run.app`
URL. Django deliberately allows the canonical host; arbitrary Host headers are rejected.
Configure application origins explicitly before granting another operator/client access.

Secret Manager contains versioned Django and database passwords. SMTP has a secret
container but no configured value. No credentials are stored in Git or Terraform state.
Operator release inputs and smoke credentials are mode-0600 files under the private
`~/.local/share/flavorbuddy/staging/` directory. Treat them as secrets; do not paste them
into shell arguments, screenshots or logs. The staging smoke client is not a credential
for the real FlavorGirls server; register that server explicitly when its identity is known.

## Terraform and subsequent releases

Configuration is in `deploy/staging/`. The local Terraform backend is intentionally
configured to a protected persistent operator path outside the checkout:

```sh
terraform -chdir=deploy/staging init -reconfigure \
  -backend-config=path="$HOME/.local/share/flavorbuddy/staging/terraform.tfstate"
terraform -chdir=deploy/staging plan \
  -var-file="$HOME/.local/share/flavorbuddy/staging/release.tfvars.json" \
  -out=/private/path/release.tfplan
```

Use ADC or a short-lived supported provider credential in the process environment;
never print or save access tokens. Back up the protected state file before releases.
No remote state backend is configured; do not run Terraform from an empty state.
Review the plan for replacements, public grants and unexpected spend before apply.

Build `linux/amd64` images from the reviewed tree, push to the project's Artifact
Registry and pin their sha256 digest in the release inputs. Run remote CI first.
Execute `flavorbuddy-staging-migrate` once; retries are disabled. Its command is Python
and its arguments are `manage.py migrate --noinput`. Explicit job argument overrides
can perform reviewed one-off management work without changing the serving process.
Do not run migration reversal as an application rollback.

Keep the previous healthy revision and digest recorded. For a candidate, deploy with
no traffic, test its protected tagged URL, then move canonical-origin traffic to it.
A tag needs an explicitly allowed Django host. Test two-user isolation, GCS media,
CSRF, sessions and v2 after switching. Return traffic to the previous compatible revision
to demonstrate rollback, then restore the approved candidate. Terraform finally declares
100% latest-revision traffic and removes temporary tag/host configuration.

## Verification and recovery

The reusable `scripts/staging_smoke.py` creates two synthetic accounts and validates
manual import/finalization/cooking, exports, pantry, private GCS photos and authorization.
Pass `--verify-only` to reuse the recorded accounts/identities during rollback.
Its evidence file contains credentials and belongs outside the repository.
`catalog_v2_client.py` validates hosted search/detail and token revocation without printing secrets.

Create an on-demand managed SQL backup and wait for SUCCESSFUL. Restore only into a
separately named disposable instance, never into `fb-staging-pg`. Run an isolated
verification job connected to that restored instance; verify exact synthetic counts,
immutable UUID/content triggers, catalog grants, two-user exports/pantry and private
photo authorization/hash/decoding. Record backup ID, operation and duration. Delete
only that disposable instance and job after the results are recorded.

A SQL backup does not back up GCS bytes. This drill verifies that restored references
can read the separately retained objects; it does not demonstrate recovery of a deleted
GCS object. Private bucket soft-delete retention is disabled per the original proposal.
Define an explicit media recovery/retention policy before promising recovery of deleted photos.

## Remaining pilot inputs

- Complete [Firebase Google provider activation](firebase-auth.md), then verify a
  real protected-host sign-in. Google handles account recovery; SMTP is no longer a gate.
- Choose pilot browser access (IAP or another reviewed protected login flow) and users.
- Observe usability; browser automation is not evidence of user validation.
- Establish a supported import source set from hosted results. One live Allrecipes
  attempt returned `source_unavailable`; the editable manual path passed. Universal
  URL support is not claimed, and no paid fallback was enabled.
