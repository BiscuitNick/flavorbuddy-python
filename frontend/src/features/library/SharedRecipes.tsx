import { useEffect, useState } from "react";
import { api } from "../../api";
import type { Recipe, User } from "../../api";
import { RecipeBody } from "../../components/RecipeContent";
import { ErrorBox } from "../../components/ErrorBox";
import { go } from "../../navigation";

export function SharedRecipes({
  id,
  user,
}: {
  id?: string;
  user: User | null;
}) {
  const [recipe, setRecipe] = useState<Recipe>();
  const [results, setResults] = useState<{
    results: Recipe[];
    has_next: boolean;
  }>();
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(1);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    let active = true;
    setError(null);
    setRecipe(undefined);
    const request = id
      ? api<Recipe>(`shared-recipes/${id}`).then((r) => {
          if (active) setRecipe(r);
        })
      : api<{ results: Recipe[]; has_next: boolean }>(
          `shared-recipes?q=${encodeURIComponent(query)}&page=${page}`,
        ).then((r) => {
          if (active) setResults(r);
        });
    request.catch((e) => {
      if (active) setError(e);
    });
    return () => {
      active = false;
    };
  }, [id, query, page]);
  return (
    <>
      <a href="#/shared" className="back">
        Public recipes
      </a>
      <ErrorBox error={error} />
      {id ? (
        recipe ? (
          <>
            <h1>{recipe.title}</h1>
            <p>{recipe.description}</p>
            <p className="muted">
              Finalized recipe · This link always identifies this recipe.
            </p>
            {user && (
              <button
                className="button secondary"
                onClick={async (e) => {
                  e.currentTarget.disabled = true;
                  try {
                    const draft = await api<Recipe>(
                      `recipes/${recipe.id}/variations`,
                      "POST",
                      {},
                    );
                    go(`/recipe/${draft.id}/edit`);
                  } catch (error) {
                    setError(error);
                  }
                }}
              >
                Make a variation
              </button>
            )}
            <RecipeBody recipe={recipe} />
          </>
        ) : (
          !error && <p role="status">Opening recipe…</p>
        )
      ) : (
        <>
          <h1>Public recipes</h1>
          <label className="search">
            Search public recipes
            <input
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </label>
          <div className="recipe-grid">
            {results?.results.map((r) => (
              <a
                key={r.public_id}
                className="recipe-card"
                href={`#/shared/${r.public_id}`}
              >
                <div className="card-body">
                  <h2>{r.title}</h2>
                </div>
              </a>
            ))}
          </div>
          <div className="pagination">
            <button disabled={page === 1} onClick={() => setPage(page - 1)}>
              Previous
            </button>
            <span>Page {page}</span>
            <button
              disabled={!results?.has_next}
              onClick={() => setPage(page + 1)}
            >
              Next
            </button>
          </div>
        </>
      )}
    </>
  );
}
