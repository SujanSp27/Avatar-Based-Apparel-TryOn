export const metricLabels = {
  shoulder_width: "Shoulder width",
  chest_circumference: "Chest circumference",
  waist_circumference: "Waist circumference",
  hip_circumference: "Hip circumference",
  thigh_circumference: "Thigh circumference",
  inseam_length: "Inseam length",
} as const;
export type Metric = keyof typeof metricLabels;
export type Measurements = Record<Metric, number>;
export type User = {
  id: string;
  name: string;
  email: string;
  height_cm: number | null;
  created_at: string;
  email_verified?: boolean;
  measurement_unit?: "cm" | "in";
};
export type Session = { access_token: string; expires_in: number; user: User };
export type Extraction = {
  measurement_id: string;
  scale_factor: number;
  measurements: Measurements;
  annotated_image_url: string;
  landmarks_normalized: number[][];
  warnings: string[];
  quality: { estimates_only: boolean; minimum_key_landmark_visibility: number };
  geometry: { image_size: [number, number]; height_cm: number };
};
export type ChartSummary = {
  brand_id: string;
  brand_name: string;
  apparel_id: string;
  category: string;
  version: number;
  gender: "men" | "women" | "unisex";
  market: string;
  is_demo: boolean;
  source: string;
  source_url: string | null;
  active_metrics: Metric[] | null;
  notes: string[];
};
export type Chart = ChartSummary & {
  sizes: {
    size_label: string;
    sort_order: number;
    bounds: Partial<Record<Metric, { lower: number; upper: number }>>;
  }[];
};
export type Brand = {
  brand_id: string;
  brand_name: string;
  recommendation_available: boolean;
  available_charts: ChartSummary[];
  coverage?: { gender: string; status?: string; note?: string }[];
};
export type Comparison = {
  measurement: number;
  lower: number;
  upper: number;
  midpoint: number;
  deviation: number;
  weighted_error: number;
  within_range: boolean;
};
export type Recommendation = {
  recommended_size: string;
  minimum_error: number;
  fit_confidence: number;
  size_rankings: {
    size: string;
    error: number;
    deviations: Partial<Record<Metric, number>>;
  }[];
  chart_comparison: Record<string, Partial<Record<Metric, Comparison>>>;
  active_weights: Partial<Record<Metric, number>>;
  chart: ChartSummary;
  warnings: string[];
  score_meaning: string;
};
export type SavedScan = {
  id: string;
  label: string;
  height_cm: number;
  measurements: Measurements;
  source: string;
  created_at: string;
  thumbnail_url: string | null;
};
export type SavedSize = {
  id: string;
  result: Recommendation;
  updated_at: string;
};
