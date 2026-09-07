import { ApiError } from "../api";
export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div className="error" role="alert">
      {error instanceof Error ? error.message : String(error)}
      {error instanceof ApiError &&
        Object.entries(error.fields).map(([key, values]) => (
          <p key={key} id={`field-error-${key}`}>
            <strong>{key.replaceAll("_", " ")}:</strong>{" "}
            {Array.isArray(values) ? values.join(" ") : String(values)}
          </p>
        ))}
    </div>
  );
}
