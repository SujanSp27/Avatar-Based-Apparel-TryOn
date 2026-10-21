import {
  metricLabels,
  type Recommendation,
  type Metric,
} from "../../types/studio";
export default function DeviationHeatmap({
  result,
  size,
}: {
  result: Recommendation;
  size: string;
}) {
  const rows = result.chart_comparison[size];
  if (!rows) return null;
  return (
    <div className="deviation-table">
      <div className="deviation-head">
        <span>MEASUREMENT</span>
        <span>YOUR VALUE / CHART</span>
        <span>FIT INDICATOR</span>
      </div>
      {(
        Object.entries(rows) as [Metric, NonNullable<(typeof rows)[Metric]>][]
      ).map(([key, value]) => {
        const state =
          value.measurement > value.upper
            ? "tight"
            : value.measurement < value.lower
              ? "loose"
              : "optimal";
        return (
          <div className="deviation-row" key={key}>
            <div>
              <strong>{metricLabels[key]}</strong>
              <small>
                {(value.deviation * 100).toFixed(1)}% from midpoint · weight{" "}
                {(result.active_weights[key]! * 100).toFixed(1)}%
              </small>
            </div>
            <div>
              <strong>
                {value.measurement.toFixed(1)} <small>cm</small>
              </strong>
              <small>
                {value.lower.toFixed(1)} – {value.upper.toFixed(1)} cm
              </small>
            </div>
            <span className={`fit-tag ${state}`}>
              {state === "tight"
                ? "Runs Tight"
                : state === "loose"
                  ? "Runs Loose"
                  : "Optimal"}
            </span>
          </div>
        );
      })}
    </div>
  );
}
