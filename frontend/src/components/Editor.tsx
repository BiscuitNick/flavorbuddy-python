import React, { useState, useRef } from "react";
import { Check, ArrowRight } from "lucide-react";
import { ApiError } from "../api";
import type { Content } from "../api";
import { ErrorBox } from "./ErrorBox";
export function Editor({
  content,
  onChange,
  onSave,
  label,
  conflictAction,
  onSaveDraft,
}: {
  content: Content;
  onChange: (c: Content) => void;
  onSave: (c: Content) => Promise<void>;
  label: string;
  conflictAction?: () => Promise<void>;
  onSaveDraft?: (c: Content) => Promise<void>;
}) {
  const [error, setError] = useState<unknown>();
  const [busy, setBusy] = useState(false);
  const firstError = useRef<HTMLDivElement>(null);
  function field<K extends keyof Content>(key: K, value: Content[K]) {
    onChange({ ...content, [key]: value });
  }
  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await onSave({
        ...content,
        ingredients: content.ingredients.map((s) => s.trim()).filter(Boolean),
        instructions: content.instructions.map((s) => s.trim()).filter(Boolean),
      });
    } catch (e) {
      setError(e);
      setTimeout(() => firstError.current?.focus(), 0);
    } finally {
      setBusy(false);
    }
  }
  const missing =
    !content.title.trim() ||
    !content.ingredients.some((s) => s.trim()) ||
    !content.instructions.some((s) => s.trim());
  return (
    <form
      className="editor"
      onSubmit={submit}
      aria-describedby={error ? "editor-errors" : undefined}
    >
      <div ref={firstError} tabIndex={-1} id="editor-errors">
        <ErrorBox error={error} />
      </div>
      {error instanceof ApiError && error.status === 409 && conflictAction && (
        <button
          type="button"
          className="button secondary"
          onClick={async () => {
            await conflictAction();
            setError(null);
          }}
        >
          Review latest draft, keeping my edits
        </button>
      )}
      {missing && (
        <p className="notice">
          Almost there: a title, ingredients, and directions are required to
          save.
        </p>
      )}
      <div className="editor-grid">
        <section className="form-section">
          <span className="eyebrow">THE BASICS</span>
          <label>
            Recipe title
            <input
              aria-invalid={error instanceof ApiError && !!error.fields.title}
              aria-describedby={
                error instanceof ApiError && error.fields.title
                  ? "field-error-title"
                  : undefined
              }
              value={content.title}
              onChange={(e) => field("title", e.target.value)}
              required
              maxLength={255}
            />
          </label>
          <label>
            Description
            <textarea
              aria-invalid={
                error instanceof ApiError && !!error.fields.description
              }
              aria-describedby={
                error instanceof ApiError && error.fields.description
                  ? "field-error-description"
                  : undefined
              }
              value={content.description}
              onChange={(e) => field("description", e.target.value)}
              rows={3}
              maxLength={10000}
            />
          </label>
          <div className="two-fields">
            <label>
              Total time (minutes)
              <input
                type="number"
                min={0}
                max={100000}
                aria-invalid={
                  error instanceof ApiError && !!error.fields.total_time
                }
                aria-describedby={
                  error instanceof ApiError && error.fields.total_time
                    ? "field-error-total_time"
                    : undefined
                }
                value={content.total_time ?? ""}
                onChange={(e) =>
                  field(
                    "total_time",
                    e.target.value === "" ? null : Number(e.target.value),
                  )
                }
              />
            </label>
            <label>
              Servings / yield
              <input
                aria-invalid={
                  error instanceof ApiError && !!error.fields.yields
                }
                aria-describedby={
                  error instanceof ApiError && error.fields.yields
                    ? "field-error-yields"
                    : undefined
                }
                value={content.yields}
                onChange={(e) => field("yields", e.target.value)}
                placeholder="e.g. 4 servings"
                maxLength={255}
              />
            </label>
          </div>
          <label>
            Author
            <input
              aria-invalid={error instanceof ApiError && !!error.fields.author}
              aria-describedby={
                error instanceof ApiError && error.fields.author
                  ? "field-error-author"
                  : undefined
              }
              value={content.author}
              onChange={(e) => field("author", e.target.value)}
              maxLength={255}
            />
          </label>
          <label>
            Source URL
            <input
              type="url"
              aria-invalid={
                error instanceof ApiError && !!error.fields.source_url
              }
              aria-describedby={
                error instanceof ApiError && error.fields.source_url
                  ? "field-error-source_url"
                  : undefined
              }
              value={content.source_url ?? ""}
              onChange={(e) => field("source_url", e.target.value || null)}
              maxLength={2000}
            />
          </label>
          <label>
            Image URL <small>(optional)</small>
            <input
              type="url"
              aria-invalid={error instanceof ApiError && !!error.fields.image}
              aria-describedby={
                error instanceof ApiError && error.fields.image
                  ? "field-error-image"
                  : undefined
              }
              value={content.image}
              onChange={(e) => field("image", e.target.value)}
              maxLength={2000}
            />
          </label>
        </section>
        <section className="form-section">
          <span className="eyebrow">THE GOOD STUFF</span>
          <label>
            Ingredients <small>One ingredient per line</small>
            <textarea
              aria-invalid={
                error instanceof ApiError && !!error.fields.ingredients
              }
              aria-describedby={
                error instanceof ApiError && error.fields.ingredients
                  ? "field-error-ingredients"
                  : undefined
              }
              value={content.ingredients.join("\n")}
              onChange={(e) => field("ingredients", e.target.value.split("\n"))}
              rows={8}
              required
              maxLength={50000}
            />
          </label>
          <label>
            Directions <small>One step per line</small>
            <textarea
              aria-invalid={
                error instanceof ApiError && !!error.fields.instructions
              }
              aria-describedby={
                error instanceof ApiError && error.fields.instructions
                  ? "field-error-instructions"
                  : undefined
              }
              value={content.instructions.join("\n")}
              onChange={(e) =>
                field("instructions", e.target.value.split("\n"))
              }
              rows={10}
              required
              maxLength={100000}
            />
          </label>
          <label>
            Personal notes
            <textarea
              aria-invalid={error instanceof ApiError && !!error.fields.notes}
              aria-describedby={
                error instanceof ApiError && error.fields.notes
                  ? "field-error-notes"
                  : undefined
              }
              value={content.notes ?? ""}
              onChange={(e) => field("notes", e.target.value)}
              rows={3}
              placeholder="A little more lemon next time…"
              maxLength={10000}
            />
          </label>
        </section>
      </div>
      <div className="editor-actions">
        <span>
          <Check size={16} /> Draft kept on this device
        </span>
        {onSaveDraft && (
          <button
            type="button"
            className="button secondary"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              setError(null);
              try {
                await onSaveDraft({
                  ...content,
                  ingredients: content.ingredients
                    .map((s) => s.trim())
                    .filter(Boolean),
                  instructions: content.instructions
                    .map((s) => s.trim())
                    .filter(Boolean),
                });
              } catch (e) {
                setError(e);
              } finally {
                setBusy(false);
              }
            }}
          >
            Save draft
          </button>
        )}
        <button className="button primary" disabled={busy || missing}>
          {busy ? "Saving…" : label}
          <ArrowRight size={18} />
        </button>
      </div>
    </form>
  );
}
