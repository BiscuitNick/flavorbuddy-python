import { useEffect, useState } from "react";
import { api, ApiError } from "../../api";
import type { User } from "../../api";
import type { FirebaseConfig } from "./firebase";
import { ErrorBox } from "../../components/ErrorBox";

export function GoogleSignIn({
  config,
  onAuth,
}: {
  config: FirebaseConfig;
  onAuth: (user: User) => void;
}) {
  const [signIn, setSignIn] = useState<(() => Promise<string>) | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [linkToken, setLinkToken] = useState("");
  useEffect(() => {
    let active = true;
    import("./firebase")
      .then(({ prepareGoogle }) => {
        const start = prepareGoogle(config);
        if (active) setSignIn(() => start);
      })
      .catch(() => {
        if (active)
          setError(
            new Error("Could not load Google sign-in. Refresh to try again."),
          );
      });
    return () => {
      active = false;
    };
  }, [config]);

  async function exchange(token: string, password?: string) {
    try {
      await api("me");
      const result = await api<{ user: User }>("auth/firebase", "POST", {
        id_token: token,
        ...(password ? { legacy_password: password } : {}),
      });
      setLinkToken("");
      onAuth(result.user);
    } catch (error) {
      if (error instanceof ApiError && error.code === "account_link_required")
        setLinkToken(token);
      else setLinkToken("");
      throw error;
    }
  }

  return (
    <>
      <ErrorBox error={error} />
      {linkToken ? (
        <form
          onSubmit={async (event) => {
            event.preventDefault();
            const password = String(
              new FormData(event.currentTarget).get("legacy_password") || "",
            );
            event.currentTarget.reset();
            setBusy(true);
            setError(null);
            try {
              await exchange(linkToken, password);
            } catch (error) {
              setError(error);
            } finally {
              setBusy(false);
            }
          }}
        >
          <p>
            Connect Google to your existing recipe box. After this, you’ll only
            need Google to sign in.
          </p>
          <label>
            Existing FlavorBuddy password
            <input
              name="legacy_password"
              type="password"
              autoComplete="current-password"
              maxLength={128}
              required
            />
          </label>
          <button className="button primary full" disabled={busy}>
            {busy ? "Connecting…" : "Connect Google and keep my recipes"}
          </button>
          <button
            type="button"
            className="text-button"
            disabled={busy}
            onClick={() => {
              setLinkToken("");
              setError(null);
            }}
          >
            Use another Google account
          </button>
        </form>
      ) : (
        <>
          <button
            className="button primary full"
            disabled={busy || !signIn}
            onClick={async () => {
              if (!signIn) return;
              setBusy(true);
              setError(null);
              try {
                await exchange(await signIn());
              } catch (error) {
                const code = (error as { code?: string })?.code;
                if (
                  code !== "auth/popup-closed-by-user" &&
                  code !== "auth/cancelled-popup-request"
                ) {
                  setError(
                    error instanceof ApiError
                      ? error
                      : new Error(
                          code === "auth/popup-blocked"
                            ? "Allow pop-ups for this site, then try Google sign-in again."
                            : "Google sign-in could not finish. Please try again.",
                        ),
                  );
                }
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Signing in…" : "Continue with Google"}
          </button>
          <p>
            Use your Google account to sign in or create an account. Google
            handles password recovery.
          </p>
        </>
      )}
    </>
  );
}
