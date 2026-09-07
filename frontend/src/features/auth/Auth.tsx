import React, { useState } from "react";
import { ArrowRight } from "lucide-react";
import { api, sample } from "../../api";
import type { User } from "../../api";
import { ErrorBox } from "../../components/ErrorBox";
import { FoodImage } from "../../components/RecipeContent";
import { GoogleSignIn } from "./GoogleSignIn";
import type { FirebaseConfig } from "./firebase";
type AuthProps = {
  onAuth: (u: User) => void;
  recovery: boolean;
  firebase?: FirebaseConfig | null;
  localAuth?: boolean;
};
export function Welcome({ onAuth, recovery, firebase, localAuth }: AuthProps) {
  return (
    <section className="welcome">
      <div className="welcome-copy">
        <span className="eyebrow">
          A LITTLE LESS SCROLLING. A LITTLE MORE COOKING.
        </span>
        <h1>
          Good recipes.
          <br />
          Always within reach.
        </h1>
        <p>
          A home for the dishes you want to make again. Bring a recipe, make it
          yours, and get cooking.
        </p>
        <a href="#/sample" className="button secondary">
          Explore a sample <ArrowRight size={18} />
        </a>
        <a href="#/starters" className="text-button">
          Browse the public-domain recipe collection
        </a>
        <div className="welcome-art">
          <FoodImage recipe={sample} />
          <div>
            <span className="eyebrow">FROM THE PANTRY</span>
            <h3>
              Lemony chickpeas
              <br />
              on toast
            </h3>
            <span>15 minutes · A little everyday joy</span>
          </div>
        </div>
      </div>
      <Auth
        onAuth={onAuth}
        recovery={recovery}
        firebase={firebase}
        localAuth={localAuth}
      />
    </section>
  );
}

export function Auth({
  onAuth,
  recovery,
  firebase,
  localAuth = true,
}: AuthProps) {
  const [mode, setMode] = useState("login");
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [sent, setSent] = useState(false);
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const data = Object.fromEntries(new FormData(e.currentTarget));
    try {
      await api("me");
      const result = await api<{ user: User }>("auth/" + mode, "POST", data);
      if (mode === "reset") setSent(true);
      else onAuth(result.user);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="auth-card">
      <span className="eyebrow">YOUR PRIVATE RECIPE BOX</span>
      <h2>
        {mode === "register"
          ? "Make yourself at home."
          : mode === "reset"
            ? "Let’s get you back in."
            : "Welcome to the kitchen."}
      </h2>
      <p>
        Sign in to import and save recipes privately. Your draft stays here
        while you sign in.
      </p>
      <ErrorBox error={error} />
      {firebase && <GoogleSignIn config={firebase} onAuth={onAuth} />}
      {!firebase && !localAuth && (
        <p>Sign-in is temporarily unavailable. Please try again later.</p>
      )}
      {localAuth && (
        <>
          {sent ? (
            <p role="status">
              If that account exists, a reset link is on its way.
            </p>
          ) : (
            <form onSubmit={submit}>
              <label>
                Email
                <input
                  name="email"
                  type="email"
                  autoComplete="email"
                  maxLength={150}
                  required
                />
              </label>
              {mode !== "reset" && (
                <label>
                  Password
                  <input
                    name="password"
                    type="password"
                    autoComplete={
                      mode === "register" ? "new-password" : "current-password"
                    }
                    maxLength={128}
                    minLength={mode === "register" ? 8 : 1}
                    required
                  />
                </label>
              )}
              <button className="button primary full" disabled={busy}>
                {busy
                  ? "One moment…"
                  : mode === "register"
                    ? "Create account"
                    : mode === "reset"
                      ? "Send reset link"
                      : "Sign in"}
                <ArrowRight size={18} />
              </button>
            </form>
          )}
          <button
            className="text-button"
            onClick={() => {
              setMode(mode === "register" ? "login" : "register");
              setError(null);
              setSent(false);
            }}
          >
            {mode === "register"
              ? "Already have an account? Sign in"
              : "New here? Create an account"}
          </button>
          {recovery && (
            <button className="text-button" onClick={() => setMode("reset")}>
              Forgot your password?
            </button>
          )}
        </>
      )}
    </section>
  );
}

export function Reset({ route }: { route: string }) {
  const [done, setDone] = useState(false);
  const [error, setError] = useState<unknown>();
  return (
    <section className="auth-card">
      <h1>Choose a new password</h1>
      <ErrorBox error={error} />
      {done ? (
        <a href="#/">Password updated. Sign in</a>
      ) : (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api("auth/reset-confirm", "POST", {
                uid: route.split("/")[2],
                token: route.split("/")[3],
                password: new FormData(e.currentTarget).get("password"),
              });
              setDone(true);
            } catch (e) {
              setError(e);
            }
          }}
        >
          <label>
            New password
            <input
              type="password"
              name="password"
              minLength={8}
              maxLength={128}
              required
              autoComplete="new-password"
            />
          </label>
          <button className="button primary">Update password</button>
        </form>
      )}
    </section>
  );
}
