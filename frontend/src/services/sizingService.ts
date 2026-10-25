import { api, jsonBody } from "./api/client";
import type {
  Brand,
  Chart,
  ChartSummary,
  Measurements,
  Recommendation,
  SavedSize,
} from "../types/studio";
const payload = (chart: ChartSummary, measurements: Measurements) => ({
  brand_id: chart.brand_id,
  apparel_id: chart.apparel_id,
  chart_version: chart.version,
  measurements: Object.fromEntries(
    Object.entries(measurements).filter(
      ([key, value]) =>
        value > 0 &&
        (!chart.active_metrics ||
          chart.active_metrics.includes(key as keyof Measurements)),
    ),
  ),
});
export const sizingService = {
  brands: () => api<Brand[]>("/api/v1/sizing/brands?include_demo=true"),
  chart: (chart: ChartSummary) =>
    api<Chart>(
      `/api/v1/sizing/charts/${chart.brand_id}/${chart.apparel_id}?version=${chart.version}`,
    ),
  recommend: (chart: ChartSummary, measurements: Measurements) =>
    api<Recommendation>(
      "/api/v1/sizing/recommend",
      jsonBody(payload(chart, measurements)),
    ),
  save: (chart: ChartSummary, measurements: Measurements) =>
    api<SavedSize>(
      "/api/v1/profile/sizes",
      jsonBody(payload(chart, measurements)),
    ),
  saved: () => api<SavedSize[]>("/api/v1/profile/sizes"),
  remove: (id: string) =>
    api<void>(`/api/v1/profile/sizes/${id}`, { method: "DELETE" }),
};
