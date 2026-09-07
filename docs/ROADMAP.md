# FlavorBuddy roadmap

Updated September 7, 2026. **Product promise: turn saved recipes into dinners people cook.**
This is the authoritative current backlog. [Historical September 6 planning](history/roadmap-2026-09-06.md)
is retained for context; its dates, estimates, status tables and ordering are superseded.
Implementation evidence lives in [execution](execution/README.md).

**Current outcome:** items 1 and 3 are implemented; protected staging, managed restore
and rollback are verified. A3 remains partially open for SMTP delivery and pilot access/
observations. The real FlavorGirls server has not been connected.

## Product decisions

- Django/PostgreSQL owns recipe data; React provides the mobile web experience.
- One recipe UUID identifies one finalized, immutable recipe. Drafts are private and
  editable; finalization locks content. A variation starts a new private draft/UUID.
- Sharing changes visibility without changing identity. Archiving preserves identity
  and returns unavailable responses. Notes, favorites and private photos stay personal.
- Recipe reputation will come from user feedback, not an editorial approval queue.
  Feedback, reports and ranking are still separate future work.
- Preserve ingredient/step source text and unknowns. Structured IDs do not establish
  quantities, ingredient references, dietary suitability or culinary correctness.
- The 415 licensed starters are the accepted collection size; no 500-recipe target remains.
- Public catalog and owned-app experiences share search semantics; app catalog grants,
  authentication, visibility and budgets are enforced independently on the server.

## Current status

| Area | Implemented locally | Verified on managed staging | Validated with users |
| --- | --- | --- | --- |
| Foundation/accounts | PostgreSQL, locked dependencies, production settings, safe fetching, sessions/CSRF, private ownership | HTTPS/account/isolation smoke passed; SMTP pending | Pending |
| Save-to-cook | Import/review, drafts/finalization, library/search, variations, notes/favorites, cooking | HTTPS manual import/finalize/cook and browser smoke passed | Pending |
| Recipe lifecycle | Immutable content/UUIDs enforced by PostgreSQL; sharing and archiving; populated migration rehearsal | Managed migration and isolated restore/immutability verification passed | Pending |
| Starter collection | 415 canonical recipes and aliases; 140 cloud-hosted images previously verified | 415 seeded; managed media references and v2 document delivery checked | Pending |
| Pantry/photos | Manual inventory, preferences, conservative matching, private cover/result photos, durable cleanup | Private photo upload/hash/decode/isolation and scheduled cleanup passed | Pending |
| Catalog v1 | Read-only OAuth, explicit catalog grants, quotas, revocation, audit | Protected release deployed; existing v1 retained | Other app not connected |
| Catalog v2 | Search, UUID document detail, deterministic ingredient/step IDs, unavailable responses implemented and tested | Hosted client search/detail/revocation smoke passed | FlavorGirls end-to-end pending |
| Visual capture | Durable fixture-only detection/review/approval; live detection absent | Disabled by design | Not evaluated |
| Operations | CI workflow, Docker, Terraform and local restore rehearsal | Staging, cleanup, isolated restore and compatible rollback passed | Operator use pending |

Latest application verification: 87 PostgreSQL tests and 16 desktop/mobile browser
scenarios pass, with zero production warnings and green remote CI. Current release test counts
and hosted evidence are recorded in [07-release-and-v2](execution/07-release-and-v2.md),
not inferred from feature presence. GitHub had no workflow runs at the start of this increment.

## Authorized work now

The product owner approved items 1, 2 and 3 on September 7. This supersedes the earlier
session-specific statements that no push, protected deployment or staging spending is authorized.
Use the existing small staging footprint; live AI, billing and public launch are outside this increment.

| Priority / owner | Deliverable | Exit criteria |
| --- | --- | --- |
| 1 / Engineering | Reconcile roadmap and setup documentation | One current status table; historical work clearly archived; immutable lifecycle reflected throughout current instructions |
| 2 / Engineering + product owner for SMTP configuration | A3 protected managed staging | Green remote CI, digest-pinned release, real HTTPS/two-user smoke, private media, scheduled cleanup, managed restore and compatible rollback evidence; recovery email delivery tested once a sender is configured |
| 3 / Engineering | Focused FlavorGirls v2 contract | Grant-filtered phrase search, stable cursor pagination, UUID detail with validated RecipeDocumentV1, immutable ingredient/step IDs, no-content unavailable response, v1 compatibility and client smoke |

V2 initially supports q, relevance/newest/quickest, limit/cursor and max_total_minutes.
Rating sorts, votes, tag taxonomy and generated recipes are excluded. App tokens use
version-specific audiences but the same app grants and shared usage limits. Existing
v1 clients retain their endpoint and token contract.

A3 may be partially complete: SMTP delivery, operator browser access and observations
must be listed individually, rather than marking the entire milestone done after a deployment.
Managed SQL backups do not back up GCS objects; record object verification separately.

## Next after the authorized increment

1. Observe five target users importing/saving/cooking. Test whether draft/finalize/variation
   behavior is understandable without explanation. Resolve observed friction first.
2. Connect one real FlavorGirls server to its explicitly granted catalog and verify
   search → choose → fetch → cook, including unavailable recipes. No browser secrets.
3. Improve explainable ingredient matching with representative fixtures. Add a reviewed
   missing-item grocery list; defer quantity consolidation until normalization is reliable.
4. Add the smallest useful measurement set: import outcome, save/finalization, cook start
   and completion, and repeat use. Keep private recipe text/notes out of analytics.

## Deferred until evidence supports them

- Live photo-to-pantry: provider adapter, uncertainty/output contract, actual cost settlement
  and separately bounded evaluation spend before enabling it.
- Paid subscriptions: value/cost evidence, entitlement and webhook lifecycle, downgrade/export
  behavior, and provider budgets before checkout.
- AI recipe/image generation: explicitly requested private drafts, provenance, budgets and
  idempotency; no automatic generation on empty search.
- Public feedback/reports/voting: identity/permission design, abuse controls and a defined
  availability policy before ranking. Public sharing itself is already implemented.
- Weekly planning, households, full offline sync and grocery checkout: only after the
  core workflow and ingredient correctness demonstrate demand.

## Measures and release gates

Primary outcome: weekly accounts that record a cooking completion (self-reported).
Track import reliability on an agreed source set, first-week activation, return cooking,
and observed draft/variation confusion. Small pilots provide directional evidence,
not precise market conversion estimates. Paid intent is not a current release gate.

Hosting, isolation and recovery are now demonstrated on protected staging. User-observed
usability and recovery email remain gates before pilot readiness.
No broader rollout until user observations have been reviewed. Maintain owner, status,
blocking input, next action and dated evidence for each active item; update weekly.
