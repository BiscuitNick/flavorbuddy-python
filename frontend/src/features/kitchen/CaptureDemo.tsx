import { useEffect, useState } from "react";
import { api } from "../../api";
import { ErrorBox } from "../../components/ErrorBox";
type Row = { name: string; quantity: string; location: string };
type Job = {
  id: number;
  state: string;
  notice: string;
  preview: Row[];
  approved_ids: number[];
};
export function CaptureDemo({ onApproved }: { onApproved: () => void }) {
  const [enabled, setEnabled] = useState(false);
  const [file, setFile] = useState<File | null>(null),
    [job, setJob] = useState<Job | null>(null),
    [rows, setRows] = useState<Row[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState<unknown>(),
    [key, setKey] = useState(crypto.randomUUID());
  async function refresh(id: number) {
    const data = await api<Job>(`pantry/captures/${id}`);
    setJob(data);
    if (data.state === "preview") setRows(data.preview);
  }
  useEffect(() => {
    api<{ capture_demo: boolean }>("capabilities")
      .then((d) => setEnabled(d.capture_demo))
      .catch(setError);
    api<{ jobs: Job[] }>("pantry/captures")
      .then((d) => {
        const j = d.jobs.find(
          (j) => !["cancelled", "approved"].includes(j.state),
        );
        if (j) {
          setJob(j);
          setRows(j.preview);
        }
      })
      .catch(setError);
  }, []);
  useEffect(() => {
    if (!job || !["queued", "running", "uploading"].includes(job.state)) return;
    const timer = window.setInterval(
      () => refresh(job.id).catch(setError),
      1000,
    );
    return () => window.clearInterval(timer);
  }, [job?.id, job?.state]);
  if (!enabled && !job) return null;
  return (
    <details className="panel capture-demo">
      <summary>Try the photo review demo</summary>
      <p>
        This development demo uses fixed example detections. It does not analyze
        your photo. The uploaded photo stays private; nothing enters your pantry
        until you approve.
      </p>
      <ErrorBox error={error} />
      <form
        className="kitchen-form"
        onSubmit={async (e) => {
          e.preventDefault();
          if (!file) return;
          setBusy(true);
          setError(null);
          try {
            const body = new FormData();
            body.append("photo", file);
            body.append("key", key);
            const data = await api<Job>("pantry/captures", "POST", body);
            setJob(data);
            setRows(data.preview);
          } catch (e) {
            setError(e);
          } finally {
            setBusy(false);
          }
        }}
      >
        <label>
          Pantry photo
          <input
            type="file"
            required
            accept="image/jpeg,image/png,image/webp"
            capture="environment"
            onChange={(e) => {
              setFile(e.target.files?.[0] || null);
              setKey(crypto.randomUUID());
            }}
          />
        </label>
        <button disabled={busy || !file} className="button secondary">
          Create demo preview
        </button>
      </form>
      {job && (
        <>
          <p role="status">Capture: {job.state}</p>
          <p>{job.notice}</p>
          {["queued", "running", "uploading"].includes(job.state) && (
            <button
              className="button secondary"
              onClick={() => refresh(job.id).catch(setError)}
            >
              Refresh capture status
            </button>
          )}
          {job.state === "preview" && (
            <form
              className="kitchen-form"
              onSubmit={async (e) => {
                e.preventDefault();
                setBusy(true);
                try {
                  setJob(
                    await api<Job>(`pantry/captures/${job.id}`, "POST", {
                      items: rows,
                    }),
                  );
                  onApproved();
                } catch (e) {
                  setError(e);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <h3>Review each item</h3>
              {rows.map((r, i) => (
                <fieldset key={i}>
                  <legend>Item {i + 1}</legend>
                  <label>
                    Name
                    <input
                      required
                      value={r.name}
                      onChange={(e) =>
                        setRows(
                          rows.map((x, j) =>
                            j === i ? { ...x, name: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    Amount (optional)
                    <input
                      value={r.quantity}
                      onChange={(e) =>
                        setRows(
                          rows.map((x, j) =>
                            j === i ? { ...x, quantity: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </label>
                  <label>
                    Location
                    <input
                      required
                      value={r.location}
                      onChange={(e) =>
                        setRows(
                          rows.map((x, j) =>
                            j === i ? { ...x, location: e.target.value } : x,
                          ),
                        )
                      }
                    />
                  </label>
                  <button
                    type="button"
                    className="text-button"
                    onClick={() => setRows(rows.filter((_, j) => j !== i))}
                  >
                    Remove item {i + 1}
                  </button>
                </fieldset>
              ))}
              <button
                type="button"
                className="button secondary"
                onClick={() =>
                  setRows([
                    ...rows,
                    { name: "", quantity: "", location: "Pantry" },
                  ])
                }
              >
                Add another item
              </button>
              <button className="button" disabled={busy || rows.length === 0}>
                Approve items into pantry
              </button>
            </form>
          )}
          {job.state === "approved" && (
            <p>
              Approved items are in your pantry. Cooking will not deduct them
              automatically.
            </p>
          )}
          {job.state !== "cancelled" && (
            <button
              className="text-button"
              onClick={async () => {
                try {
                  await api(`pantry/captures/${job.id}`, "DELETE");
                  setJob(null);
                  setRows([]);
                  setKey(crypto.randomUUID());
                } catch (e) {
                  setError(e);
                }
              }}
            >
              Discard capture photo and preview
            </button>
          )}
        </>
      )}
    </details>
  );
}
