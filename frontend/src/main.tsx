import React, { useState, useEffect, useRef } from "react";
import { createRoot } from "react-dom/client";
import { Utensils, BookOpen, Plus, LogOut } from "lucide-react";
import { api } from "./api";
import type { User } from "./api";
import { go } from "./navigation";
import { ErrorBox } from "./components/ErrorBox";
import { Welcome, Auth, Reset } from "./features/auth/Auth";
import { Sample, ImportFlow } from "./features/import/ImportFlow";
import { Library } from "./features/library/Library";
import { StarterCatalog } from "./features/starter/StarterCatalog";
import { SharedRecipes } from "./features/library/SharedRecipes";
import { RecipePage } from "./features/library/RecipePage";
import "@fontsource/dm-sans/400.css";
import "@fontsource/dm-sans/500.css";
import "@fontsource/dm-sans/600.css";
import "@fontsource/dm-sans/700.css";
import "@fontsource/libre-caslon-display/400.css";
import "./styles.css";
import { Pantry } from "./features/kitchen/Pantry";
function useRoute() {
  const [route, setRoute] = useState(location.hash.slice(1) || "/");
  useEffect(() => {
    const update = () => setRoute(location.hash.slice(1) || "/");
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
function App() {
  const route = useRoute();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [authError, setAuthError] = useState<unknown>(null);
  const [recovery, setRecovery] = useState(false);
  const heading = useRef<HTMLElement>(null);
  useEffect(() => {
    const expired = () => setUser(null);
    window.addEventListener("fb:session-expired", expired);
    return () => window.removeEventListener("fb:session-expired", expired);
  }, []);
  useEffect(() => {
    api<{ user: User | null; recovery_available: boolean }>("me")
      .then((data) => {
        setUser(data.user);
        setRecovery(data.recovery_available);
      })
      .catch(setAuthError)
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    heading.current?.focus();
    window.scrollTo(0, 0);
  }, [route]);
  async function signOut() {
    try {
      await api("auth/logout", "POST", {});
      setUser(null);
      go("/");
    } catch (e) {
      setAuthError(e);
    }
  }
  const requiresAuth =
    route !== "/" &&
    route !== "/sample" &&
    !route.startsWith("/shared") &&
    !route.startsWith("/reset/") &&
    !(route.startsWith("/starters") && !route.endsWith("/save"));
  return (
    <>
      <header className="site-header">
        <a href="#/" className="brand">
          <span className="brand-mark">
            <Utensils size={19} />
          </span>
          flavorbuddy<span className="alpha">ALPHA</span>
        </a>
        <nav aria-label="Main navigation">
          <a
            href="#/"
            aria-label="Recipe box"
            className={route === "/" ? "active" : ""}
          >
            <BookOpen size={17} />
            <span>Recipe box</span>
          </a>
          <a href="#/shared">Public recipes</a>
          <a href="#/import" aria-label="Add recipe" className="nav-add">
            <Plus size={18} />
            <span>Add recipe</span>
          </a>
          {user && (
            <a href="#/pantry" aria-label="Pantry">
              Pantry
            </a>
          )}
          {user && (
            <button
              className="icon-button"
              onClick={signOut}
              aria-label={`Sign out ${user.email}`}
              title={user.email}
            >
              <LogOut size={18} />
            </button>
          )}
        </nav>
      </header>
      <main ref={heading} tabIndex={-1} id="main">
        <ErrorBox error={authError} />
        {loading ? (
          <p className="loading" role="status">
            Opening your recipe box…
          </p>
        ) : route.startsWith("/reset/") ? (
          <Reset route={route} />
        ) : !user && requiresAuth ? (
          <Auth onAuth={setUser} recovery={recovery} />
        ) : route.startsWith("/starters") ? (
          <StarterCatalog
            key={`${user?.id ?? "guest"}:${route}`}
            user={user}
            id={Number(route.split("/")[2]) || undefined}
          />
        ) : route.startsWith("/shared") ? (
          <SharedRecipes id={route.split("/")[2]} user={user} />
        ) : route === "/sample" ? (
          <Sample user={user} />
        ) : !user ? (
          <Welcome onAuth={setUser} recovery={recovery} />
        ) : route === "/pantry" ? (
          <Pantry key={user.id} />
        ) : route === "/import" ? (
          <ImportFlow user={user} />
        ) : route.match(/^\/recipe\/\d+/) ? (
          <RecipePage
            key={`${user.id}:${route.split("/")[2]}`}
            user={user}
            id={Number(route.split("/")[2])}
            mode={route.split("/")[3] || "detail"}
          />
        ) : (
          <Library user={user} />
        )}
      </main>
      <footer>
        <span>Made for the way you cook.</span>
        <span>Your recipes. Your little rituals.</span>
      </footer>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
