import { api, jsonBody } from "./api/client";
import type {
  Brand,
  Chart,
  ChartSummary,
  Measurements,
  Recommendation,
  SavedSize,
  Extraction,
  Metric,
} from "../types/studio";
const payload = (
  chart: ChartSummary,
  measurements: Measurements,
  extraction?: Extraction,
  reviewed: Metric[] = [],
) => ({
  brand_id: chart.brand_id,
  apparel_id: chart.apparel_id,
  chart_version: chart.version,
  ...(extraction?.measurement_id
    ? {
        measurement_id: extraction.measurement_id,
        measurement_overrides: Object.fromEntries(
          reviewed
            .filter(
              (key) =>
                measurements[key] > 0 &&
                (!chart.active_metrics || chart.active_metrics.includes(key)),
            )
            .map((key) => [key, measurements[key]]),
        ),
      }
    : {
        measurements: Object.fromEntries(
          Object.entries(measurements).filter(
            ([key, value]) =>
              value > 0 &&
              (!chart.active_metrics ||
                chart.active_metrics.includes(key as keyof Measurements)),
          ),
        ),
      }),
});
export const sizingService = {
  brands: () => api<Brand[]>("/api/v1/sizing/brands?include_demo=true"),
  chart: (chart: ChartSummary) =>
    api<Chart>(
      `/api/v1/sizing/charts/${chart.brand_id}/${chart.apparel_id}?version=${chart.version}`,
    ),
  recommend: (
    chart: ChartSummary,
    measurements: Measurements,
    extraction?: Extraction,
    reviewed?: Metric[],
  ) =>
    api<Recommendation>(
      "/api/v1/sizing/recommend",
      jsonBody(payload(chart, measurements, extraction, reviewed)),
    ),
  save: (
    chart: ChartSummary,
    measurements: Measurements,
    extraction?: Extraction,
    reviewed?: Metric[],
  ) =>
    api<SavedSize>(
      "/api/v1/profile/sizes",
      jsonBody(payload(chart, measurements, extraction, reviewed)),
    ),
  saved: () => api<SavedSize[]>("/api/v1/profile/sizes"),
  remove: (id: string) =>
    api<void>(`/api/v1/profile/sizes/${id}`, { method: "DELETE" }),
};
