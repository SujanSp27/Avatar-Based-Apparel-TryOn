import { useState } from "react";
import {
  metricLabels,
  type Measurements,
  type Metric,
} from "../../types/studio";
export const validMeasurements = (values?: Measurements) =>
  !!values &&
  (Object.keys(metricLabels) as Metric[]).every((key) => {
    const value = values[key];
    return (
      Number.isFinite(value) &&
      value > 0 &&
      value <=
        (key === "shoulder_width" ? 100 : key === "inseam_length" ? 200 : 400)
    );
  });
export default function MeasurementGrid({
  values,
  onChange,
}: {
  values?: Measurements;
  onChange: (values: Measurements) => void;
}) {
  const [edit, setEdit] = useState<Metric | null>(null);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  return (
    <div className="metric-grid">
      {(Object.keys(metricLabels) as Metric[]).map((key, index) => (
        <article className="metric-card" key={key}>
          <div className="row-between">
            <span className="metric-index">M{index + 1}</span>
            {values && (
              <button
                type="button"
                className="text-button"
                aria-label={`Edit ${metricLabels[key]}`}
                onClick={() => {
                  setEdit(key);
                  setDraft(values[key] ? String(values[key]) : "");
                  setError("");
                }}
              >
                Edit
              </button>
            )}
          </div>
          <span className="metric-name">{metricLabels[key]}</span>
          {edit === key && values ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                const updated = { ...values, [key]: Number(draft) };
                if (
                  !draft ||
                  !Number.isFinite(updated[key]) ||
                  updated[key] <= 0 ||
                  updated[key] >
                    (key === "shoulder_width"
                      ? 100
                      : key === "inseam_length"
                        ? 200
                        : 400)
                ) {
                  setError(
                    "Enter a positive measurement within the supported range.",
                  );
                  return;
                }
                onChange(updated);
                setEdit(null);
              }}
            >
              <div className="metric-edit">
                <input
                  autoFocus
                  type="number"
                  step=".1"
                  aria-label={`${metricLabels[key]} in centimeters`}
                  value={draft}
                  onChange={(e) => setDraft(e.target.value)}
                />
                <button className="text-button">Save</button>
                <button
                  type="button"
                  className="text-button"
                  onClick={() => setEdit(null)}
                >
                  Cancel
                </button>
              </div>
              {error && (
                <small role="alert" className="field-error">
                  {error}
                </small>
              )}
            </form>
          ) : (
            <div className="metric-value">
              {values?.[key] ? values[key].toFixed(1) : "—"}
              <small>cm</small>
            </div>
          )}
          <span className="metric-caption">
            {values
              ? "Review against a tape measure"
              : "Available after your scan"}
          </span>
        </article>
      ))}
    </div>
  );
}
