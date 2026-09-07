# FlavorGirls “Cook with me”: FlavorBuddy audit and contract proposal

**Product decision: user feedback is the source of truth for curation.** Recipes
are user- or AI-generated. There is no team editorial approval, reapproval,
kitchen-testing requirement, or prepublication quality-review queue. New recipes
can be available with no feedback yet. Ratings are thumbs up/down.

**Assessment: current payload needs technical integration work.** Stable versions,
structured references, feedback and withdrawal support are still missing. Lack of
editorial approval is not a blocker or a requirement. Format validation determines
whether software can consume a recipe; community feedback determines its reputation.

This is an audit of the current **uncommitted working tree and local PostgreSQL
16.11 data**, after implementation was paused at the user's instruction. It does
not describe a released service. This audit changed only files in this audit folder;
no application behavior, database content, grants, recipes or either app was changed.
No paid extraction, publishing, cloud provisioning or outreach occurred. Database
inspection used a repeatable-read, read-only transaction, not API calls that could
write usage/audit records. The database has 415 StarterRecipe rows and **zero Recipe
rows**, so there is no honest live private-recipe example to show from this database.

## Current-state findings

| Area | Actual current behavior | Implication for FlavorGirls |
| --- | --- | --- |
| Private recipe model | `scrape_me/models.py:11`: integer primary key, title/author/description, free-text yield, nullable total minutes, ingredient/instruction JSON, owner, notes/favorite, mutable version | IDs are stable within this database, not a portable identity/revision contract. JSONFields alone do not constrain their internal shapes. |
| Save validation | `scrape_me/api/serializers.py:32` and `:53`: nonempty title/ingredient list/instruction list; strict nonblank item strings; 200 entries each, ingredient 2,000 and instruction 10,000 characters; title/yield/author 255; total_time 0–100000 or null | Basic saved-recipe structure only. No quantities, references, equipment, timers, dietary validation, completeness or culinary correctness checks. |
| Unknowns | Empty strings for description/author/yield/image; null for missing total_time; source_url may be null/empty | Unknown representations are inconsistent. An empty total time is not zero; do not convert unknown yield to one serving. |
| Preview/import | `scrape_me/services/extraction.py:11`: previews may be empty; URL extraction uses safe fetch + scraper; only known serializer fields survive | Imported equipment/structured step data is not retained as first-class data. A “ready” preview means extraction finished, not safe/complete cooking instructions. |
| Instruction normalization | `scrape_me/views.py:17`: strings split on newlines; iterable strings retained; nonstring entries skipped | Not semantic action splitting. A list of HowToStep objects passed directly to this helper would be dropped; do not assume support for every structured upstream form. |
| Text extraction | `scrape_me/services/ai_extraction.py:59`, prompt in `scrape_me/prompts/raw-text-system-prompt.md` | AI is explicitly gated/metered. Prompt prohibits invention, but output validation proves only types/limits. No paid call was made for this audit. |
| Manual editing | `frontend/src/components/Editor.tsx:30` and `:199`: multiline fields split by newline, then trim/filter blank entries | “One step per line” is a UI convention, not one action, stable step identity or ingredient-reference enforcement. |
| Revision handling | `scrape_me/api/views.py:106`: PATCH checks version then increments it, including notes/favorites | Current version is optimistic concurrency, not immutable content. There is no historical document lookup; notes/favorites may change version without recipe content changing. |
| Cooking | `frontend/src/features/cooking/Cook.tsx:7`, `:23`, `:155`: array indexes, account/recipe-local progress, one user-set timer; `scrape_me/api/views.py:229` records completion | Progress is not revision-bound; edits can shift indexes. The timer is not recipe/step data and implies no completion guarantee. |
| Completion/photo history | `scrape_me/models.py:102`, `kitchen/models.py`: new completion snapshots retain title/ingredients/instructions + version for result photos | Helpful partial history, not a full immutable recipe/provenance document. Legacy completions may have no snapshot. |
| Starters | `scrape_me/models.py:112`: unique slug, title, JSON content/provenance, original Markdown | No content revision, publication state, approval or moderation field. Slugs can be reseeded/edited. |
| Starter ingestion | `scripts/build_starter_catalog.py:35`, `:87`, `:106`; `seed_starter_recipes.py:25` | Builder flattens groups into string prefixes, leaves total_time null, preserves timing text in notes and source Markdown. Seeding validates save shape plus Unlicense/nonempty source revision, then updates rows in place. |
| Public/private boundary | `scrape_me/api/starter.py:11`, `:49` | Public reads serialize starter JSON directly; saving creates an independent owned copy by source URL. Repeat save preserves private edits. No automatic private-to-public synchronization. |
| Existing exports/API | `scrape_me/api/views.py:130`, `integrations/views.py:87` | Private export has container `schema_version: 1`. App v1 API reuses current starter serialization, with `limit`/`after` pagination. Neither is RecipeDocumentV1. |
| Catalog permission | `integrations/models.py`, `integrations/auth.py` | Catalog membership and OAuth grants are access controls. They are not editorial approval, safety review or per-revision withdrawal. Disabling an app catalog does not withdraw the separate public starter endpoint. |
| Ratings/reports | No matching recipe Rating, Report, EditorialReview, ModerationCase or Publication model/API/UI exists | Favorite, view count and cooking completion are not thumbs up/down feedback. CaptureJob `approved` means approving pantry items, unrelated to recipe approval. |

A nonpersisted validation probe accepted title “Recipe-shaped text,” ingredient
“Salt,” and instruction “Enjoy.” Extra `equipment` and `schema_version` input keys
were silently dropped. This demonstrates why passing today's serializer is not
sufficient for FlavorGirls. Model/admin/direct database writes also need not go
through that serializer. Public starter reads do not revalidate on response.

## Representative current JSON from existing records

These are actual public starter values, not a proposed shape. Full unabridged
responses for Coconut Oil Coffee, Fried Potatoes, Irish Coffee, Apple Pie and
Lemon juice salad dressing are in [current-starter-examples.json](current-starter-examples.json).
This compact excerpt preserves all shown values:

```json
{
  "id": 150,
  "slug": "fried-potatoes",
  "title": "Fried Potatoes",
  "yields": "",
  "total_time": null,
  "ingredients": ["Potatoes", "Oil or Crème Fraîche", "Onions"],
  "instructions": [
    "Peel and cut the potatoes to desired size.",
    "Cut the onions.",
    "Put a bit of Oil or Crème Fraîche in your pan.",
    "Put both the potatoes and the onions into the pan.",
    "Cook them until they're golden-brown.",
    "Enjoy"
  ]
}
```

The first string already contains two actions. “Oil or Crème Fraîche” is an
unresolved alternative, not a parsed ingredient with a trustworthy amount.

Actual Irish Coffee has `yields: "1"`, `total_time: null`, and source notes
`"⏲️ Prep time: 5 min\n\n🍳 Cook time: 5 min"`. Its **one** instruction string is:

> In a coffee mug, combine Irish cream and Irish whiskey. Fill mug with coffee. Top with a dab of whipped cream and a dash of nutmeg.

That single UI step contains combine/fill/top actions. Do not infer a ten-minute
total by summing source fields; overlap and source meaning were not reviewed.

A concrete ingredient-consistency gap: **Lemon juice salad dressing, ID 210**, lists
lemon juice, olive oil and garlic, while step 2 says “Add salt and pepper to taste.”
Salt and pepper are absent from its ingredient list. It passes the current save
validator. This is an audit observation on one record, not a quantified full-catalog
culinary defect rate. Do not quietly add them during a lossless structural migration.

## Quantified full-catalog audit

Input: all 415 local starter records, matching the pinned source collection revision
`da84378b36bd5b2e3cb35f610d64630bf1bd899d`. The canonicalized audit-input checksum,
row-level gaps, exact regex methods and candidate texts are saved alongside this
report. Checks did not fetch external source pages or test recipes in a kitchen.

| Check | Count / result |
| --- | --- |
| Pass current save serializer | **415/415** |
| Missing/empty/non-array ingredient lists | **0/415** |
| Malformed/blank ingredient entries | **0/3,323** |
| Ingredient entries stored only as strings | **3,323/3,323**, across **415/415** recipes |
| Missing/empty/non-array instruction lists | **0/415** |
| Malformed/blank instruction entries | **0/3,038** |
| Instruction entries stored only as strings | **3,038/3,038**, across **415/415** recipes |
| Unknown normalized yield | **164/415 (39.5%)**; remaining **251** have free text |
| Wrong-type/over-limit normalized yield | **0**; this does not validate serving semantics |
| Unknown normalized total_time | **415/415 (100%)**; wrong-type/out-of-range nonnull values **0** |
| Source notes with a timing label | **291/415** |
| Source notes with numeric duration text | **289/415** |
| Source Markdown with numeric duration text | **357/415** |
| Steps containing numeric-duration text | **599/3,038**, across **289** recipes; no structured timer definitions |
| Unknown yield but numeric yield-like source text | **12** review candidates; e.g. Baba's Feta Pasta says “Serves Around 3 People” |
| Required provenance strings missing, malformed URL/revision, source hash mismatches | **0** for each tested category |
| Original source Markdown retained and hash-verified | **415/415** |
| Model/content title mismatch or source URL mismatch | **0** |
| Nonimage content differences from seed snapshot | **0**; **140** records differ only by migrated image URL |
| Usable image URL / no image URL | **140 / 275**; all 140 have managed image metadata |
| Explicit ingredient group prefixes recoverable by heading match | **197** entries across **14** recipes; no structured group IDs |
| Two-or-more-action-word candidate steps | **1,185/3,038**, across **370/415** recipes |
| Multiple-sentence candidate instruction strings | **890/3,038** |
| Distinct source tag strings | **180**, with no controlled application taxonomy |
| Stable ingredient IDs, stable step IDs, equipment arrays, ingredient/step references, timer definitions | **0** structured occurrences in the current catalog shape |
| Recorded feedback/moderation state | **No supporting model/records**; editorial approval is intentionally not required |

The action-word count is a deterministic **screening heuristic**, not an exact count
of all multi-action steps or flawed recipes: it matches at least two distinct verbs
from an explicit vocabulary. It can overcount negated/adjectival words and miss
synonyms/implicit actions (Irish Coffee demonstrates this). All 1,185 candidate
strings and matched words are in [multi-action-candidates.json](multi-action-candidates.json).
The original group-prefix check is conservative. Yield-recovery candidates retain
the matching source lines; they were not written back. Missing normalized values
must not be described as missing from the source when source text survives.

## Current contract and schema review

The earlier revision-based proposal has been superseded by the user's immutable
published-recipe model. A published recipe has one ID and one permanent link.
A correction is a new recipe with a new ID; no revision table or revision URL exists.

See [SCHEMA-REVIEW.md](SCHEMA-REVIEW.md) for the current model/table review,
search/detail contract, migration checks and remaining decisions. The linked
[RecipeDocumentV1 schema](RecipeDocumentV1.schema.json),
[example](RecipeDocumentV1.example.json), and
[migration example](RecipeDocumentV1.migration-example.json) now follow that rule.
`schema_version` describes the JSON format, not an edit of a recipe.
Source repository revisions remain provenance, not recipe revisions.

The structured and migration examples are now two distinct proposed recipes.
The enriched example links to its source recipe through optional inspired_by_recipe_id.
They do not create any application records or assert recipe quality.

Proposal-only validation passes two examples, a timer fixture and 13 rejection
cases; see [proposal-validation.json](proposal-validation.json). These checks do
not prove database immutability or implement any proposed runtime behavior.
