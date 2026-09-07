import { useState, useEffect, useRef } from "react";
import { ArrowLeft, ArrowRight, Clock, Check, X } from "lucide-react";
import { readLocal, writeLocal } from "../../api";
import type { User, Recipe } from "../../api";
import { go } from "../../navigation";
import { ErrorBox } from "../../components/ErrorBox";
type Progress = {
  step: number;
  checked: number[];
  end: number | null;
  completed: boolean;
  key: string;
};
export function Cook({
  user,
  recipe,
  onNote,
}: {
  user: User;
  recipe: Recipe;
  onNote: (notes: string, key: string) => Promise<void>;
}) {
  const storage = `fb:${user.id}:cook:${recipe.id}`;
  const [progress, setProgress] = useState<Progress>(() =>
    readLocal(storage, {
      step: 0,
      checked: [],
      end: null,
      completed: false,
      key: crypto.randomUUID(),
    }),
  );
  const [now, setNow] = useState(Date.now());
  const [minutes, setMinutes] = useState(5);
  const [note, setNote] = useState(() =>
    readLocal(storage + ":note", recipe.notes),
  );
  useEffect(() => writeLocal(storage + ":note", note), [note, storage]);
  const [error, setError] = useState<unknown>();
  const [awake, setAwake] = useState(false);
  const lock = useRef<WakeLockSentinel | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    writeLocal(storage, progress);
  }, [progress, storage]);
  useEffect(() => {
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => {
      clearInterval(timer);
      lock.current?.release();
    };
  }, []);
  const step = Math.min(progress.step, recipe.instructions.length - 1);
  const left =
    progress.end === null
      ? null
      : Math.max(0, Math.ceil((progress.end - now) / 1000));
  async function toggleAwake() {
    try {
      if (lock.current) {
        await lock.current.release();
        lock.current = null;
        setAwake(false);
      } else if ("wakeLock" in navigator) {
        lock.current = await navigator.wakeLock.request("screen");
        lock.current.addEventListener("release", () => {
          setAwake(false);
          lock.current = null;
        });
        setAwake(true);
      }
    } catch {
      setError(
        new Error(
          "Screen awake is unavailable. You can keep cooking normally.",
        ),
      );
    }
  }
  return (
    <section className="cook">
      <div className="cook-top">
        <a href={`#/recipe/${recipe.id}`} className="back">
          <X size={18} /> Exit cooking
        </a>
        <span className="eyebrow">IN YOUR KITCHEN</span>
      </div>
      <h1>{recipe.title}</h1>
      <ErrorBox error={error} />
      <div className="cook-grid">
        <aside className="ingredient-panel">
          <h2>Ingredients</h2>
          <p className="muted">Check them off as you go.</p>
          {recipe.ingredients.map((s, i) => (
            <label
              className={`check-row ${progress.checked.includes(i) ? "checked" : ""}`}
              key={i}
            >
              <input
                type="checkbox"
                checked={progress.checked.includes(i)}
                onChange={() =>
                  setProgress((p) => ({
                    ...p,
                    checked: p.checked.includes(i)
                      ? p.checked.filter((n) => n !== i)
                      : [...p.checked, i],
                  }))
                }
              />
              <span>{s}</span>
            </label>
          ))}
        </aside>
        <div>
          <div className="cook-step">
            <span className="eyebrow">
              STEP {step + 1} OF {recipe.instructions.length}
            </span>
            <div className="step-dots" aria-hidden="true">
              {recipe.instructions.map((_, i) => (
                <span key={i} className={i <= step ? "done" : ""} />
              ))}
            </div>
            <p className="instruction" aria-live="polite">
              {recipe.instructions[step]}
            </p>
            <div className="step-controls">
              <button
                className="button secondary"
                disabled={step === 0}
                onClick={() => setProgress((p) => ({ ...p, step: step - 1 }))}
              >
                <ArrowLeft size={18} /> Previous
              </button>
              {step < recipe.instructions.length - 1 ? (
                <button
                  className="button primary"
                  onClick={() => setProgress((p) => ({ ...p, step: step + 1 }))}
                >
                  Next step <ArrowRight size={18} />
                </button>
              ) : (
                <button
                  className="button primary"
                  onClick={() =>
                    setProgress((p) => ({ ...p, completed: true }))
                  }
                >
                  <Check size={18} /> Mark complete
                </button>
              )}
            </div>
          </div>
          <section className="timer">
            <Clock size={21} />
            <label>
              Kitchen timer
              <input
                type="number"
                aria-label="Timer minutes"
                value={minutes}
                onChange={(e) => setMinutes(Number(e.target.value))}
                min={1}
                max={240}
              />
            </label>
            <span>min</span>
            <button
              className="button secondary"
              disabled={
                !Number.isFinite(minutes) || minutes < 1 || minutes > 240
              }
              onClick={() =>
                setProgress((p) => ({
                  ...p,
                  end: Date.now() + minutes * 60000,
                }))
              }
            >
              Start
            </button>
            {left !== null && (
              <>
                <strong role={left === 0 ? "status" : undefined}>
                  {left === 0
                    ? "Timer finished"
                    : `${Math.floor(left / 60)}:${String(left % 60).padStart(2, "0")}`}
                </strong>
                <button
                  className="icon-button"
                  aria-label="Clear timer"
                  onClick={() => setProgress((p) => ({ ...p, end: null }))}
                >
                  <X size={17} />
                </button>
              </>
            )}
          </section>
          <p className="muted timer-note">
            Keep this page open to see the timer. Background alerts aren’t
            supported.
          </p>
          {"wakeLock" in navigator && (
            <button
              className="text-button"
              aria-pressed={awake}
              onClick={toggleAwake}
            >
              {awake ? "Screen awake is on" : "Keep screen awake while cooking"}
            </button>
          )}
          {progress.completed && (
            <section className="completion">
              <span className="eyebrow">NICE WORK, CHEF</span>
              <h2>Make a little note for next time.</h2>
              <label>
                Cooking note
                <textarea
                  rows={3}
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                  maxLength={10000}
                />
              </label>
              <button
                className="button primary"
                disabled={saving}
                onClick={async () => {
                  setSaving(true);
                  try {
                    await onNote(note, progress.key);
                    writeLocal(storage, null);
                    writeLocal(storage + ":note", null);
                    go(`/recipe/${recipe.id}`);
                  } catch (e) {
                    setError(e);
                  } finally {
                    setSaving(false);
                  }
                }}
              >
                {saving ? "Saving…" : "Save note & finish"}
              </button>
            </section>
          )}
        </div>
      </div>
    </section>
  );
}
