# Plan 3: Add private accounts and a usable recipe API

**Outcome:** People can securely save, edit, search, and export their own recipes.  
**Change sets:** C1, C2  
**Dependencies:** A1; coordinate schema and API contracts with B1/B2.

## C1: Identity and minimal ownership model

Use Django's existing user model and same-origin session authentication for the first alpha. Avoid replacing the user model merely for future flexibility. Put optional profile/preferences in a separate entity. Email-based login, verification, and recovery should use an established maintained account package or carefully reviewed Django flows; choose the package/version during implementation.

Implement registration, login, logout, current-account retrieval, verification/recovery as required for the selected onboarding, and throttling of login/reset attempts. Keep CSRF enforcement for all session-authenticated mutations, including login; remove blanket exemptions from migrated customer routes. Do not store session credentials in browser local storage.

### Minimal recipe schema

For alpha, evolve the existing `Recipe` rather than building the entire long-term roadmap schema at once:

- Add nullable owner initially for migration compatibility.
- Remove global uniqueness from `source_url`; different users may save the same URL.
- Add a uniqueness rule on `(owner, source_url)` when both are present, if alpha chooses one saved copy per source per user.
- Permit multiple manually entered recipes with no source URL.
- Keep personal notes and favorite state on the owned record initially.
- Add import provenance and an optional source metadata reference only when B2 requires it.
- Preserve ingredients/instructions JSON for alpha; structured ingredient tables belong to the planning/grocery milestone.

This intentionally narrows the comprehensive roadmap's source/saved-recipe separation: copies are independent from the beginning, while a shared `RecipeSource` table can be added before shared caching or source-refresh workflows. No user edits may be stored in a globally shared source cache.

### Migration sequence

1. Inspect whether an actual deployed database exists and back it up before production migration.
2. Add ownership/notes/favorite fields through additive migrations.
3. Update every customer queryset to require the authenticated owner. Existing ownerless rows remain staff-only; never assign them to the first registered user.
4. Replace global source uniqueness with the chosen owner-scoped constraint in a migration that checks existing data first.
5. Keep legacy IDs and content intact. Staff can explicitly assign/import legacy content through a controlled migration or admin action later.
6. Test forwards migration with representative legacy rows. Rollback must account for multiple users now sharing one source URL; blindly reinstating global uniqueness is not safe.

### Files to touch

- `config/settings.py` and `config/urls.py` for account/API dependencies and routes.
- New account/profile module or app with a narrow identity responsibility.
- `scrape_me/models.py`, new migrations, and `scrape_me/admin.py`.
- `scrape_me/api/` for serializers, permissions, and routes.
- Legacy `scrape_me/views.py` and `scrape_me/urls.py` to close alternate access paths.

## C2: Recipe API

| Method/path | Behavior |
| --- | --- |
| `GET /api/v1/me` | Current authenticated account and minimal preferences. |
| `GET /api/v1/recipes` | Owned, paginated recipes; title search, favorites filter, deterministic ordering. |
| `POST /api/v1/recipes` | Validated manual content or an owned import draft plus reviewed edits. |
| `GET /api/v1/recipes/{id}` | Owned recipe detail; no import view-counter side effect. |
| `PATCH /api/v1/recipes/{id}` | Validated edits, notes, favorite state. |
| `DELETE /api/v1/recipes/{id}` | Defined deletion behavior; confirmation/undo strategy matches the UI. |
| `GET /api/v1/recipes/export` | Export owned recipes as structured JSON with source attribution. |

Authenticate before selecting data. Apply ownership on reads, updates, deletes, search, exports, import drafts, and any related collection entries. Return 404 for another user's resource where appropriate, so IDs do not reveal existence. Staff administration is an explicit separate permission path.

Use `created_at`/ID tie-breaking for stable pagination. Do not allow client-supplied owner fields. Document whether PATCH updates nested ingredient/instruction arrays by replacement for alpha. Consider an optimistic version/updated-time precondition to prevent silent lost edits; return 409 for conflicts and preserve the user's draft.

### Legacy endpoints

`/get-recipes` and `/parse-recipe-url` must not remain an anonymous alternate route into the private model. During local compatibility, require authentication and apply ownership consistently, or make them staff/development-only. Retire `/test-example` from production routing. Document transition behavior and update the existing homepage or replace it; do not leave a broken public form pointing to protected legacy writes.

## Acceptance tests

Create Alice and Bob and verify:

- Both can import the same source URL and edit independently.
- Neither can read/update/delete/export the other's content, notes, drafts, or collection memberships.
- Anonymous access to private resources fails predictably.
- Malicious owner fields are rejected or ignored; ownership is assigned server-side.
- Search and pagination contain only owned records, including empty results and invalid page parameters.
- Session mutations require CSRF; logout invalidates access; reset tokens cannot be reused.
- Legacy unowned rows remain staff-only and retain original content after migration.
- Export round-trips the documented fields without leaking internal tokens/provider metadata.
- Concurrent edits produce documented conflict behavior rather than silent data loss when versioning is enabled.

## Completion and rollout

C1 completes when account/ownership migrations and two-user isolation tests pass on PostgreSQL. C2 completes when the complete API contract works with real sessions and documented examples. Roll out additive schema changes first, then permission-scoped code, before inviting users to save private content.

Household sharing, social login breadth, advanced preferences, public discovery, and subscription entitlements are later work. The initial API must nevertheless make adding a household authorization boundary possible without treating every recipe as public.

## Implementation evidence — September 6, 2026

Owner: Codex; uncommitted implementation for review.

**C1/C2 implemented and validated on PostgreSQL.** Existing Django User is retained;
normalized email is its unique username. Registration/login/logout/me, password
validators and SMTP-gated Django-token recovery use session cookies and CSRF even
on anonymous login/register mutations. PostgreSQL counters throttle identity and
address attempts. Email verification is not offered in this local alpha; configure
and test SMTP before exposing recovery or inviting users. No email was sent live.

Migration 0006 preserves legacy IDs/content with nullable owner, removes global URL
uniqueness, and adds per-owner source uniqueness, notes, favorites, and version.
Migration 0007 adds idempotent self-reported cooking completions. A migration test
creates a legacy row at 0005 and verifies its content/owner after migrating forward.
Ownerless data is staff-admin-only. Legacy APIs return 410; `/test-example` is absent.

Versioned APIs implement owned create/read/update/delete, bounded title search and
favorites/pagination, structured JSON export, drafts and cooking completion/notes.
PATCH replaces supplied arrays and requires `version`; concurrent/stale edits
return 409. Server assigns ownership and ignores submitted owner fields. Foreign
IDs return 404. Deletes are permanent and confirmed by the UI. Recipe exports
exclude raw import input, quota counters, provider IDs, passwords and other users.

Evidence is in `scrape_me/test_alpha.py`: two-user API isolation (including search,
export, drafts and completion), independent same-source copies, multiple manual
recipes, CSRF, logout, single-use reset token, input validation, optimistic conflict,
concurrent saves, and legacy migration. Real browser sessions verify a second
account cannot view the first account's recipe and expired sessions preserve edits.

Remaining release limitations: no email verification, account-deletion UI, household
sharing, collections or transactional email delivery evaluation. SMTP and ingress
address handling must be validated on the selected staging host. Database-backed
identity throttles use REMOTE_ADDR, never client-supplied forwarded addresses.
