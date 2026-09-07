import { useEffect, useState } from "react";
import { ArrowLeft, ArrowRight, Clock, Search } from "lucide-react";
import { api } from "../../api";
import type { Content, Recipe, User } from "../../api";
import { go } from "../../navigation";
import { ErrorBox } from "../../components/ErrorBox";
import { FoodImage, RecipeBody } from "../../components/RecipeContent";

type Starter = Content & {
  id: number;
  slug: string;
  provenance: {
    license: string;
    license_url: string;
    source_url: string;
    revision: string;
  };
};
type Results = { results: Starter[]; count: number; has_next: boolean };
export function StarterCatalog({
  user,
  id,
}: {
  user: User | null;
  id?: number;
}) {
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [result, setResult] = useState<Results>();
  const [recipe, setRecipe] = useState<Starter>();
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    let active = true;
    setBusy(true);
    setError(null);
    setRecipe(undefined);
    const timer = setTimeout(() => {
      const request = id
        ? api<Starter>(`starters/${id}`).then((value) => {
            if (active) setRecipe(value);
          })
        : api<Results>(
            `starters?q=${encodeURIComponent(query)}&page=${page}`,
          ).then((value) => {
            if (active) setResult(value);
          });
      request
        .catch((e) => {
          if (active) setError(e);
        })
        .finally(() => {
          if (active) setBusy(false);
        });
    }, 150);
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [id, query, page, retry]);
  async function save() {
    if (!id) return;
    if (!user) {
      go(`/starters/${id}/save`);
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const saved = await api<Recipe>(`starters/${id}/save`, "POST", {});
      go(`/recipe/${saved.id}`);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <a className="back" href={id ? "#/starters" : "#/"}>
        <ArrowLeft size={16} />
        {id ? "Browse starter recipes" : "Your kitchen"}
      </a>
      <ErrorBox error={error} />
      {error && (
        <button
          className="button secondary"
          onClick={() => setRetry((v) => v + 1)}
        >
          Try again
        </button>
      )}
      {id ? (
        <>
          {recipe ? (
            <>
              <div className="recipe-heading">
                <span className="eyebrow">PUBLIC DOMAIN RECIPES</span>
                <h1>{recipe.title}</h1>
                <p>{recipe.description}</p>
                <p>
                  By {recipe.author || "a community contributor"} ·{" "}
                  <a
                    href={recipe.provenance.license_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Public domain / Unlicense
                  </a>
                </p>
                <div className="recipe-meta">
                  <span>{recipe.yields || "Yield not provided"}</span>
                  <a
                    href={recipe.source_url ?? undefined}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Original recipe
                  </a>
                </div>
              </div>
              <div className="detail-actions">
                <button
                  className="button primary"
                  disabled={busy}
                  onClick={save}
                >
                  {busy
                    ? "Saving…"
                    : user
                      ? "Save to my recipes"
                      : "Sign in to save"}
                  <ArrowRight size={18} />
                </button>
                <span className="muted">
                  Your saved copy and edits stay private.
                </span>
              </div>
              <RecipeBody recipe={recipe} />
            </>
          ) : busy ? (
            <p role="status">Opening starter recipe…</p>
          ) : null}
        </>
      ) : (
        <>
          <div className="page-heading">
            <div>
              <span className="eyebrow">
                A COMMUNITY COOKBOOK, READY FOR YOUR KITCHEN
              </span>
              <h1>Something new to cook.</h1>
              <p>
                Browse public-domain recipes. Save the ones you love and make
                them your own.
              </p>
            </div>
          </div>
          <label className="search">
            <Search size={18} />
            <span className="sr-only">Search starter recipes</span>
            <input
              placeholder="Pasta, soup, apple pie…"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <div className="section-label" style={{ marginTop: 24 }}>
            <span>STARTER COLLECTION</span>
            <span>{result?.count ?? 0} recipes</span>
          </div>
          {busy ? (
            <p role="status">Finding starter recipes…</p>
          ) : (
            <>
              <div className="recipe-grid">
                {result?.results.map((r) => (
                  <a
                    className="recipe-card"
                    href={`#/starters/${r.id}`}
                    key={r.id}
                  >
                    <FoodImage recipe={r} />
                    <div className="card-body">
                      <div className="card-source">PUBLIC DOMAIN RECIPES</div>
                      <h2>{r.title}</h2>
                      <div className="card-meta">
                        <span>
                          <Clock size={15} />
                          {r.total_time === null
                            ? "Community recipe"
                            : `${r.total_time} min`}
                        </span>
                        <ArrowRight size={18} />
                      </div>
                    </div>
                  </a>
                ))}
              </div>
              {result?.count === 0 && (
                <p>No matches. Try another dish or ingredient name.</p>
              )}
              <div className="pagination">
                <button
                  className="button secondary"
                  disabled={page === 1}
                  onClick={() => setPage((p) => p - 1)}
                >
                  Previous
                </button>
                <span>Page {page}</span>
                <button
                  className="button secondary"
                  disabled={!result?.has_next}
                  onClick={() => setPage((p) => p + 1)}
                >
                  Next
                </button>
              </div>
            </>
          )}
          <p className="muted">
            Community-contributed recipes from Public Domain Recipes. Source
            text and credit are retained; these recipes have not been
            individually kitchen-tested by FlavorBuddy.
          </p>
        </>
      )}
    </>
  );
}
