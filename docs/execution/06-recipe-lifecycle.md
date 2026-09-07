# Drafts, immutable recipes, and visibility

Implemented locally September 6–7, 2026. This supersedes earlier proposals for
editable private recipes and separate immutable recipe revisions.

## Product behavior

One Recipe model holds private and public recipes. `state` is draft/finalized;
`visibility` is private/public. Drafts are always private and can be incomplete.
Save draft keeps editing available. Save recipe finalizes and locks content.
Sharing a finalized recipe changes visibility, retaining its UUID and content.
Make a variation creates a new private draft with a new UUID and `inspired_by` link.
Notes, favorites, cooking progress and private photos remain personal mutable data.
There is no editorial approval, public recipe revision, or automatic public sharing.

Finalized recipes are archived rather than hard-deleted. Public archived links
return 410, never replacement content. Making a recipe private restricts access
again; the owner can still open the same UUID link. Previously downloaded public
content cannot be recalled by making the original private.

## Implemented schema and API

Migration `scrape_me.0010_recipe_lifecycle` adds public_id, state, visibility,
finalized_at, archived_at, inspired_by and original-source storage to Recipe. The
internal integer primary key remains for existing application routes. `version`
remains a save-conflict counter, not recipe content history. Source URL uniqueness
is removed because separate recipes can share the same source.

PostgreSQL checks enforce lifecycle states and prevent self-inspiration. A trigger
rejects finalized content/identity changes and hard deletion, including bulk SQL
updates. The API and model also reject changes and require valid ingredients/title/
instructions for finalization. Personal fields and visibility remain writable.

Existing StarterRecipe rows are retained as original-source archives and legacy
URL/catalog aliases pointing to canonical Recipe records. They are not a separate
editable kind of public recipe. Public reads use canonical content and visibility;
unmapped aliases are not served. All new private/public recipes use Recipe.

Session/CSRF APIs:

- POST /api/v1/recipes with state draft (default) or finalized; initially private.
- PATCH /api/v1/recipes/{id}: content only while draft; notes/favorite after finalization.
- POST /api/v1/recipes/{id}/finalize with version.
- POST /api/v1/recipes/{id}/visibility with version and private/public.
- POST /api/v1/recipes/{id}/variations: owned or accessible public finalized source.
- GET /api/v1/shared-recipes?q=…&page=…: public finalized recipes, 24/page.
- GET /api/v1/shared-recipes/{public_id}: permanent content link, owner access if private.

Public responses exclude notes, favorites, owner identity and private photos.
The old starter and integration v1 routes retain integer aliases. V1 app grants
still grant explicit starter catalog membership; sharing publicly does not silently
extend those grants. Integration v2, richer structured ingredients/steps, votes,
reports and AI generation are separate proposed work, not implemented by this change.

## Data preservation and migration evidence

Before applying migration locally, a mode-0600 PostgreSQL custom-format backup was
saved outside the repository at `/tmp/flavorbuddy-before-lifecycle-20260907-033303.dump`.
A corresponding JSON snapshot records all original starter fields.

Migration applied successfully to the local PostgreSQL database. It mapped 415
existing public starters to 415 finalized/public Recipe rows with unique UUIDs.
The local database had zero private Recipe rows before migration. Every original
starter content field, provenance field, source Markdown and alias ID was compared
with the backup snapshot. Original source notes are retained as source provenance,
not exposed as a user's private notes. Repeat seeding reports 0 new rows and cannot
overwrite changed content at an existing slug. Managed images must be prepared
before finalization; the image command will not rewrite finalized recipe content.

A separate migration rehearsal tests pre-existing private content, notes/favorites,
edit counters, incomplete drafts, ownerless rows and public starter aliases. Complete
legacy recipes finalize privately; incomplete records remain private drafts;
ownerless records are not made public. Deferred FK checks are flushed before the
post-backfill ALTER TABLE operations so populated PostgreSQL migrations succeed.

Rollback after users create new data requires an explicit data-preserving procedure
or restoration into a separate database from backup. Do not blindly reverse source
URL uniqueness or downgrade and lose lifecycle metadata. No cloud deployment or
production migration was performed.

Validation: 78 PostgreSQL tests (including populated migration rehearsal), 16
Playwright desktop/mobile scenarios, TypeScript/Vite build and Django system checks.
Browser tests use a disposable database and fake/local extraction fixtures. No paid
AI call, public deployment, or new recipe publication was performed on the real
local catalog; migration preserved the existing public starter collection.
