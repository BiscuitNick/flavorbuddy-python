# Protected staging proposal and evidence

Updated September 6, 2026 (local date). This is a reviewable proposal, not a deployment.
No additional cloud infrastructure was created in this implementation session.

## Verified account state

Read-only inspection found the existing public starter bucket in US-CENTRAL1,
with uniform bucket-level access. Cloud SQL Admin and Cloud Run Admin APIs are
disabled; their list operations failed, so a successful empty inventory is **not**
claimed. The enabled-service listing corroborated both APIs being absent. Repeat
inventory after approved API enablement, before creating similarly named resources.
`gh run list` returned an empty list for BiscuitNick/flavorbuddy-python. The local
workflow has not been pushed, and no remote CI execution is claimed.
ADC discovery failed with DefaultCredentialsError. A fresh browser login was opened;
completion still requires the user's Google sign-in. Do not print tokens or copy
CLI credentials into source files to bypass ADC setup.

## Concrete proposed resources

`deploy/staging/` is Terraform configuration validated with Google provider 7.46.1;
its provider lock is included. No plan/apply has run. It proposes:

- One us-central1 PostgreSQL 16 Enterprise db-f1-micro, zonal, 10 GiB SSD (automatic
  growth bounded at 20 GiB), seven retained backups and seven-day PITR logs.
- One IAM-protected Cloud Run service, 0–2 instances, 1 vCPU/512 MiB each, two
  Gunicorn workers, and one explicitly invoked migration job with no automatic retry.
- A dedicated runtime identity, Artifact Registry repository, three Secret Manager
  secret containers, and version-pinned references. Secret values and SQL login
  creation stay outside Terraform state. No service-account key files.
- A **separate private** staging photo bucket with public-access prevention enforced,
  no public IAM members, no soft-deleted object retention, and object access only
  for the runtime. The existing public starter bucket is not modified.

No allUsers/allAuthenticatedUsers grant is allowed. Initially invoke through an
operator's authenticated Cloud Run proxy; for realistic HTTPS browser validation,
use an operator-controlled local TLS forwarding origin with the corresponding
Django host/origin, or configure an explicitly reviewed IAP/custom OAuth client.
IAM protection must not be disabled to make browser testing easier. A production-
like HTTPS browser origin and operator identities remain inputs, not solved facts.
See [Cloud Run IAM](https://docs.cloud.google.com/run/docs/securing/managing-access)
and [IAP setup](https://docs.cloud.google.com/run/docs/securing/identity-aware-proxy-cloud-run).

## Cost estimate for approval

Assumptions: 730 hours/month for the tiny database, light private testing, no HA,
small media and backups, no paid AI. Cloud SQL db-f1-micro compute at $0.0105/hour
is approximately **$7.67/month**, before disks/backups/networking. Shared-core
instances have no Cloud SQL SLA. [Cloud SQL pricing](https://cloud.google.com/sql/pricing?authuser=1).

Budget **$15–30/month for this GCP staging footprint**, plus **$0–15/month reserved
for an as-yet unselected transactional SMTP provider**, and **up to $2 for a short
isolated recovery drill**. These ranges are estimates, not vendor quotes or enforced
spending caps. Actual disk growth, egress, image pulls, retained logs, secrets and
billing-account free-tier consumption can change them. Cloud Run has usage-based
charges and monthly free allowances; do not assume the account has unused allowance.
[Cloud Run pricing](https://cloud.google.com/run/pricing?authuser=3).

Before creating resources, obtain approval for this concrete footprint and a chosen
SMTP plan, then recheck calculator estimates and set project billing alerts. Billing
alerts notify; they do not stop charges. No final consumer pricing or checkout is
proposed. A larger database, HA, load balancer, or always-on worker is a new decision.

## Prepare and release after approval

1. Inventory resources again; adopt existing equivalents rather than duplicating
   them. Review Terraform variables for digest-pinned image, exact HTTPS origin,
   explicit invokers, SMTP sender/host/user, and numeric secret versions.
2. Use a protected state location. `terraform -chdir=deploy/staging init` and
   `terraform -chdir=deploy/staging plan -out=staging.tfplan` are operator commands;
   inspect the concrete plan before apply. Bootstrap API/repository/secret containers
   first, populate secret versions and a separate SQL login, then deploy service/job.
   Do not put secret values in shell arguments, logs, a tfvars file or Terraform state.
3. Build the image from the reviewed complete working tree and push only after
   release authorization. Run the migration job once:
   `gcloud run jobs execute flavorbuddy-staging-migrate --region=us-central1 --project=flavorbuddy-20260906 --wait`.
   Seed licensed starters as a separate one-off job. Capture revision and image digest.
4. Check anonymous invocation is denied, health/ready and assets work through the
   protected ingress, and Host/X-Forwarded-Proto cannot bypass policy. Verify session
   cookies, CSRF, two-user isolation and recovery on the actual HTTPS origin.
5. Configure the selected sender domain's SPF/DKIM/DMARC and secret-injected SMTP
   credentials. Test reset delivery only to an explicitly authorized operator address:
   valid delivery, bounded timeout, expired/single-use token, and generic unknown-email
   response. No live email has been sent. Backend EMAIL_TIMEOUT is now ten seconds.
6. Schedule `expire_imports`, `cleanup_private_photos`, and OAuth `cleartokens` using
   an approved job scheduler. Preserve failed cleanup records for retry; monitor them.
   Capture fixtures remain disabled in production. Do not run the development demo
   worker as a paid inference service. Review request-body and ingress-address limits.

## Actual managed recovery and rollback exercise — still required

Use synthetic staging accounts/content first. Record source instance, backup ID,
backup completion time, exact target instance and observed duration. Create an
on-demand managed backup with `gcloud sql backups create --instance=fb-staging-pg
--project=flavorbuddy-20260906`; confirm SUCCESSFUL using `gcloud sql backups list`.
Create an isolated `fb-restore-<date>` PostgreSQL 16 instance under the approved drill
budget; **never use the serving instance as the restore target**. Restore that backup
with `gcloud sql backups restore BACKUP_ID --backup-instance=fb-staging-pg
--restore-instance=fb-restore-<date> --project=flavorbuddy-20260906`.

Point an isolated candidate revision/SQL connector at the restored database. Verify
migrations, exact synthetic record counts, independent same-source copies, private
exports, app catalog grants, pantry ownership and private image authorization. A
SQL backup does not back up GCS objects: verify referenced private objects separately.
Record actual restore duration and checks; merely listing backups is insufficient.
Remove only the explicitly disposable drill instance after recording evidence.

For rollback, deploy a second schema-compatible image digest with no traffic, smoke
it, switch traffic, then return traffic to the recorded previous revision with
`gcloud run services update-traffic flavorbuddy-staging --to-revisions=PREVIOUS_REVISION=100
--region=us-central1 --project=flavorbuddy-20260906`. Verify the same flows after
rollback, then return to the approved candidate. Do not reverse ownership migrations
or delete new tables. The local synthetic restore is not managed restore evidence.

## Local evidence

The synthetic Compose dump/restore passed with three recipes, two independent owners,
one legacy row and scoped exports: restore 0.267 s, end-to-end 2.677 s. Terraform
fmt/validate pass. Fresh lockfile installation and current backend/browser counts
are recorded in `docs/execution/05-expansion.md`. Managed deployment, email delivery,
restore/rollback and observed usability remain release blockers.
