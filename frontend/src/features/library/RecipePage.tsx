import { useState, useEffect } from "react";
import {
  ArrowLeft,
  Clock,
  ExternalLink,
  ChefHat,
  SlidersHorizontal,
  Heart,
  Trash2,
} from "lucide-react";
import { api, readLocal, writeLocal, recipeContent } from "../../api";
import type { User, Recipe, Content } from "../../api";
import { go } from "../../navigation";
import { ErrorBox } from "../../components/ErrorBox";
import { RecipeBody } from "../../components/RecipeContent";
import { Editor } from "../../components/Editor";
import { PrivatePhotos } from "../kitchen/PrivatePhotos";
import { Cook } from "../cooking/Cook";
export function RecipePage({
  user,
  id,
  mode,
}: {
  user: User;
  id: number;
  mode: string;
}) {
  const [recipe, setRecipe] = useState<Recipe>();
  const [error, setError] = useState<unknown>();
  const [revision, setRevision] = useState(0);
  const [edit, setEdit] = useState<Content | null>(null);
  const [editVersion, setEditVersion] = useState(1);
  const [latest, setLatest] = useState<Recipe>();
  const storage = `fb:${user.id}:edit:${id}`;
  useEffect(() => {
    api<Recipe>(`recipes/${id}`)
      .then((r) => {
        setRecipe(r);
        const saved = readLocal<Recipe>(storage, r);
        setEdit(saved);
        setEditVersion(saved.version ?? r.version);
      })
      .catch(setError);
  }, [id, revision, storage]);
  function change(c: Content) {
    setEdit(c);
    writeLocal(storage, { ...c, version: editVersion });
  }
  async function patch(values: Partial<Content>) {
    if (!recipe) return;
    const result = await api<Recipe>(`recipes/${id}`, "PATCH", {
      ...values,
      version: recipe.version,
    });
    setRecipe(result);
    if (!readLocal(storage, null)) {
      setEdit(result);
      setEditVersion(result.version);
    }
    return result;
  }
  if (error)
    return (
      <>
        <ErrorBox error={error} />
        <a href="#/" className="button secondary">
          Back to recipe box
        </a>
        <button
          className="text-button"
          onClick={() => {
            setError(null);
            setRevision(revision + 1);
          }}
        >
          Try again
        </button>
      </>
    );
  if (!recipe)
    return (
      <p className="loading" role="status">
        Opening your recipe…
      </p>
    );
  if (mode === "cook" && recipe.state === "finalized")
    return (
      <Cook
        user={user}
        recipe={recipe}
        onNote={async (notes, key) => {
          const result = await api<Recipe>(`recipes/${id}/cook`, "POST", {
            notes,
            key,
            version: recipe.version,
          });
          setRecipe(result);
        }}
      />
    );
  return (
    <>
      <a href="#/" className="back">
        <ArrowLeft size={16} /> Your recipe box
      </a>
      <div className="recipe-heading">
        <span className="eyebrow">
          {mode === "edit" ? "MAKE IT YOURS" : "FROM YOUR RECIPE BOX"}
        </span>
        <h1>{recipe.title || "Untitled draft"}</h1>
        <p>{recipe.description}</p>
        <p className="notice">
          {recipe.state === "draft"
            ? "Private draft · You can keep editing."
            : `Finalized · ${recipe.visibility === "public" ? "Public" : "Private"} · Make a variation to change the recipe.`}
        </p>
        {recipe.provenance?.license && (
          <p className="muted">
            From Public Domain Recipes ·{" "}
            <a
              href={recipe.provenance.license_url}
              target="_blank"
              rel="noreferrer"
            >
              Public domain / Unlicense
            </a>
          </p>
        )}
        <div className="recipe-meta">
          <span>
            <Clock size={17} />
            {recipe.total_time === null
              ? "Time not provided"
              : `${recipe.total_time} minutes`}
          </span>
          <span>{recipe.yields || "Yield not provided"}</span>
          {recipe.source_url && (
            <a href={recipe.source_url} target="_blank" rel="noreferrer">
              Original recipe <ExternalLink size={14} />
            </a>
          )}
        </div>
      </div>
      {mode === "edit" && recipe.state === "draft" && edit ? (
        <>
          {latest && (
            <details open className="notice">
              <summary>
                Latest saved draft — compare before saving your edits
              </summary>
              <h3>{latest.title}</h3>
              <p>{latest.description}</p>
              <p>Ingredients: {latest.ingredients.join("; ")}</p>
              <p>Directions: {latest.instructions.join(" ")}</p>
              <p>Notes: {latest.notes}</p>
            </details>
          )}
          <Editor
            content={edit}
            onChange={change}
            onSave={async (c) => {
              const draft = await api<Recipe>(`recipes/${id}`, "PATCH", {
                ...recipeContent(c),
                version: editVersion,
              });
              // Persist the updated conflict token even if finalization fails.
              setRecipe(draft);
              setEditVersion(draft.version);
              writeLocal(storage, { ...c, version: draft.version });
              const result = await api<Recipe>(
                `recipes/${id}/finalize`,
                "POST",
                { version: draft.version },
              );
              setRecipe(result);
              setEdit(result);
              setEditVersion(result.version);
              writeLocal(storage, null);
              go(`/recipe/${id}`);
            }}
            onSaveDraft={async (c) => {
              const result = await api<Recipe>(`recipes/${id}`, "PATCH", {
                ...recipeContent(c),
                version: editVersion,
              });
              setRecipe(result);
              setEdit(result);
              setEditVersion(result.version);
              writeLocal(storage, null);
              go(`/recipe/${id}`);
            }}
            label="Save recipe"
            conflictAction={async () => {
              const r = await api<Recipe>(`recipes/${id}`);
              setRecipe(r);
              setLatest(r);
              setEditVersion(r.version);
              writeLocal(storage, { ...edit, version: r.version });
            }}
          />
          <a className="text-button" href={`#/recipe/${id}`}>
            Back to recipe (keep draft)
          </a>
        </>
      ) : (
        <>
          <div className="detail-actions">
            {recipe.state === "draft" ? (
              <a className="button primary" href={`#/recipe/${id}/edit`}>
                <SlidersHorizontal size={17} /> Edit draft
              </a>
            ) : (
              <>
                <a href={`#/recipe/${id}/cook`} className="button primary">
                  <ChefHat size={19} /> Let’s cook
                </a>
                <button
                  className="button secondary"
                  onClick={async (event) => {
                    event.currentTarget.disabled = true;
                    try {
                      const draft = await api<Recipe>(
                        `recipes/${id}/variations`,
                        "POST",
                        {},
                      );
                      go(`/recipe/${draft.id}/edit`);
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  Make a variation
                </button>
                <button
                  className="button secondary"
                  onClick={async () => {
                    try {
                      const result = await api<Recipe>(
                        `recipes/${id}/visibility`,
                        "POST",
                        {
                          version: recipe.version,
                          visibility:
                            recipe.visibility === "private"
                              ? "public"
                              : "private",
                        },
                      );
                      setRecipe(result);
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  {recipe.visibility === "private"
                    ? "Share publicly"
                    : "Make private"}
                </button>
                <a
                  className="text-button"
                  href={`#/shared/${recipe.public_id}`}
                >
                  Permanent recipe link
                </a>
              </>
            )}
            <button
              className={`icon-button favorite ${recipe.favorite ? "selected" : ""}`}
              aria-label={recipe.favorite ? "Remove favorite" : "Add favorite"}
              onClick={async () => {
                try {
                  await patch({ favorite: !recipe.favorite });
                } catch (e) {
                  setError(e);
                }
              }}
            >
              <Heart
                size={21}
                fill={recipe.favorite ? "currentColor" : "none"}
              />
            </button>
            <button
              className="icon-button delete"
              aria-label={
                recipe.state === "draft" ? "Delete draft" : "Archive recipe"
              }
              onClick={async () => {
                if (
                  confirm(
                    recipe.state === "draft"
                      ? `Delete draft “${recipe.title}”?`
                      : `Archive “${recipe.title}”? Its content and identity will be retained.`,
                  )
                ) {
                  try {
                    await api(`recipes/${id}`, "DELETE");
                    writeLocal(storage, null);
                    writeLocal(`fb:${user.id}:cook:${id}`, null);
                    go("/");
                  } catch (e) {
                    setError(e);
                  }
                }
              }}
            >
              <Trash2 size={19} />
            </button>
          </div>
          <RecipeBody recipe={recipe} />
        </>
      )}
      {mode !== "edit" && (
        <PrivatePhotos
          recipeId={id}
          onChange={() => {
            api<Recipe>(`recipes/${id}`).then(setRecipe).catch(setError);
          }}
        />
      )}
    </>
  );
}
