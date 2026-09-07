import { useState, useEffect } from "react";
import {
  Plus,
  Search,
  Heart,
  Download,
  Clock,
  ArrowRight,
  BookOpen,
  Leaf,
} from "lucide-react";
import { api } from "../../api";
import type { User, Recipe } from "../../api";
import { ErrorBox } from "../../components/ErrorBox";
import { FoodImage } from "../../components/RecipeContent";
export function Library({ user }: { user: User }) {
  const [query, setQuery] = useState("");
  const [favorite, setFavorite] = useState(false);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<{
    results: Recipe[];
    count: number;
    has_next: boolean;
  }>();
  const [error, setError] = useState<unknown>();
  const [retry, setRetry] = useState(0);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let alive = true;
    setBusy(true);
    const timer = setTimeout(() => {
      api<typeof data & {}>(
        `recipes?q=${encodeURIComponent(query)}&favorite=${favorite}&page=${page}`,
      )
        .then((d) => {
          if (alive) {
            setData(d);
            setError(null);
          }
        })
        .catch((e) => {
          if (alive) setError(e);
        })
        .finally(() => {
          if (alive) setBusy(false);
        });
    }, 180);
    return () => {
      alive = false;
      clearTimeout(timer);
    };
  }, [query, favorite, page, retry]);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR EVERYDAY INSPIRATION</span>
          <h1>
            Your recipe box<span className="tomato">.</span>
          </h1>
          <p>Old favorites and soon-to-be favorites. All in one place.</p>
        </div>
        <a className="button primary desktop-add" href="#/import">
          <Plus size={18} /> Add a recipe
        </a>
      </div>
      <a className="button secondary" href="#/starters">
        Browse starter recipes <ArrowRight size={18} />
      </a>
      <section className="library-toolbar">
        <label className="search">
          <Search size={19} />
          <span className="sr-only">Search recipes</span>
          <input
            value={query}
            placeholder="Find something delicious…"
            onChange={(e) => {
              setQuery(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <button
          className={`chip ${favorite ? "selected" : ""}`}
          aria-pressed={favorite}
          onClick={() => {
            setFavorite(!favorite);
            setPage(1);
          }}
        >
          <Heart size={16} /> Favorites
        </button>
        <button
          className="icon-button"
          aria-label="Export your recipes"
          onClick={async () => {
            try {
              const data = await api("recipes/export");
              const url = URL.createObjectURL(
                new Blob([JSON.stringify(data, null, 2)], {
                  type: "application/json",
                }),
              );
              const a = document.createElement("a");
              a.href = url;
              a.download = "flavorbuddy-recipes.json";
              a.click();
              URL.revokeObjectURL(url);
            } catch (e) {
              setError(e);
            }
          }}
        >
          <Download size={19} />
        </button>
      </section>
      <div className="section-label">
        <span>
          {query
            ? "SEARCH RESULTS"
            : favorite
              ? "THE ONES YOU LOVE"
              : "ALL YOUR RECIPES"}
        </span>
        <span>{data?.count ?? 0} recipes</span>
      </div>
      <ErrorBox error={error} />
      {error && (
        <button
          className="button secondary"
          onClick={() => setRetry(retry + 1)}
        >
          Try again
        </button>
      )}
      {busy ? (
        <p role="status" className="loading">
          Finding your recipes…
        </p>
      ) : data?.results.length ? (
        <>
          <div className="recipe-grid">
            {data.results.map((recipe) => (
              <a
                href={`#/recipe/${recipe.id}`}
                className="recipe-card"
                key={recipe.id}
              >
                <FoodImage recipe={recipe} />
                <div className="card-body">
                  <div className="card-source">
                    {recipe.source_url
                      ? new URL(recipe.source_url).hostname.replace("www.", "")
                      : "FROM YOUR KITCHEN"}
                    {recipe.favorite && <Heart size={16} fill="currentColor" />}
                  </div>
                  <h2>{recipe.title || "Untitled draft"}</h2>
                  <div className="card-meta">
                    <span>
                      <Clock size={15} />
                      {recipe.total_time === null
                        ? "Take your time"
                        : `${recipe.total_time} min`}
                    </span>
                    <ArrowRight size={18} />
                  </div>
                </div>
              </a>
            ))}
          </div>
          <div className="pagination">
            <button
              className="button secondary"
              disabled={page === 1}
              onClick={() => setPage(page - 1)}
            >
              Previous
            </button>
            <span>Page {page}</span>
            <button
              className="button secondary"
              disabled={!data.has_next}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </>
      ) : (
        <section className="empty">
          <span className="empty-icon">
            <BookOpen size={36} strokeWidth={1.2} />
          </span>
          <h2>
            {query || favorite
              ? "No recipes here just yet."
              : "Every good meal starts somewhere."}
          </h2>
          <p>
            {query || favorite
              ? "Try another search or show all your recipes."
              : "Bring that recipe you keep meaning to try. We’ll keep it ready for you."}
          </p>
          <a href="#/import" className="button primary">
            {query || favorite ? "Add a recipe" : "Save your first recipe"}
            <Plus size={18} />
          </a>
          <a className="text-button" href="#/sample">
            Or take a look at an example
          </a>
        </section>
      )}
      <aside className="kitchen-note">
        <Leaf size={22} />
        <div>
          <strong>A recipe is just the beginning.</strong>
          <p>
            Add your own notes. A little more garlic? Always worth remembering.
          </p>
        </div>
      </aside>
      <span className="sr-only">Signed in as {user.email}</span>
    </>
  );
}
