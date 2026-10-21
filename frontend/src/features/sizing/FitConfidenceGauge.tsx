export default function FitConfidenceGauge({ value }: { value: number }) {
  const bounded = Math.max(0, Math.min(100, value));
  const color =
    bounded >= 90 ? "#205a46" : bounded >= 75 ? "#897118" : "#a65b20";
  return (
    <div className="confidence">
      <div
        className="gauge"
        role="meter"
        aria-label="Heuristic fit confidence"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={bounded}
      >
        <svg viewBox="0 0 120 120" aria-hidden="true">
          <circle cx="60" cy="60" r="49" className="gauge-track" />
          <circle
            cx="60"
            cy="60"
            r="49"
            pathLength="100"
            stroke={color}
            strokeDasharray={`${bounded} 100`}
            className="gauge-value"
          />
        </svg>
        <strong>
          {bounded.toFixed(1)}
          <small>%</small>
        </strong>
      </div>
      <div>
        <span className="eyebrow">FIT CONFIDENCE</span>
        <h3>
          {bounded >= 90
            ? "Ideal Tailored Fit"
            : bounded >= 75
              ? "Standard Comfortable Fit"
              : "Borderline Fit — Review Measurements"}
        </h3>
        <p>
          Chart similarity score · not a calibrated probability or guarantee of
          fit.
        </p>
      </div>
    </div>
  );
}
