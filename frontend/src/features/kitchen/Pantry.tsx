import { useEffect, useState } from "react";
import { api } from "../../api";
import { CaptureDemo } from "./CaptureDemo";
import { ErrorBox } from "../../components/ErrorBox";
type Item = {
  id: number;
  name: string;
  quantity: string;
  location: string;
  running_low: boolean;
  use_soon: boolean;
  used_up: boolean;
  version: number;
};
type Match = {
  id: number;
  kind: string;
  title: string;
  matched: { ingredient: string; explanation: string }[];
  missing: string[];
  uncertain: { ingredient: string; explanation: string }[];
};
const empty = {
  name: "",
  quantity: "",
  location: "Pantry",
  running_low: false,
  use_soon: false,
};
export function Pantry() {
  const [items, setItems] = useState<Item[]>([]),
    [form, setForm] = useState(empty),
    [editing, setEditing] = useState<Item | null>(null);
  const [error, setError] = useState<unknown>(),
    [busy, setBusy] = useState(false),
    [loaded, setLoaded] = useState(false);
  const [matches, setMatches] = useState<Match[]>([]),
    [notice, setNotice] = useState(""),
    [excluded, setExcluded] = useState(0);
  const [diet, setDiet] = useState(""),
    [exclusions, setExclusions] = useState(""),
    [status, setStatus] = useState("");
  async function load() {
    const data = await api<{ items: Item[] }>("pantry");
    setItems(data.items);
    setLoaded(true);
  }
  async function match() {
    const data = await api<{
      matches: Match[];
      notice: string;
      excluded_count: number;
    }>("pantry/matches");
    setMatches(data.matches);
    setNotice(data.notice);
    setExcluded(data.excluded_count);
  }
  useEffect(() => {
    load().catch(setError);
    api<{ diet: string; exclusions: string[] }>("preferences")
      .then((p) => {
        setDiet(p.diet);
        setExclusions(p.exclusions.join("\n"));
      })
      .catch(setError);
  }, []);
  async function update(item: Item, values: Partial<Item>) {
    setError(null);
    setBusy(true);
    try {
      await api(`pantry/${item.id}`, "PATCH", {
        ...values,
        version: item.version,
      });
      await load();
      setMatches([]);
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="kitchen-page">
      <span className="eyebrow">WHAT YOU HAVE</span>
      <h1>Your pantry</h1>
      <p>
        Pantry, fridge, freezer, and every little cupboard. Add as much detail
        as you find useful.
      </p>
      <ErrorBox error={error} />
      <form
        className="panel kitchen-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError(null);
          try {
            await api(
              editing ? `pantry/${editing.id}` : "pantry",
              editing ? "PATCH" : "POST",
              { ...form, ...(editing ? { version: editing.version } : {}) },
            );
            setForm(empty);
            setEditing(null);
            await load();
            setMatches([]);
            setStatus("Pantry saved.");
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2>{editing ? "Edit ingredient" : "Add an ingredient"}</h2>
        <label>
          Ingredient
          <input
            required
            maxLength={120}
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
        </label>
        <label>
          Quantity (optional)
          <input
            maxLength={80}
            placeholder="A bag, 2 cups, or leave blank"
            value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: e.target.value })}
          />
        </label>
        <label>
          Location
          <input
            required
            list="pantry-locations"
            maxLength={80}
            value={form.location}
            onChange={(e) => setForm({ ...form, location: e.target.value })}
          />
        </label>
        <datalist id="pantry-locations">
          {Array.from(
            new Set([
              "Pantry",
              "Fridge",
              "Freezer",
              ...items.map((i) => i.location),
            ]),
          ).map((l) => (
            <option key={l} value={l} />
          ))}
        </datalist>
        <label className="check-row">
          <input
            type="checkbox"
            checked={form.running_low}
            onChange={(e) =>
              setForm({ ...form, running_low: e.target.checked })
            }
          />
          Running low
        </label>
        <label className="check-row">
          <input
            type="checkbox"
            checked={form.use_soon}
            onChange={(e) => setForm({ ...form, use_soon: e.target.checked })}
          />
          Use soon
        </label>
        <button className="button" disabled={busy}>
          {editing ? "Save ingredient" : "Add ingredient"}
        </button>
        {editing && (
          <button
            type="button"
            className="button secondary"
            onClick={() => {
              setEditing(null);
              setForm(empty);
            }}
          >
            Cancel edit
          </button>
        )}
      </form>
      <p role="status">{status}</p>
      {!loaded ? (
        <p role="status">Opening your pantry…</p>
      ) : items.length === 0 ? (
        <p>Your pantry is empty. Start with an ingredient you use often.</p>
      ) : (
        <div className="pantry-list">
          {items.map((item) => (
            <article className="panel pantry-item" key={item.id}>
              <div>
                <h3>
                  {item.name}
                  {item.used_up ? " · Used up" : ""}
                </h3>
                <p>
                  {item.quantity ? `${item.quantity} · ` : ""}
                  {item.location}
                  {item.running_low ? " · Running low" : ""}
                  {item.use_soon ? " · Use soon" : ""}
                </p>
              </div>
              <div className="kitchen-actions">
                <button
                  disabled={busy}
                  className="button secondary"
                  onClick={() => update(item, { used_up: !item.used_up })}
                >
                  {item.used_up
                    ? `Undo used up ${item.name}`
                    : `Used up ${item.name}`}
                </button>
                <button
                  className="text-button"
                  onClick={() => {
                    setEditing(item);
                    setForm(item);
                    window.scrollTo(0, 0);
                  }}
                >
                  Edit {item.name}
                </button>
                <button
                  disabled={busy}
                  className="text-button"
                  onClick={async () => {
                    if (!confirm(`Delete ${item.name} from your pantry?`))
                      return;
                    try {
                      await api(`pantry/${item.id}`, "DELETE");
                      await load();
                      setMatches([]);
                    } catch (e) {
                      setError(e);
                    }
                  }}
                >
                  Delete {item.name}
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
      <CaptureDemo
        onApproved={() => {
          load().catch(setError);
          setMatches([]);
        }}
      />
      <form
        className="panel kitchen-form"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          try {
            await api("preferences", "PUT", {
              diet,
              exclusions: exclusions
                .split("\n")
                .map((x) => x.trim())
                .filter(Boolean),
            });
            await match();
            setStatus("Preferences saved; suggestions updated.");
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <h2>Your preferences</h2>
        <label>
          Diet preference
          <select value={diet} onChange={(e) => setDiet(e.target.value)}>
            <option value="">No diet filter</option>
            <option value="vegetarian">Vegetarian</option>
            <option value="vegan">Vegan</option>
          </select>
        </label>
        <label>
          Ingredients to exclude (one per line)
          <textarea
            value={exclusions}
            onChange={(e) => setExclusions(e.target.value)}
            placeholder="Peanuts&#10;Cilantro"
          />
        </label>
        <p>
          Filters use ingredient words. They cannot guarantee allergy or dietary
          safety; check recipes and food labels.
        </p>
        <button disabled={busy} className="button secondary">
          Save preferences and find recipes
        </button>
      </form>
      <p>
        <a href="/api/v1/kitchen/export" download>
          Export pantry, preferences and photo references
        </a>
      </p>
      <div className="kitchen-actions">
        <h2>What could you cook?</h2>
        <button
          className="button"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await match();
            } catch (e) {
              setError(e);
            } finally {
              setBusy(false);
            }
          }}
        >
          Find recipes with my pantry
        </button>
      </div>
      {notice && (
        <p>
          {notice} {excluded} recipes hidden by your exclusions.
        </p>
      )}
      <div className="pantry-list">
        {matches.map((m) => (
          <article className="panel" key={`${m.kind}:${m.id}`}>
            <h3>
              <a
                href={`#/${m.kind === "private" ? "recipe" : "starters"}/${m.id}`}
              >
                {m.title}
              </a>
            </h3>
            <p>
              {m.matched.length} ingredient names matched · {m.missing.length}{" "}
              to check or buy
            </p>
            {m.matched.map((x, i) => (
              <p key={i}>
                <strong>{x.ingredient}</strong> — {x.explanation}
              </p>
            ))}
            {m.missing.length > 0 && (
              <p>Missing or unconfirmed: {m.missing.join("; ")}</p>
            )}
            {m.uncertain.map((x, i) => (
              <p key={i}>
                {x.ingredient}: {x.explanation}
              </p>
            ))}
          </article>
        ))}
      </div>
    </section>
  );
}
