import { useState, useEffect } from "react";
import { ArrowLeft, ArrowRight, Leaf } from "lucide-react";
import {
  api,
  blank,
  sample,
  readLocal,
  writeLocal,
  recipeContent,
} from "../../api";
import type { User, Content, Draft, Recipe } from "../../api";
import { go } from "../../navigation";
import { ErrorBox } from "../../components/ErrorBox";
import { RecipeBody } from "../../components/RecipeContent";
import { Editor } from "../../components/Editor";
export function Sample({ user }: { user: User | null }) {
  return (
    <>
      <a href="#/" className="back">
        <ArrowLeft size={16} /> Back to your kitchen
      </a>
      <div className="page-heading">
        <div>
          <span className="eyebrow">AN EXAMPLE TO MAKE YOUR OWN</span>
          <h1>{sample.title}</h1>
          <p>
            This is a local sample. Import your own recipes once you sign in.
          </p>
        </div>
        <button
          className="button primary"
          onClick={() => {
            writeLocal("fb:sample-requested", true);
            go("/import");
          }}
        >
          {user ? "Use this sample" : "Sign in to make it yours"}
          <ArrowRight size={18} />
        </button>
      </div>
      <RecipeBody recipe={sample} />
    </>
  );
}

type ImportState = {
  mode: string;
  input: string;
  key: string;
  draft: Draft | null;
  content: Content | null;
};
export function ImportFlow({ user }: { user: User }) {
  const storage = `fb:${user.id}:import`;
  const [state, setState] = useState<ImportState>(() => {
    if (readLocal("fb:sample-requested", false)) {
      return {
        mode: "manual",
        input: "",
        key: crypto.randomUUID(),
        draft: null,
        content: sample,
      };
    }
    return readLocal(storage, {
      mode: "url",
      input: "",
      key: crypto.randomUUID(),
      draft: null,
      content: null,
    });
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>();
  useEffect(() => {
    writeLocal(storage, state);
    writeLocal("fb:sample-requested", false);
  }, [state, storage]);
  function change(values: Partial<ImportState>) {
    setState((s) => ({ ...s, ...values }));
  }
  async function extract() {
    setBusy(true);
    setError(null);
    try {
      const result = await api<Draft>("imports", "POST", {
        mode: state.mode,
        input: state.input,
        key: state.key,
      });
      change({
        draft: result,
        content: result.state === "ready" ? result.content : blank,
      });
      if (result.state === "failed")
        setError(
          new Error(
            result.error_code === "ai_unavailable"
              ? "Text extraction is not enabled on this instance. Your text is preserved below; add the recipe details manually."
              : result.error_code === "throttled"
                ? "The import limit has been reached. You can still enter the recipe manually."
                : "We couldn’t extract this source. Your input is preserved. Correct the recipe below or try pasted text.",
          ),
        );
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  async function save(
    content: Content,
    saveState: "draft" | "finalized" = "finalized",
  ) {
    let draft = state.draft;
    if (!draft) {
      draft = await api<Draft>("imports", "POST", {
        mode: "manual",
        input: "",
        key: state.key,
      });
      change({ draft });
    }
    const recipe = await api<Recipe>("recipes", "POST", {
      ...recipeContent(content),
      state: saveState,
      import_id: draft.id,
    });
    writeLocal(storage, null);
    go(`/recipe/${recipe.id}`);
  }
  return (
    <>
      <a href="#/" className="back">
        <ArrowLeft size={16} /> Your recipe box
      </a>
      <div className="page-heading">
        <div>
          <span className="eyebrow">MAKE ROOM FOR SOMETHING GOOD</span>
          <h1>
            {state.content
              ? "A little finishing touch."
              : "Bring a recipe home."}
          </h1>
          <p>
            {state.content
              ? "Save a draft to keep editing, or save the recipe to lock its content privately."
              : "From a favorite website, a note, or your own kitchen."}
          </p>
        </div>
      </div>
      <ErrorBox error={error} />
      {!state.content ? (
        <section className="import-panel">
          <div className="tabs" role="group" aria-label="Import method">
            {[
              ["url", "Website link"],
              ["text", "Paste text"],
              ["manual", "Write your own"],
            ].map(([mode, label]) => (
              <button
                key={mode}
                className={state.mode === mode ? "selected" : ""}
                aria-pressed={state.mode === mode}
                onClick={() => change({ mode, key: crypto.randomUUID() })}
              >
                {label}
              </button>
            ))}
          </div>
          {state.mode === "url" ? (
            <label>
              Recipe URL
              <input
                type="url"
                placeholder="https://your-favorite-site.com/recipe"
                value={state.input}
                onChange={(e) =>
                  change({ input: e.target.value, key: crypto.randomUUID() })
                }
              />
            </label>
          ) : state.mode === "text" ? (
            <label>
              Recipe text
              <textarea
                rows={9}
                maxLength={50000}
                value={state.input}
                placeholder="Paste the title, ingredients, and directions…"
                onChange={(e) =>
                  change({ input: e.target.value, key: crypto.randomUUID() })
                }
              />
              <small>
                Text extraction uses AI when enabled. You’ll always review the
                result.
              </small>
            </label>
          ) : (
            <p>A family favorite? A delicious experiment? Give it a home.</p>
          )}
          <button
            className="button primary"
            onClick={
              state.mode === "manual"
                ? () => change({ content: blank })
                : extract
            }
            disabled={busy || (state.mode !== "manual" && !state.input.trim())}
          >
            {busy
              ? "Importing your recipe…"
              : state.mode === "manual"
                ? "Start writing"
                : "Import recipe"}
            <ArrowRight size={18} />
          </button>
          {busy && (
            <p role="status">
              This may take a few moments. Keep this page open.
            </p>
          )}
          <div className="import-tip">
            <Leaf size={20} />
            <p>
              Just the recipe, ready for you to cook. You can edit every detail
              before saving.
            </p>
          </div>
          <button
            className="text-button"
            onClick={() => change({ content: sample, mode: "manual" })}
          >
            Try it with our chickpea toast sample
          </button>
        </section>
      ) : (
        <>
          {state.input && (
            <details className="source-input">
              <summary>
                Your original {state.mode === "url" ? "link" : "text"}
              </summary>
              <p className="preserve-lines">{state.input}</p>
            </details>
          )}
          <Editor
            key={state.key}
            content={state.content}
            onChange={(content) => change({ content })}
            onSave={save}
            onSaveDraft={(c) => save(c, "draft")}
            label="Save recipe"
          />
          <button
            className="text-button"
            onClick={() => {
              if (
                confirm(
                  "Start another import? This will replace this unsaved preview.",
                )
              ) {
                change({
                  content: null,
                  draft: null,
                  key: crypto.randomUUID(),
                });
                setError(null);
              }
            }}
          >
            Start another import
          </button>
        </>
      )}
    </>
  );
}
