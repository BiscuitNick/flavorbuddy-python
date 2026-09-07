# Firebase Google sign-in increment — September 7, 2026

The owner selected Firebase Google sign-in instead of maintaining SMTP/password recovery.
Implementation provides a Google popup, verified Firebase-to-Django session exchange,
one-time proof of legacy account ownership, and revocation/disablement checks.
Recipe, pantry and photo owner IDs remain unchanged when linking an existing account.

Firebase project, Authentication configuration, staging web app and authorized staging
hostname are provisioned. The Google provider still needs activation in the signed-in
owner console, followed by a real hosted sign-in. The application feature remains gated
until then. See [operating instructions](../operations/firebase-auth.md).

The FlavorGirls application API retains its existing client-credentials OAuth flow:
standard app identity, short-lived tokens, catalog grants, shared quotas and revocation.
This is separate from Firebase user identity and introduces no user consent flow.

Validation ([green CI run](https://github.com/BiscuitNick/flavorbuddy-python/actions/runs/34142215749),
application commit `39fdd05`):

- 101 backend tests passed in remote CI, including 14 Firebase checks for token
  validation, linking, session revocation, outage logout and production emulator rejection.
- 16 existing desktop/mobile browser scenarios passed.
- Four real-SDK emulator scenarios passed: desktop/mobile sign-in, session reload,
  private recipe isolation, disabled-user denial and one-time legacy linking/logout.
- Production checks with Firebase enabled passed with zero warnings; migration drift,
  TypeScript/Vite build, Terraform validation and runtime dependency audit passed.
- Firebase SDK is loaded separately (about 27 KB compressed); the emulator CLI is
  development-only. The production dependency audit reported zero vulnerabilities.

Hosted provider activation and a real Google login are pending. Emulator tests do not
prove Google consent configuration, hosted popup handling or real account recovery.


## Protected deployment

- Application commit `39fdd05`, image digest
  `sha256:2730247f4b9189d6c6d00e9219ca218394944ade44239170867c96137b0c356a`.
- Serving revision `flavorbuddy-staging-00005-pkw`, 100% traffic. Prior healthy revision
  `flavorbuddy-staging-00004-8b5` remains the compatible rollback target; no schema reversal.
- Backup `1788797775878` succeeded before the migration. Migration job execution
  `flavorbuddy-staging-migrate-mhj9c` applied `0011_firebaseidentity` and exited successfully.
- The runtime custom role has only user verification and session-creation permissions.
  Execution `flavorbuddy-staging-migrate-69444` used the actual Firebase Admin SDK with
  the attached Cloud Run identity and successfully performed a Firebase user lookup
  (expected nonexistent-user response). It also verified the migration and zero bulk links.
- Existing two-account HTTPS smoke passed: login/CSRF, private recipe and pantry isolation,
  existing completion/export data, and private GCS photo hash/decode/ownership checks.
- FlavorGirls v2 smoke returned 12 candidates for `lemon`, validated the selected document,
  and revoked its test token. Existing app OAuth is unaffected.
- Firebase Google provider remains absent, and deployment has `firebase_enabled=false` /
  `local_auth_enabled=true`. This deliberately retains existing staging access until the
  console activation step; **hosted Firebase authentication is not yet active or verified**.
- Terraform reports no drift. No accounts were bulk linked, no email was sent, and
  IAM-protected ingress remains intact.

After enabling Google, set the existing Terraform Firebase flag, deploy, and verify real
Google sign-in. Legacy password smoke scripts apply only while legacy mode is enabled;
the Firebase-enabled host needs real Google identities for its hosted account smoke.
