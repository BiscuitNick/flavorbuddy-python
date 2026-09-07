import { useEffect, useState } from "react";
import { api } from "../../api";
import { ErrorBox } from "../../components/ErrorBox";
type Photo = {
  id: number;
  url: string;
  kind: string;
  recipe_version: number;
  completion_id: number | null;
};
type Completion = { id: number; created_at: string; recipe_version: number };
export function PrivatePhotos({
  recipeId,
  onChange,
}: {
  recipeId: number;
  onChange: () => void;
}) {
  const [photos, setPhotos] = useState<Photo[]>([]),
    [completions, setCompletions] = useState<Completion[]>([]);
  const [error, setError] = useState<unknown>(),
    [file, setFile] = useState<File | null>(null),
    [kind, setKind] = useState("cover"),
    [completion, setCompletion] = useState(""),
    [busy, setBusy] = useState(false),
    [status, setStatus] = useState("");
  async function load() {
    const data = await api<{ photos: Photo[]; completions: Completion[] }>(
      `recipes/${recipeId}/photos`,
    );
    setPhotos(data.photos);
    setCompletions(data.completions);
  }
  useEffect(() => {
    load().catch(setError);
  }, [recipeId]);
  return (
    <section className="panel private-photos">
      <h2>Your private photos</h2>
      <p>
        Add a cover or remember how dinner turned out. Photos stay in your
        account.
      </p>
      <ErrorBox error={error} />
      <div className="photo-grid">
        {photos.map((p) => (
          <figure key={p.id}>
            <img
              src={p.url}
              alt={
                p.kind === "cover" ? "Your recipe cover" : "Your cooking result"
              }
            />
            <a href={p.url} download={`photo-${p.id}.webp`}>
              Download photo
            </a>
            <figcaption>
              {p.kind === "cover" ? "Cover" : "Cooking result"}
            </figcaption>
            <button
              className="text-button"
              disabled={busy}
              onClick={async () => {
                if (!confirm("Delete this private photo?")) return;
                try {
                  await api(`photos/${p.id}`, "DELETE");
                  await load();
                  onChange();
                } catch (e) {
                  setError(e);
                }
              }}
            >
              Delete photo
            </button>
          </figure>
        ))}
      </div>
      <form
        className="kitchen-form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!file) return;
          setBusy(true);
          setError(null);
          try {
            const data = new FormData();
            data.append("photo", file);
            data.append("kind", kind);
            if (kind === "result") data.append("completion_id", completion);
            await api(`recipes/${recipeId}/photos`, "POST", data);
            await load();
            onChange();
            setStatus("Private photo saved.");
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Photo type
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="cover">Recipe cover</option>
            <option value="result">Cooking result</option>
          </select>
        </label>
        {kind === "result" && (
          <label>
            Cooking session
            <select
              required
              value={completion}
              onChange={(e) => setCompletion(e.target.value)}
            >
              <option value="">Choose a completed session</option>
              {completions.map((c) => (
                <option key={c.id} value={c.id}>
                  {new Date(c.created_at).toLocaleString()}
                </option>
              ))}
            </select>
          </label>
        )}
        {kind === "result" && completions.length === 0 && (
          <p>
            Finish a cooking session first to attach your result to that recipe
            you cooked.
          </p>
        )}
        <label>
          Photo (JPEG, PNG or WebP, up to 8 MiB)
          <input
            required
            type="file"
            accept="image/jpeg,image/png,image/webp"
            onChange={(e) => setFile(e.target.files?.[0] || null)}
          />
        </label>
        <button className="button secondary" disabled={busy || !file}>
          {busy ? "Saving photo…" : "Save private photo"}
        </button>
      </form>
      <p role="status">{status}</p>
    </section>
  );
}
