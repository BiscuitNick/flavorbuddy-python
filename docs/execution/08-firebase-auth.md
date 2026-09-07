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

Local validation:

- 99 full backend tests passed before adding two final checks; all 14 Firebase-specific
  tests then passed, including provider outage logout and production emulator rejection.
- 16 existing desktop/mobile browser scenarios passed.
- Four real-SDK emulator scenarios passed: desktop/mobile sign-in, session reload,
  private recipe isolation, disabled-user denial and one-time legacy linking/logout.
- Production checks with Firebase enabled passed with zero warnings; migration drift,
  TypeScript/Vite build, Terraform validation and runtime dependency audit passed.
- Firebase SDK is loaded separately (about 27 KB compressed); the emulator CLI is
  development-only. The production dependency audit reported zero vulnerabilities.

Hosted provider activation and a real Google login are pending. Emulator tests do not
prove Google consent configuration, hosted popup handling or real account recovery.
