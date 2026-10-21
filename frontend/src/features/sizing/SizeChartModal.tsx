import Modal from "../../components/ui/Modal";
import { metricLabels, type Chart, type Metric } from "../../types/studio";
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
  const metrics = Object.keys(chart.sizes[0].bounds) as Metric[];
  return (
    <Modal
      wide
      open={open}
      onClose={onClose}
      title={`${chart.brand_name} · Size guide`}
    >
      <p className="muted">
        {chart.gender} · {chart.category} · India · version {chart.version} ·
        body ranges in cm
      </p>
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
                      ? `${size.bounds[key]!.lower.toFixed(1)} – ${size.bounds[key]!.upper.toFixed(1)}`
                      : "Not provided"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
