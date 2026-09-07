# September 7: protected staging and FlavorGirls v2

The product owner approved roadmap reconciliation, A3 and focused v2 integration.
The feature/API work is implemented and deployed to IAM-protected managed staging.
Managed restore and compatible rollback have passed. SMTP, real-client onboarding
and observed pilot use remain explicitly unfinished.

## Implemented

- Replaced conflicting roadmap status/backlogs with one current roadmap; archived the
  historical planning document and staging proposal. Updated root setup/lifecycle docs.
- V2 grant-filtered search across title, description and ingredient text; bounded
  signed keyset cursors, relevance/newest/quickest and optional maximum time.
- UUID document detail and recipe-scoped stable ingredient/step IDs; source text and
  unknowns preserved. All 415 public recipe documents validated against RecipeDocumentV1.
- Private/archived granted recipe identity returns 410 with no document. Ungranted or
  unknown identity returns 404. Private annotations/photos are excluded.
- Separate version-specific OAuth audiences, shared grants/quotas/revocation, UUID audits.
  Existing v1 remains compatible. No voting, generated recipes or live AI was added.
- OpenAPI 3.1 contract validated with openapi-spec-validator. Regression coverage checks
  local schema references. Standalone RecipeDocumentV1 is served separately.
- GCS deployment configuration fixed after real-host testing exposed an unsupported
  django-storages option; a real production-backend initialization regression test was added.
- OAuth deployment compliance settings are explicit; CI now fails on production warnings.

## Local and remote verification

- Baseline: 78 PostgreSQL tests passed before changes.
- Final application suite: **87 PostgreSQL tests pass**, including nine new integration/
  storage checks and the populated lifecycle migration rehearsal.
- **16 desktop/mobile browser scenarios pass**; TypeScript/Vite production build passes.
- Production checks: **zero warnings**. Terraform validate and current-document link checks pass.
- Remote CI initially caught an existing Docker healthcheck quoting error; it was fixed.
  Green runs include [34087653669](https://github.com/BiscuitNick/flavorbuddy-python/actions/runs/34087653669),
  [34088199372](https://github.com/BiscuitNick/flavorbuddy-python/actions/runs/34088199372), and
  [34088478613](https://github.com/BiscuitNick/flavorbuddy-python/actions/runs/34088478613).
  The last includes strict warning-free production checks on application commit `565febe`.

## Hosted evidence

Canonical app origin: `https://flavorbuddy-staging-560489769953.us-central1.run.app`.
Cloud Run IAM remains enabled; only the explicit operator has an invocation binding.
Anonymous HTTPS is denied. The original public starter image bucket remains public.
The separate private staging bucket has public-access prevention and runtime identity access.

- Managed migration execution `flavorbuddy-staging-migrate-mmh6v` succeeded.
- Licensed 415-recipe starter snapshot, including 140 managed-image references, seeded;
  staging-only catalog `licensed-starters` and a smoke client registered explicitly.
- Real HTTPS two-user smoke passed: manual import → review/save → finalization → cook,
  independent same-source recipes, private exports, pantry isolation, secure cookies,
  CSRF rejection, private photo upload/ownership/hash/decoding.
- Real desktop and 360px mobile browser sign-in → recipe → cooking passed, with no
  horizontal overflow or JavaScript runtime errors. Screenshots retained in protected
  local operator evidence. Automated checks are not moderated user observations.
- Hosted v2 smoke searched “pasta”, retrieved 12 candidates, validated a selected UUID
  document and verified that token revocation denied subsequent access.
- Scheduler-triggered housekeeping execution `flavorbuddy-staging-housekeeping-nwmwx`
  succeeded. It performs hourly import/media/OAuth cleanup through a dedicated identity.
- One live Allrecipes URL import returned controlled `source_unavailable`; no recipe was
  saved and no paid fallback occurred. Manual imports passed. Hosted URL reliability
  needs a supported-source evaluation; one blocked source does not establish general reliability.

## Recovery and rollback

On-demand managed backup **1788760282232** succeeded September 7 at 05:52:13 UTC.
It contains the 415 catalog recipes and two synthetic private recipes. Restoration is
into the separate disposable `fb-restore-20260907`, never the serving instance.
Restore operation: `9bf4498d-ede3-47a2-9f8f-14b100000032`, completed successfully
at 06:00:54 UTC. Managed restore duration: **7 minutes 36 seconds** (05:53:18–06:00:54).
Isolated verification execution `flavorbuddy-staging-restore-check-hrcks` succeeded
at 06:04:52 UTC. It verified **417 recipes**, 415 starters, private notes, cooking
completion/pantry/photo counts, catalog grants, PostgreSQL content immutability,
scoped exports, pantry ownership, and private GCS photo ownership/hash/decoding.
See the [captured result](../operations/evidence/restore-result-2026-09-07.json) and
[exact verification code](../operations/evidence/restore-check-2026-09-07.py).
The disposable restore-check job was deleted after verification. Instance
`fb-restore-20260907` deletion completed at **06:07:28 UTC** (operation
`d98dd4c8-1bd2-4ae2-bd91-5cec00000032`). A final inventory contains only the
serving `fb-staging-pg` database instance and the migration/housekeeping jobs.
Temporary private fixture/diagnostic objects were removed; the managed backup and
nonsecret verification evidence were retained.

Previous working revision: `flavorbuddy-staging-00002-bsg`, image digest
`sha256:c0eb35a4f95b3df4051be68087dbf70216577a077579f1996c538660941b16b5`.
Candidate: `flavorbuddy-staging-releasecheck-20260907`, digest
`sha256:ab636fe3c4c695873df123707071f06d0075bb05024178046bd8902c7a1f6f78`.
The candidate passed protected tagged-origin health/session/OpenAPI smoke at 0% traffic,
then passed the full two-user and v2 smoke after receiving canonical-origin traffic.
Rollback to `flavorbuddy-staging-00002-bsg` passed the full two-user/private-media
and v2 smoke. Final Terraform reconciliation restored the verified image and removed the
temporary tagged host and routing. Final revision **`flavorbuddy-staging-00004-8b5`**
serves 100% latest-revision traffic. Full two-user/private-media and v2 smoke passed
again on that final revision; Terraform reports **no infrastructure drift**.

## Remaining inputs and limits

- SMTP provider, sender and credentials have not been supplied. Recovery is visibly disabled;
  real email delivery/expiry/single-use checks remain an A3 gate. No email was sent.
- Real FlavorGirls server identity/access and pilot browser login have not been configured.
  This increment provides the server contract and staging smoke, not a deployed second app.
- Local ADC sign-in is still pending; the managed host uses attached service credentials.
- SQL backup restoration verifies separately retained GCS objects, not recovery of deleted
  images. Private object soft-delete retention remains disabled per the approved proposal.
- No moderated user observation, public app release, paid AI, subscriptions or outreach.

Follow [staging operations](../operations/staging-release.md) for resources, private state,
secret handling, budget alerts and release/restore procedure. The $30 project budget alert
is not a spending cap. Temporary recovery resources are removed after verified completion.
