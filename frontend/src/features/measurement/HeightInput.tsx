import { useState } from "react";
export default function HeightInput({
  value,
  onChange,
  disabled = false,
}: {
  value: number;
  onChange: (value: number) => void;
  disabled?: boolean;
}) {
  const [unit, setUnit] = useState<"cm" | "ft">("cm");
  const total = Math.round((value / 2.54) * 10) / 10;
  const feet = Math.floor(total / 12);
  const inches = Math.round((total - feet * 12) * 10) / 10;
  return (
    <fieldset className="height-field" disabled={disabled}>
      <legend className="visually-hidden">Your height</legend>
      <div className="row-between">
        <strong>Your height</strong>
        <div className="segmented compact">
          <button
            type="button"
            aria-pressed={unit === "cm"}
            onClick={() => setUnit("cm")}
          >
            cm
          </button>
          <button
            type="button"
            aria-pressed={unit === "ft"}
            onClick={() => setUnit("ft")}
          >
            ft / in
          </button>
        </div>
      </div>
      {unit === "cm" ? (
        <div className="input-unit">
          <input
            aria-label="Height in centimeters"
            type="number"
            min={80}
            max={250}
            step="0.1"
            required
            value={value || ""}
            onChange={(e) => onChange(Number(e.target.value))}
          />
          <span>cm</span>
        </div>
      ) : (
        <div className="two-fields">
          <label className="input-unit">
            <input
              aria-label="Height feet"
              type="number"
              min={2}
              max={8}
              value={feet}
              onChange={(e) =>
                onChange(
                  Math.round(
                    (Number(e.target.value) * 12 + inches) * 2.54 * 10,
                  ) / 10,
                )
              }
            />
            <span>ft</span>
          </label>
          <label className="input-unit">
            <input
              aria-label="Height inches"
              type="number"
              min={0}
              max={11.9}
              step="0.1"
              value={inches}
              onChange={(e) =>
                onChange(
                  Math.round((feet * 12 + Number(e.target.value)) * 2.54 * 10) /
                    10,
                )
              }
            />
            <span>in</span>
          </label>
        </div>
      )}
      <small>Used to scale your photo. Enter your actual height.</small>
    </fieldset>
  );
}
