# Execution status

Updated September 7, 2026. Use [the current roadmap](../ROADMAP.md) for priorities.
Older plan appendices are dated historical evidence, not a current backlog.

| Work | Current state | Evidence |
| --- | --- | --- |
| A1/A2/B1/C1/C2/B2/D1/D2 | Implemented locally | [Foundation](01-foundation.md), [imports](02-imports.md), [library](03-private-library.md), [frontend](04-frontend-alpha.md) |
| Starter catalog/media | 415 accepted recipes, 140 managed images | [Starter documentation](../../data/starter/README.md) |
| E1–E3 | Controlled catalog v1, private photos, manual pantry/preferences/matching locally implemented | [Expansion](05-expansion.md) |
| E4/E5 | Durable fixture capture and quota foundations only; live AI absent | [Expansion limits](05-expansion.md) |
| Recipe lifecycle | Immutable finalized UUID recipes, private drafts, variations, sharing/archive | [Lifecycle](06-recipe-lifecycle.md) |
| A3 + catalog v2 | Authorized September 7; release and integration work in progress | [Current release evidence](07-release-and-v2.md) |

Baseline suite rerun September 7: 78 PostgreSQL tests pass. The lifecycle increment
records 16 browser scenarios. Current increment results are recorded in its own evidence.

Finalization replaces the earlier general-purpose editable saved-recipe behavior.
StarterRecipe now provides original-source archives/legacy aliases to canonical Recipe;
source URL uniqueness no longer prevents distinct recipes with the same source.
The [root README](../../README.md) describes current setup and endpoint semantics.
