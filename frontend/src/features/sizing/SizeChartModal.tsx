import Modal from "../../components/ui/Modal";
import { useState } from "react";
import { useAuth } from "../auth/AuthProvider";
import { metricLabels, type Chart, type Metric } from "../../types/studio";
import ChartProvenance, { marketName } from "./ChartProvenance";
export default function SizeChartModal({
  chart,
  open,
  onClose,
  selected,
  onSelect,
}: {
  chart: Chart;
  open: boolean;
  onClose: () => void;
  selected?: string;
  onSelect: (size: string) => void;
}) {
  const { user } = useAuth();
  const [unit, setUnit] = useState<"cm" | "in">(user?.measurement_unit ?? "cm");
  const display = (n: number) => (unit === "in" ? n / 2.54 : n).toFixed(1);
  const metrics = Object.keys(chart.sizes[0].bounds) as Metric[];
  return (
    <Modal
      wide
      open={open}
      onClose={onClose}
      title={`${chart.brand_name} · Size guide`}
    >
      <p className="muted">
        {chart.gender} · {chart.category} · {marketName(chart.market)} · version{" "}
        {chart.version} ·{chart.measurement_basis ?? "body"} measurements in{" "}
        {unit}
      </p>
      <label className="field">
        Display units
        <select
          value={unit}
          onChange={(e) => setUnit(e.target.value as "cm" | "in")}
        >
          <option value="cm">Centimetres</option>
          <option value="in">Inches</option>
        </select>
      </label>
      <div className="table-scroll">
        <table>
          <caption className="visually-hidden">
            Select a size to compare its measurement ranges
          </caption>
          <thead>
            <tr>
              <th scope="col">Size</th>
              {metrics.map((key) => (
                <th scope="col" key={key}>
                  {metricLabels[key]}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {chart.sizes.map((size) => (
              <tr
                key={size.size_label}
                data-selected={selected === size.size_label}
              >
                <th scope="row">
                  <button
                    className="size-label-button"
                    aria-pressed={selected === size.size_label}
                    onClick={() => onSelect(size.size_label)}
                  >
                    {size.size_label}
                  </button>
                </th>
                {metrics.map((key) => (
                  <td key={key}>
                    {size.bounds[key]
                      ? size.bounds[key]!.lower === size.bounds[key]!.upper
                        ? display(size.bounds[key]!.lower)
                        : `${display(size.bounds[key]!.lower)} – ${display(size.bounds[key]!.upper)}`
                      : "Not provided"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <ChartProvenance chart={chart} />
      {chart.notes.map((note) => (
        <p className="fine-print" key={note}>
          {note}
        </p>
      ))}
      <p className="fine-print">
        {chart.is_demo
          ? "Fictional demonstration chart. Do not use it as retailer sizing advice."
          : chart.source}
      </p>
      {chart.source_url && (
        <a
          className="text-button"
          href={chart.source_url}
          target="_blank"
          rel="noreferrer"
        >
          View the original size guide ↗
        </a>
      )}
    </Modal>
  );
}
