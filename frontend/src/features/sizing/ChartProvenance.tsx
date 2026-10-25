import type { ChartSummary } from "../../types/studio";
export function marketName(market: string) {
  return (
    (
      {
        IN: "India",
        GB: "United Kingdom",
        US: "United States",
        XK: "Kosovo",
        UNSPECIFIED: "Unspecified market",
      } as Record<string, string>
    )[market] ?? market
  );
}
export default function ChartProvenance({ chart }: { chart: ChartSummary }) {
  return (
    <div className="chart-provenance">
      <strong>
        {chart.is_demo
          ? "Demonstration data"
          : chart.verification_status === "verified"
            ? "Source verified"
            : "Unverified / user-supplied guide"}
      </strong>
      <p>
        {marketName(chart.market)} · {chart.sizing_system || "Brand labels"}
        <br />
        {chart.measurement_basis === "garment"
          ? "Garment dimensions — not scored against body measurements"
          : "Body measurements"}
        {chart.checked_on && <> · Checked {chart.checked_on}</>}
      </p>
      <p>{chart.source}</p>
      {chart.source_url && (
        <a href={chart.source_url} target="_blank" rel="noreferrer">
          View {chart.source_type === "official" ? "official" : "original"}{" "}
          source ↗
        </a>
      )}
      <p className="fine-print">
        Regional size labels are not automatically converted. Chart matching is
        separate from AI try-on and does not guarantee fit.
      </p>
    </div>
  );
}
