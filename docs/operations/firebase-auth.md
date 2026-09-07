# Firebase Google sign-in

Selected September 7, 2026 to replace app-owned password recovery and SMTP setup.
Firebase authenticates people; Django/PostgreSQL retains application data and ownership.
The existing FlavorGirls client-credentials OAuth API remains independent.

## Provisioned and pending

Firebase was added to existing GCP project `flavorbuddy-20260906`; Authentication was
initialized and web app `1:560489769953:web:f77309d411a016ae0cc0a0` registered. The canonical
staging hostname is an authorized Firebase domain. The web app configuration is in
`~/.local/share/flavorbuddy/staging/firebase-web-config.json` (public identifiers/API key;
it does not grant access to recipes). No Firestore database or Firebase Storage bucket
is needed or provisioned for this integration.

**Google provider activation remains pending.** Open
[Authentication → Sign-in method](https://console.firebase.google.com/project/flavorbuddy-20260906/authentication/providers),
sign in to the project owner's Google account, enable Google, set the app's public name
and project support email, and save. Use the console-created web OAuth client; do not
paste its secret into chat, Git, Django settings or Terraform state. The available agent
browser is signed out, so this owner-console step is not yet completed.

After the provider is configured, set `firebase_web_config` from that operator file and
`firebase_enabled=true` in the existing protected Terraform release inputs. Review/apply
the plan and test a real Google sign-in, reload, private recipe access and logout.
Do not declare hosted authentication verified based on emulator results.

Cloud Run's existing IAM gate remains enforced: a Firebase token does not replace a
Cloud Run invoker identity. Operator access still needs the existing authenticated
proxy/header; pilot-friendly ingress remains a separate roadmap item.

## Configuration and permissions

The backend reads `FIREBASE_PROJECT_ID`, `FIREBASE_API_KEY`, `FIREBASE_AUTH_DOMAIN` and
`FIREBASE_APP_ID` at runtime and serves public web configuration through `/api/v1/me`.
No environment-specific frontend rebuild is required. Firebase mode defaults
`LOCAL_AUTH_ENABLED=false`, hiding and rejecting password login, registration and reset.
An unconfigured development instance retains legacy local authentication.

The runtime's custom IAM role contains only `firebaseauth.users.get` and
`firebaseauth.users.createSession`. Admin SDK credentials come from the attached
Cloud Run service account; do not create/download a service account key. Local real-project
work requires separately configured Application Default Credentials.

## Account/session behavior

- Only a Firebase-verified `google.com` sign-in with verified email and authentication
  within the last five minutes can start a session. SDK verification enforces project,
  issuer, signature, expiry and revocation/disablement.
- A unique `(project_id, uid)` maps to one existing Django user. When a legacy account's
  email matches, the user must supply its current password once. There is no automatic
  email merge, recipe reassignment or bulk migration. Linked users have unusable local
  passwords, and old reset tokens/local sessions are invalidated by that change.
- New accounts receive unusable Django passwords. Google owns password/account recovery.
  A legacy user unable to prove their existing password needs operator-assisted identity
  verification; do not silently merge them by email.
- The browser SDK uses in-memory persistence and signs out after obtaining the ID token.
  Django holds the minted Firebase session cookie in its database-backed session;
  the browser receives only the existing HttpOnly, Secure-in-production session ID.
  Sessions expire after 12 hours. No raw token or legacy password is logged or returned.
- Each Firebase session request checks provider revocation and disablement. This adds
  an Identity Toolkit user lookup per request, acceptable for the small pilot; monitor
  latency/quota before scaling. Invalid sessions are cleared; outages return 503 without
  destroying the session. Local logout remains available during a provider outage.
- CSRF protects the exchange and every application mutation; login rotates CSRF/session
  identifiers. `same-origin-allow-popups` permits the Google popup callback.
- Normal logout ends this browser session. Revoke Firebase sessions/disable the user in
  Firebase to terminate access across devices; the next request checks provider state.

## Automated verification

Run the regular backend/browser suite and:

```sh
npm run test:firebase --prefix frontend
```

This starts only the Auth emulator on `127.0.0.1:9099` with isolated project
`demo-flavorbuddy`, plus a disposable PostgreSQL browser database. It uses the actual
Firebase client and Admin SDKs through the emulator's Google popup. No real Google
accounts, live credentials, emails or cloud writes are used by this suite.
`FIREBASE_AUTH_EMULATOR_HOST` is forbidden in production and requires a `demo-` project
in development/test. The emulator is never a hosted authentication bypass.

References: [Google sign-in](https://firebase.google.com/docs/auth/web/google-signin),
[server verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens),
[session cookies](https://firebase.google.com/docs/auth/admin/manage-cookies),
[Auth emulator](https://firebase.google.com/docs/emulator-suite/connect_auth).
