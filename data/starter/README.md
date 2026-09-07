# Public Domain Recipes starter catalog

Requested target: **500**. The selected upstream revision contains **415** recipe
Markdown files (plus the site index); all 415 pass the FlavorBuddy save schema.
The user accepted 415 as the final collection size; the original 500 target remains
in the manifest as historical provenance. No supplemental source or padding is needed. Schema validation is not individual culinary review.

Source: https://github.com/ronaldl29/public-domain-recipes
Revision: `da84378b36bd5b2e3cb35f610d64630bf1bd899d`
License: Unlicense; upstream README explicitly dedicates recipe text and images to
the public domain. The repository license is retained in LICENSE.md. Each record
retains the author, source URL, revision, source path, original Markdown, and SHA256.

Rebuild from a local checkout without running upstream code:

```bash
.venv/bin/python scripts/build_starter_catalog.py /path/to/public-domain-recipes --limit 500
.venv/bin/python manage.py seed_starter_recipes
```

The build report includes target, availability, valid/selected counts and skips.
Ingredients keep section labels (e.g. Filling/Crust); source timing and supplementary
text are preserved in notes. Unknown total time stays null rather than inferring a
sum from overlapping prep/cook/rest times. Images reference the original public
website, with the existing missing-image fallback when unavailable.

StarterRecipe is explicitly public and separate from Recipe. Seeding upserts only
starter records by slug. Saving creates an owner-scoped independent Recipe with
read-only provenance metadata; repeated saves return the existing private copy
without replacing edits. Private and legacy ownerless rows never appear in the
starter catalog. This is a pinned snapshot, not an automatic upstream synchronizer.

Image coverage: 142 recipes have source image URLs; 273 have no image URL. The app
stores URL references, loads images directly from the source with lazy loading, and
shows the leaf illustration for missing or failed images. No managed image storage
or image proxy has been configured.

Live image verification (2026-09-06 22:45 UTC): 140 of 142 URLs returned images
that successfully decoded. Banana and oatmeal cookies and Tzatziki returned HTTP
200 with text/html rather than image data, confirmed on a second attempt. Detailed
results are in ../../docs/operations/starter-image-audit.json. Image files were
checked in memory and were not added to application storage.

The two broken image references were removed at the user’s request. The catalog
now has 140 image URLs and 275 recipes with intentional fallbacks. Rebuilds consult
excluded-image-urls.json so the known-broken URLs are not reintroduced. The original
source Markdown and historical audit remain intact for provenance.
