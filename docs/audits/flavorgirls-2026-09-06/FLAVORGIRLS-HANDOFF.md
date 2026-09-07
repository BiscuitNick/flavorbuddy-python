# FlavorBuddy → FlavorGirls: simplified integration handoff

## Current implemented subset — September 7

Read-only v2 search and UUID detail are implemented. See the authoritative
[OpenAPI contract](../../api/catalog-v2.openapi.json) and
[release evidence](../../execution/07-release-and-v2.md).

Supported: phrase q across title/description/ingredient source text, relevance/newest/
quickest, limit/cursor, max_total_minutes, stable recipe-scoped ingredient/step IDs,
source-preserving RecipeDocumentV1 and unavailable responses. Unsupported parameters
are rejected. Feedback is null; tags, rating sorts, votes/reports and generation below
remain proposals. Schema validation does not infer ingredient quantities or cooking facts.

Obtain catalog:read tokens at `/api/integrations/v1/oauth/token` with the exact v2
resource audience (`<PROJECT_URL>/api/integrations/v2/`). V1 tokens stay v1-only;
registered applications share the same grants and quotas across versions. Protected
staging also requires Google IAM invocation authentication in `X-Serverless-Authorization`;
keep the app OAuth token in `Authorization`.
Search and detail only expose explicit licensed-starter catalog membership.
The real FlavorGirls server has not been configured or contacted by this implementation.

The remaining sections describe the broader future contract. Implement only the
supported subset above until another increment is authorized.

## Recipe identity and curation

- One finalized recipe = one immutable recipe ID and permanent link, whether private or public. Drafts remain editable and private. Sharing changes visibility only.
- No revision IDs, revision tables, or latest-version endpoints.
- Changes create a new recipe with its own ID, votes, and reports.
- Optional provenance.inspired_by_recipe_id links to another recipe without
  replacing it, redirecting its link, or inheriting its feedback.
- schema_version identifies the JSON format, not a recipe revision.
- Users curate through thumbs up/down and reports. No team editorial approval.
- New recipes can be available with zero feedback.
- Availability and feedback can change; recipe content cannot.

## Search → choose → cook

GET /api/integrations/v2/catalogs/{catalog}/recipes?q=meatballs&sort=relevance&limit=12
Authorization: Bearer <app token>

Proposed parameters:
- q: optional text, up to 200 characters; title/description/ingredients/tags.
- sort: relevance, top_rated, newest, quickest.
  Default relevance with q; newest without q.
- limit: default 24, maximum 100.
- cursor: opaque continuation token; keep the other parameters unchanged.
- tags: optional comma-separated controlled tags, all must match.
- max_total_minutes: optional positive integer; unknown times excluded.
- min_votes: optional nonnegative integer, default 0.

Top-rated uses thumbs feedback with vote-count confidence, not raw percentage
alone; finalize the formula before implementation. Unrated recipes remain
available. Quickest puts unknown times last. Use stable tie-breaks/pagination;
reject unsupported parameters rather than silently ignoring them.

Illustrative response shape (placeholder IDs, not actual records):

```json
{
  "results": [{
    "recipe_id": "<uuid>",
    "title": "Meatballs in Tomato Sauce",
    "description": null,
    "image_url": null,
    "yield_text": null,
    "total_minutes": null,
    "feedback": {"thumbs_up": 42, "thumbs_down": 3}
  }],
  "next_cursor": null
}
```

Show these as recipe cards. The user selects one; then fetch:

GET /api/integrations/v2/recipes/{recipe_id}

Return {document, status}. document is the validated RecipeDocumentV1 with UUID
recipe_id, schema_version, finalized_at, title/description/yield, provenance,
structured ingredients, ordered steps, equipment, optional timers/images/tags.
Unknown fields remain null. Step/ingredient IDs are local reference IDs, not
revisions. status contains current availability and thumbs counts.

The session stores recipe_id and step progress. The same link always identifies
the same recipe. An unavailable recipe returns an explicit unavailable/tombstone
response, never another recipe's content. Check availability before starting;
existing imported sessions can refresh status or consume a later change feed.
No team approval is part of this process.

## Optional AI generation — new capability to implement

POST /api/integrations/v2/recipe-generations
Authorization: Bearer <token with recipes:generate>
Idempotency-Key: <uuid>

```json
{
  "prompt": "Create an Italian-style meatball recipe",
  "constraints": {
    "servings": 4,
    "max_total_minutes": 45,
    "include_ingredients": ["ground beef"],
    "exclude_ingredients": []
  },
  "inspired_by_recipe_id": null
}
```

Only prompt is required. Constraints are optional; omit unknown preferences.
An inspiration ID must identify a recipe this caller can access. It supplies
context for a NEW recipe; it never mutates the original. Conflicting/unsupported
constraints should return an actionable error rather than silently be discarded.
Requested dietary constraints are not a verified allergen-safety certification.

Return 202 with generation_id, status and polling URL:
GET /api/integrations/v2/recipe-generations/{generation_id}

States: queued, running, succeeded, failed.
Success returns recipe_id; failure returns a stable error code and message.
The generation ID tracks asynchronous work, not recipe versions.
On success, store one editable private draft with a new UUID,
AI origin metadata and optional inspiration link. Fetch the draft through an owner-authorized draft endpoint. Let the user edit it, then finalize to lock its content before cooking. The UUID stays the same when finalized or shared.

Recommended initial visibility: restricted to the generating app/user context;
generation does not automatically add the result to a public catalog. Public
sharing is a separate explicit action, not team editorial approval. Finalize
whether app-level or delegated user-level ownership is required before building.
Any app-only credential acts as the app and must not impersonate a human user.
A later content change generates a new recipe, while sharing only changes visibility.

Generation authors new content intentionally; imported-source extraction must
still preserve unknowns rather than invent source facts. Neither format validation
nor AI generation establishes culinary correctness. User feedback remains curation.

Use a separate generation grant, request/concurrency/spend limits, and idempotency.
The same key/body must return the same job; changed input with that key returns 409.
Timeouts should resume/poll the existing job, not initiate duplicate paid requests.
Keep credentials and AI provider calls on the backend. No paid fallback from a
search with zero results: generation must be an explicit user action.

## Feedback and implementation boundaries

Thumbs votes attach to recipe_id. Reports attach to recipe_id plus optional step_id,
automatically captured from the cooking screen. Categories: inappropriate content,
seriously flawed recipe, potentially unsafe instructions, other.
Write endpoints require a separate feedback identity/permission design; current
catalog:read credentials cannot write votes/reports or generate recipes.

FlavorBuddy and FlavorGirls should share backend search semantics while enforcing
visibility/grants before pagination. The public catalog must not expose private
copies or app-restricted generations. Open decisions: vote ranking formula,
report-driven hiding/restoration policy, generation visibility/identity and budgets,
and availability freshness. No editorial workflow or recipe revision model is needed.
