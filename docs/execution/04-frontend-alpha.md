# Plan 4: Ship a compelling import-to-cooking experience

**Outcome:** A target user can save and cook a recipe independently on a phone, and the product feels worth returning to.  
**Change sets:** D1, D2  
**Dependencies:** D1 can begin with local samples; D2 requires the C2 recipe API and B2 import contract.

## Scope and structure

Create the frontend in `frontend/` inside this repository initially, using React, TypeScript, and Vite. This keeps deployment and API integration reviewable without prematurely splitting repositories. Use accessible UI primitives and a custom design system. Verify selected dependencies and build commands when scaffolding.

Keep account/authentication and business validation on Django. Route browser calls through the same origin in production; configure a development proxy to Django instead of introducing a broad CORS policy. Account forms and API calls must participate in Django's CSRF/session flow.

Suggested structure:

```text
frontend/
  src/
    app/                  routing and authenticated application shell
    components/           reusable accessible interface components
    features/auth/        login, registration, recovery
    features/import/      input, progress, preview, correction, save
    features/library/     recipe grid/list, search, detail, editing
    features/cooking/     step view, ingredient checkoffs, timers
    lib/api/              typed API client and error mapping
    styles/               tokens and global typography
```

## D1: Visual system and tested prototype

1. Define warm ivory surfaces, olive text, and a tomato action color with verified contrast. Select typefaces and fallbacks with clear licensing/loading behavior.
2. Establish spacing, radii, image ratios, focus rings, button hierarchy, dialogs, inputs, skeletons, errors, and empty states.
3. Build a mobile-first shell with Recipe box, Add recipe, and account access. Do not show nonfunctional Week/Groceries tabs.
4. Design recipe cards with title, real image or intentional fallback, time when known, source, and favorite state. Avoid fabricating unknown timing or dietary labels.
5. Prototype input → editable preview → saved recipe → cooking using representative local samples with long titles, no image, many ingredients, and incomplete content.
6. Observe five target users completing these tasks and correct the biggest comprehension failures before polishing secondary surfaces.

**D1 completion:** Core screens and states exist, mobile/keyboard use works, and observed prototype feedback is documented. Sample-backed screens are explicitly not a working product release.

## D2: Real API integration

### Import and preview

- Offer URL and pasted-text modes; preserve the input across errors and authentication.
- Show status such as fetching, extracting, or ready only when supported by actual API state; no fictional percentage progress.
- Present extracted title, servings, time, ingredients, and directions with clear inline correction.
- Show source attribution, missing-field warnings, and a primary Save recipe action.
- Prevent double saves and recover safely from an uncertain response using the import identifier.
- An unsupported source offers pasted text/manual correction instead of a dead-end error.
- Do not make anonymous paid import a dependency for alpha. If account gating is required, show a useful local sample before signup and explain why saving needs an account.

### Recipe box and detail

- Add fast title search, empty/search-empty states, favorites, loading, pagination, and a useful grid/list switch if it fits the scope.
- Fetch by stable recipe ID; browser refresh and back navigation must work.
- Keep detail actions clear: Cook, Edit, Favorite, and secondary Delete/Export access.
- Display source content and personal notes distinctly. Preserve form edits during recoverable errors.
- Confirm deletion clearly or implement recoverable trash/undo consistently with the API. Do not display an undo toast unless the backend can actually restore the record.

### Cook mode

- Use large readable steps with the ingredient list accessible without losing position.
- Support ingredient checkoffs, previous/next steps, and a clear return to recipe detail.
- Add explicit user-created timers first; automatic time extraction is optional.
- Persist progress locally per user/recipe and clear or partition it correctly at logout/account switch.
- Use screen-awake support where available; do not promise that the browser will always keep the screen awake or fire background timer notifications.
- Let users mark cooking complete and save a brief note through a defined backend field/event. Use completion as a product measurement, not a claim of verified cooking.

### States to implement deliberately

| State | Required behavior |
| --- | --- |
| First visit | Explain the product briefly and provide a clear first import/sample action. |
| Empty library | One primary add action and a useful example. |
| Slow import | Honest activity indication and preserved input. |
| Unsupported source | Pasted-text/manual continuation. |
| Quota exhausted | Clear explanation; existing recipes remain usable. |
| Session expired | Reauthenticate without losing the current draft. |
| Network failure | Retry and preserved editing state. |
| Edit conflict | Retain local edits and offer review/reload. |
| Missing image | Intentional visual fallback, not a broken image icon. |
| Another user's/missing ID | Neutral not-found experience. |

## Quality and validation

- Test at 360-pixel mobile, tablet, and desktop widths with no horizontal overflow.
- Keyboard users can import, edit, save, navigate steps, and exit dialogs; focus returns appropriately.
- Labels and validation errors are associated with inputs; status changes are announced without excessive screen-reader interruption.
- Respect reduced motion and verify contrast using actual final colors.
- Optimize images and layout stability; avoid loading full-size source images in every grid card.
- If introducing an image proxy, use the safe-fetching boundary from B1 rather than creating a new arbitrary URL fetch endpoint.
- Run end-to-end tests against Django for login → import → correction → save → search → edit → cook, plus failure recovery.
- Include a second account to verify cached UI data and local progress do not cross account boundaries.
- Validate production routing, CSRF behavior, static assets, and page refresh on staging.

## Pilot and next investment decision

Invite the recruited cohort after A3 and record whether users save and cook without assistance. Ask for feedback after actual use, not just a first visual impression. Observe import failures, time to first saved recipe, abandoned edits, first cooked recipe, and repeated use over several weeks.

The next product investment is a simple weekly plan and reviewed grocery consolidation if users repeatedly cook saved recipes and express planning friction. If users cannot reliably import or find recipes, fix those failures first. Pricing experiments follow demonstrated recurring value; do not add checkout just to label the alpha monetized.

**D2 completion:** The real complete flow works on staging, critical usability issues are resolved, and remaining limitations are explicit. Full offline synchronization, household collaboration, and native share extensions remain separate milestones.

## Implementation evidence — September 6, 2026

Owner: Codex; uncommitted implementation for review.

**D1/D2 implementation works locally against real Django/PostgreSQL APIs.** React,
TypeScript and Vite are built under `frontend/` and served same-origin by Django /
WhiteNoise. Warm ivory/olive/tomato tokens, bundled OFL fonts, responsive recipe
cards, source images with intentional missing-image states, visible focus styles,
accessible native controls and reduced-motion rules are implemented. Hash routes
support refresh/back for stable recipe IDs.

The working flow includes account/sample onboarding; URL, text and manual imports;
review/edit/save; source attribution; title search, favorites, pagination, export;
recipe detail/edit/delete; cooking steps, ingredient checkoffs, explicit timers,
best-effort wake-lock, and persisted completion/notes. No fake Week/Groceries tabs.
Drafts, base versions, notes and cooking progress are partitioned by account on the
device. Session expiry presents login and restores the draft. Version conflicts
preserve edits and offer the latest saved content for comparison. Network and source
failures offer retry/manual correction. No unsupported background timer/offline-sync
claims are made.

**Validation:** production TypeScript/Vite build passes. **8 Playwright scenarios
pass** (four workflows each on desktop Chromium and 360px mobile Chromium):

1. Real session + URL fixture extraction → correction → save → favorite/search →
   edit → cooking/progress refresh → completion note, followed by account isolation.
2. Unsupported source → manual correction and failed-network-save recovery.
3. Expired session restoration and a stale edit surviving refresh, with required
   conflict comparison before saving.
4. Keyboard activation, viewport overflow checks at 360/768/1280px, and axe WCAG
   A/AA checks for auth, editor and cooking screens.

Visual inspection of desktop/mobile screenshots confirmed layout/readability.
Axe caught muted text at 4.42:1 on the ingredient panel; the final token was darkened
and the accessibility tests passed. Screenshots and failure traces are generated
under ignored `frontend/test-results/`; CI uploads failures. These automated checks
are not a substitute for screen-reader or moderated usability testing.

**D1 acceptance still needs five authorized target-user observations. D2 release
acceptance still needs A3 managed-staging verification.** Neither user sessions nor
public/staging deployment occurred. Browser tests replace only outbound HTML fetching
with a deterministic fixture and use real database, authentication and API work;
paid AI is mocked separately. No pilot readiness claim is made.
