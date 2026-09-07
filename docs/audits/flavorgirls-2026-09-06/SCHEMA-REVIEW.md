> Superseded lifecycle decision: one Recipe model with draft/finalized state and private/public visibility is now implemented locally. See [implementation and migration evidence](../../execution/06-recipe-lifecycle.md). The table recommendations below are historical review notes.

# Schema review: one published recipe, one permanent ID

This review supersedes the previous revision-based contract proposal. It covers all
17 application-defined Django models in scrape_me, integrations and kitchen, plus
the proposed feedback/recipe contract. It does not audit third-party Django/OAuth
tables or change application behavior. Decisions below are recommendations unless
explicitly identified as the user's settled product requirements.

## Settled model

- Published recipe content is immutable. One recipe ID always identifies the same
  content. A new recipe is a new identity, not a new version behind the old link.
- A new recipe may optionally name `inspired_by_recipe_id`. This is attribution,
  not a revision chain, automatic replacement, or permission to inherit feedback.
- User thumbs feedback and reports are the curation mechanism. No team editorial
  approval, reapproval, or kitchen-testing gate exists.
- User drafts/private working copies may remain editable. Their conflict-detection
  counters are internal and have no place in the public recipe contract.
- Publication availability, vote totals, and reports can change without changing
  the recipe's ingredients/instructions/provenance.

The published document uses a plain UUID `recipe_id`, `published_at`, and a
`schema_version` for its JSON format. There is no revision ID, revision number,
parent revision, or latest-revision endpoint. Future schema-format changes must not
silently change the content or representation served at a pinned contract endpoint.

An optional `inspired_by_recipe_id` in provenance is another recipe UUID or null.
It does not imply endorsement by the source author or establish reuse rights.
Keep source URLs/license metadata separately. Source Git commits remain provenance;
they are not FlavorBuddy recipe revisions. Inspiration links are recorded at
publication and immutable along with the recipe.

## Proposed minimum product tables

| Table/concept | Purpose and minimum fields |
| --- | --- |
| PublishedRecipe | UUID ID, immutable structured content/provenance/source archive, published_at. Optional inspired-by ID in provenance, validated against a known recipe. Mutable availability status/reason may live in separate columns on this same row. No separate revision/publication/editorial tables required. |
| PrivateRecipe (existing Recipe) | Owner's editable working copy, private notes/favorite, optional published source ID, internal edit counter. Publishing copies content into a new immutable PublishedRecipe; editing privately never changes the published object. |
| RecipeVote (new) | User identity, published recipe ID, value up/down, timestamps; unique user+recipe. Change/remove a vote. Counts are derived, not client-controlled. No star rating or revision foreign key. |
| RecipeReport (new) | Reporter identity, published recipe ID, optional step ID, category, explanation, state, timestamps. Step ID validated within this exact recipe's immutable steps. No revision foreign key. |

The existing StarterRecipe is the natural migration starting point for
PublishedRecipe. Avoid introducing both a new RecipeIdentity and RecipeRevision on
top of it. Keep the public/private boundary explicit; do not turn all ownerless
legacy Recipe rows into public recipes. Catalog membership remains a join table.
Do not add normalized ingredient, timer, equipment, tag-assignment or step tables
merely to implement this document API. Validated JSON is sufficient initially;
search indexes or dedicated tables should follow demonstrated query needs.

## Existing table-by-table review

Paths refer to the application root flavorbuddy-python.

| Current table/model | Recommendation | Reason / concrete implication |
| --- | --- | --- |
| Recipe — scrape_me/models.py:11 | Keep for editable private copies; add a published-source ID when implemented | Notes/favorites are private. `version` is a save-conflict counter, not public history. The owner+source_url unique constraint and SaveStarterView source-URL lookup can conflate separate immutable recipes sharing a URL; distinguish published recipe IDs and preserve legacy import deduplication separately. |
| StarterRecipe — scrape_me/models.py:112 | Evolve into the immutable published recipe store | Current JSON content is usable storage, but no immutability enforcement exists. `seed_starter_recipes.py` uses update_or_create by slug and can overwrite the same public ID. Changed seed content must get a new ID; identical reseeds are no-ops. Keep permanent legacy-ID mappings. |
| CookingCompletion — scrape_me/models.py:102 | Keep; point published sessions directly at a published recipe ID | For editable private copies, snapshots remain useful. For immutable published recipes, no recipe_version is needed. Existing recipe CASCADE deletion also deletes completions, so public-history retention must be explicitly designed before changing relationships. |
| ImportDraft — scrape_me/models.py:70 | Keep | Processing/error/idempotency state is different from a published recipe. Its owner+key uniqueness protects retries. No generic workflow abstraction needed. |
| UsageCounter — scrape_me/models.py:90 | Keep | Simple quota counters are used by existing request/extraction paths. Not recipe curation. Define expiration/cleanup for old time-window keys as operational work. |
| AIInvocation — scrape_me/models.py:95 | Keep for now | Separates invocation state/provider reference from editable draft content and supports paid-call tracking. Do not unify all job types during this recipe change. |
| Catalog — integrations/models.py:4 | Keep if app-specific collections/grants are required | Membership controls what an app can read. It must not be called editorial approval. Repoint membership to published identities during migration; removing membership must not repoint old links. |
| AppGrant — integrations/models.py:11 | Keep | OAuth app entitlement, expiry and quotas are necessary access controls, distinct from recipe quality. |
| AppAudit — integrations/models.py:24 | Keep; adjust resource identifier | Current resource_id is integer-only; a UUID published recipe needs a compatible field when migrating. Retain action/status/request metadata, not private recipe bodies. |
| PantryItem — kitchen/models.py:5 | Keep | Owner-scoped state is mutable. Its version protects concurrent updates; removing it because published recipes are immutable would be incorrect. |
| Preferences — kitchen/models.py:17 | Keep | A small owner-scoped preference record. Do not build a normalized diet/exclusion taxonomy database without need. Preferences are not verified recipe dietary claims. |
| PrivatePhoto — kitchen/models.py:23 | Keep; simplify history references selectively | Current result photos can link to a completion while also duplicating its snapshot/version. For future published sessions, recipe/completion references suffice. Preserve snapshots for private editable recipes and existing history. Cover photos have no required completion, so do not globally drop snapshot fields. |
| PhotoCleanup — kitchen/models.py:42 | Keep | Storage cleanup/reservations survive failures; database deletion and object storage deletion are not one transaction. This is justified operational state. |
| CapabilityGrant — kitchen/models.py:50 | Keep for now | Explicit feature/cost limits are distinct from user Preferences. Small overlap in ownership does not justify mixing preferences and entitlements. |
| CaptureJob — kitchen/models.py:56 | Keep | Lease, attempts, retry times and preview state support asynchronous processing. `approved_ids` means user acceptance of pantry items, not team recipe approval; clarify naming in a future change if confusing. |
| JobUsage — kitchen/models.py:79 | Candidate for later consolidation | It is currently one-to-one with CaptureJob, holding state/units/time, not a multi-entry billing ledger. It could become usage fields on CaptureJob if transactional retry/accounting semantics stay intact. No need to change it for immutable recipes. |

For published content, immutability must cover admin actions, seed/import jobs,
QuerySet.update and storage assets as well as the public API. Restrict changes to
content columns after publication, ideally at the database boundary too. Mutable
availability columns may stay on the same row; a separate table is not intrinsically
required. External image URLs can change even when JSON is frozen: stable managed
asset content is needed for the same visual guarantee. Private cover changes must
never rewrite a public recipe's image.

## Permanent links and availability

`GET /api/integrations/v2/recipes/{recipe_id}` returns that recipe, never a newer one.
An inspiration link does not redirect the source recipe or remove it from search.
Both recipes may remain discoverable independently, each with its own feedback.
If removal is necessary, the old ID stays reserved and returns a clearly identified
unavailable/tombstone response. It must never return another recipe's body. This
preserves identity even when ongoing content access cannot be offered.

Reports and thumbs votes attach directly to recipe_id. A cooking session stores
recipe_id and its step progress. A report submitted from a step automatically adds
step_id. No version selection or revision vocabulary appears in the user flow.
An inspired recipe starts with zero votes and no inherited reputation. Report abuse
rules still need to prevent copying a held recipe under new IDs to evade restrictions;
no team editorial approval is implied by that requirement.

## Search and detail contract

Actual current endpoints:

- `/api/v1/starters?q=meatball&page=1`: basic title substring search, 24 results/page,
  count/page/has_next, title ordering. Source: scrape_me/api/starter.py:20 and api/urls.py.
- `/api/integrations/v1/catalogs/{catalog}/recipes?limit=24&after=0`: authenticated
  catalog listing ordered by ID; no search/filter/sort. Source: integrations/views.py:87.
- Both have integer-ID detail routes today. Production deployment is not established.

Proposed additive API:

```http
GET /api/integrations/v2/catalogs/{catalog}/recipes?q=meatballs&sort=top_rated&limit=12
GET /api/integrations/v2/recipes/{recipe_id}
```

Search cards contain recipe_id, title, nullable description/image/time/yield,
thumbs_up/thumbs_down and next_cursor at the response level. No revision ID.
Retain the proposed q, sort (relevance/top_rated/newest/quickest), limit, cursor,
optional tags/max_total_minutes/min_votes parameters. Unknown times are excluded
by a time limit and sort last for quickest. Zero feedback does not prevent listing.
Keep ranking/tie-breaks documented and page continuation stable. Both apps use the
same search service with appropriate visibility/grant filters.

Detail returns `{document, status}`: document is immutable RecipeDocumentV1;
status contains current availability and feedback counts. A held recipe returns a
consistent unavailable response, not another recipe. Refresh status before a new
session. A minimal availability change feed may be introduced for offline imports;
its events reference recipe_id only. An event sequence/cursor is delivery state,
not a recipe revision. No webhook or elaborate synchronization platform is needed
just to support initial online search/select/fetch.

## Contract simplification beyond revisions

Implemented in proposal artifacts only: remove revision objects and URN wrappers;
use UUID recipe IDs, published_at, and optional inspired_by_recipe_id. Retain
schema_version because consumers still need a known JSON format.

Further simplification candidates, not silently changed in the current schema:

- Array order already orders steps: `position` is redundant and could be removed.
  Keep local step IDs for progress/reports and ingredient IDs for references.
- Keep grouping as nullable labels rather than separate group registries unless
  nested grouping/references are demonstrably needed.
- Per-item source_refs/locators are optional enrichment; retain original text and
  recipe-level provenance without requiring extraction machinery for manual recipes.
- Detailed portion quantities, unresolved-text arrays, language, and asset digest
  metadata should not all be mandatory client authoring inputs. Server normalization
  can fill explicit nulls. Do not introduce new tables for these fields.
- Keep exact/range quantities and ambiguous original unit text only where useful;
  do not infer measurements or promise scaling when data is absent.

These are simplification recommendations for the next schema pass, not reasons to
block ordinary user-generated recipes. The current proposal remains more detailed
than the minimum MVP needs; no application migration should blindly implement it.

## Migration and checks before implementation

1. Preserve original rows/source text/provenance and private edits. Map existing public
   IDs to permanent published UUIDs, retaining old routes as aliases to the same content.
2. Freeze each published document. Reseed identical content without changes; changed
   published content becomes a new recipe. Optional inspiration records attribution.
3. Keep private edit counters, migrate source associations from URL-only matching, and
   test saving two public recipes with the same source URL without conflation.
4. Add votes/reports referencing recipe_id, with uniqueness and step-reference checks.
5. Test unchanged old links after publishing an inspired recipe; independent feedback;
   immutable writes via API/admin/seed/direct update; private notes/photo isolation;
   availability holds/tombstones; stable search pagination; and preserved cooking history.
6. Test snapshots against editable private recipes before removing any existing history
   fields. Defer job/accounting consolidation to a separate, justified change.

Proposal schema checks passed: two examples, one timer fixture, and 13 negative cases,
including rejection of the obsolete revision object. No database immutability,
feedback system, search change, migration, or publication was implemented by this review.
