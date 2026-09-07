> Current recipe lifecycle: [06-recipe-lifecycle.md](06-recipe-lifecycle.md). Drafts are editable; finalized private/public recipes are immutable. This supersedes earlier editable-private-recipe plans.

# Highest-impact next steps and execution sequence

**Date:** September 6, 2026  
**Status:** A1–D2 implemented and locally validated; external release gates remain  
**Parent document:** [Comprehensive roadmap](../ROADMAP.md)

## First outcome to deliver

A user can import a real recipe, correct it, save it privately, find it again, and cook from a beautiful mobile interface. The system safely handles unsupported sources and malformed input, and another user cannot access the saved content.

This is the first complete product experience. Planning, groceries, household subscriptions, and recommendations build on it; they should not delay proving that people can successfully save and cook.

## Current next work — September 6 expansion update

A1–D2 are implemented locally; the ranked table below records the original plan.
**A3 remains the next unfinished release change set.** See the roadmap's
[current priorities and expansion decisions](../ROADMAP.md#current-priorities-and-expansion-decisions--september-6-2026)
for the authoritative next order: A3 → E1 controlled read-only owned-app API →
E2 private photos / E3 pantry and matching → E4 entitlements/durable jobs →
E5 photo capture → E6 paid lifecycle/personalization → E7 generation → E8 community.
These expansion items are proposed scopes, not completed implementations. Free/
paid packaging is provisional; API access is explicitly app-scoped and starts
with licensed starter content, never shared access to private libraries.

## Ranked next steps (original alpha plan)

| Rank | Work | Why it has high impact | Result |
| --- | --- | --- | --- |
| 1 | [Verify the baseline and establish production configuration](01-foundation.md) | Prevents building on an unverified database/deployment path. | Reproducible PostgreSQL environment, CI, documented staging configuration. |
| 2 | [Secure and unify imports](02-imports.md) | Importing is the existing core value and the largest current exposure/cost risk. | Validated extraction previews, controlled fetching, bounded AI usage, recoverable errors. |
| 3 | [Add private accounts and recipe APIs](03-private-library.md) | Converts a global scraping demo into a personal product. | Secure sign-in, owned drafts/recipes, editable private library. |
| 4 | [Ship the import-to-cooking frontend](04-frontend-alpha.md) | Creates a concrete experience to test with users. | Attractive, accessible mobile flow and pilot evidence. |

Rank reflects product impact; implementation dependencies require interleaving steps 2 and 3. Safe-fetching and schema work can start before accounts. Public imports require ownership and quotas first.

## Suggested implementation order

| Change set | Scope | Dependency | Indicative effort |
| --- | --- | --- | --- |
| A1 | PostgreSQL baseline, dependency lock, CI | None | 1–2 days |
| A2 | Production settings, health/static/deploy configuration | A1 | 1–2 days |
| B1 | Extraction schema, error contract, controlled fetch service | A1 | 2–4 days |
| C1 | Account lifecycle and private-recipe schema | A1 | 2–4 days |
| C2 | Owned CRUD/search/export endpoints and authorization tests | C1 | 2–3 days |
| B2 | Owned import previews, idempotent save, AI quotas | B1, C1, C2 | 2–4 days |
| D1 | UI tokens, navigation, local sample prototype | Product interviews; API-independent work may begin early | 2–3 days |
| D2 | Live import, preview, library, edit, and cook flows | B2, C2, D1 | 4–7 days |
| A3 | Staging smoke tests, restore drill, pilot deployment | A2, B2, C2, D2 | 1–2 days |

These are rough engineering estimates, not deadlines. Allow approximately 4–7 weeks for the first complete private alpha with one engineer, including integration and feedback. Recruitment can add calendar time. Household collaboration, durable queued imports, and full offline sync are additional scope unless explicitly pulled forward.

## Product validation while foundations are built

- Interview 5–8 target users about their last actual recipe-saving and cooking experience.
- Ask which tools they use, where saved recipes get lost, how they shop, and why they abandon recipes.
- Recruit 5 users for moderated prototype sessions and 20–30 for the later pilot.
- Test import → preview → cook before building every planned screen.
- Record observations and decisions, not just feature requests. Do not contact anyone automatically; recruiting messages require the product owner's authorization.

## Immediate working session

1. Read the four plans and inspect current changes; preserve uncommitted work.
2. Begin A1: start the local database, run migrations/tests against PostgreSQL, and add representative import integration fixtures.
3. Record baseline results and lock the tested dependencies.
4. Begin A2/B1: production settings and safe extraction boundaries.
5. Implement C1 before exposing any new customer data or paid extraction.

No hosting purchase or public deployment is needed to complete A1/B1/C1 locally. Resolve account/provider configuration when the relevant implementation reaches a concrete integration point.

## First-alpha release gate

- A clean environment builds and PostgreSQL migrations/tests pass.
- Customer content is private and authorization tests cover every resource route, including legacy routes.
- Unsafe destinations are blocked, request sizes/time are bounded, and invalid input produces structured errors.
- Paid extraction has authenticated ownership and enforceable usage limits.
- A user completes import, correction, save, retrieval, edit, and cooking without assistance.
- Failures preserve the user's work and give a useful next action.
- Staging uses production-like settings and demonstrates backup restoration.
- The product owner reviews pilot feedback before adding meal planning or monetization scope.

## Status tracking

Updated September 6, 2026. Owner: Codex working session. Implementation is in the
working tree; no commit/PR/push or public deployment was performed. Original user
changes were inspected and incorporated; no working-tree reset was used.

| Change set | Current status | Evidence / next action |
| --- | --- | --- |
| A1 | Implemented locally | Project venv/locks, PostgreSQL migrations, 42 backend tests; CI configured but remote run pending |
| A2 | Implemented locally | Zero deployment warnings; Docker image and production-style health/static/HTTPS smoke pass |
| B1 | Implemented locally | Pinned safe fetch and schema tests; one successful live Allrecipes extraction |
| C1 | Implemented locally | Sessions/CSRF, ownership migration, throttling and token recovery tests |
| C2 | Implemented locally | Owned CRUD/search/export/completion; cross-user and concurrency tests |
| B2 | Implemented locally | Owned previews, retry-safe saves, atomic AI quotas; live paid evaluation deferred |
| D1 | Built and technically validated | Responsive screens and axe checks; five moderated observations still pending authorization |
| D2 | Working local alpha | 8 real browser/API flows pass; managed-staging validation remains |
| A3 | **Next unfinished release change set** | Local restore drill passed; managed staging, restore/rollback and pilot observation remain |

Detailed evidence and limitations are appended to each execution plan. Start the
app with the root README. For release work, use `docs/operations/deployment.md`.
Do not reopen legacy endpoints, silently reverse owner uniqueness, or call paid AI
to make a release gate look complete. No pilot outreach, purchases or public
publishing is authorized by this implementation request.

## Starter collection increment — September 6, 2026

User requested 500 recipes from Public Domain Recipes. Its current pinned revision
contains only 415 recipe files; all 415 were validated and loaded. The 500 target is
retained in the snapshot manifest, with the 85-recipe shortfall explicit. The user subsequently accepted 415 as the final collection size. No supplemental
source is needed, and no duplicate padding was used.

Implemented a separate public StarterRecipe catalog, repeatable seed/build commands,
search/pagination/detail APIs and screens, authenticated retry-safe private-copy
saving, and exported read-only provenance. Existing private recipes and staff-only
legacy rows remain separate. Ingredients retain group labels and the original
Markdown/source/license/revision is preserved. Recipes are schema-validated, not
individually kitchen-tested.

Validation: **46 PostgreSQL backend tests and 10 desktop/mobile browser tests pass**.
Production frontend build passes. Browser flow covers public discovery → signup →
save → private edit, then verifies the public original remains unchanged. See
`data/starter/README.md` for regeneration and source evidence. The previous A3
managed-staging and moderated usability gates remain unfinished.

## Managed starter images — September 6, 2026

Google Cloud Storage integration implemented via `starter_images` Django storage
alias, with a local filesystem development backend. Dependencies locked. Repeatable
`store_starter_images` command validates/re-encodes curated source files, uploads
before updating references, preserves custom personal images, records object
metadata and survives reseeding. 49 PostgreSQL tests pass. Deployment instructions
are in `docs/operations/deployment.md`. Next unfinished storage step: configure
an existing GCS bucket and credentials, run the migration and verify cloud delivery.
Cloud resources/public access were not provisioned. Original A3 release gates remain.

Storage follow-up: user authorized creation of a new Google Cloud project and
completed CLI sign-in. Created `flavorbuddy-20260906` (display name FlavorBuddy,
project number 560489769953). Billing is not linked and no bucket exists yet.
Next action requires the user's choice/authorization of billing account; four
open accounts are available (Firebase Payment, Biscuit Land, BiscuitLandFire,
GauntletAi). Application Default Credentials are not configured yet (CLI login
alone does not configure them). All 140 starter images are now stored locally;
a repeat migration succeeded with zero failures, and live Django image delivery
returned HTTP 200 image/webp with successful decoding after server restart.

Cloud storage completed September 6: user authorized Biscuit Land billing, linked
to `flavorbuddy-20260906`. Created uniform-access US Central1 bucket
`flavorbuddy-20260906-starter-images`, public object-read for licensed starter
images only. Uploaded 140 local WebP objects using authenticated gcloud storage;
all 140 anonymous HTTPS GETs passed byte-hash comparison and full WebP decoding.
Updated starter references and matching unchanged private-copy images to cloud
URLs; local .env selects gcs. Application Default Credentials browser sign-in
was initiated but is still pending; CLI credentials handled this initial upload.
Future Django management-command uploads require ADC or an attached service identity.

## September 6 continuation — A3 preparation and E1–E5 local increments

The earlier proposed-only expansion status is superseded by
[05-expansion.md](05-expansion.md). Controlled app-only catalog access, private
cover/result photos, manual pantry/preferences/matching, and durable fixture
capture with explicit approval are now implemented locally. A3 managed evidence
is still outstanding. The staged infrastructure/cost proposal is in
[staging-release.md](../operations/staging-release.md). It has not been applied.
Current validation: 70 PostgreSQL tests and 14 desktop/mobile browser scenarios.
No additional cloud spending, live AI, remote push, public release or outreach.
