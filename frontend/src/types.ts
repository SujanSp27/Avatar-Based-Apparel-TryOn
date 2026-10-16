export type Brand = { id: number; name: string; slug: string; isDemo: boolean };
export type VtonAvailability = {
  available: boolean;
  reason: string | null;
  backend: string;
  nativeResolution: [number, number];
  supportedCategories: string[];
  inferenceSteps: number;
  connectionState?: string;
  automaticConnection?: boolean;
};
export type Result = {
  status: string; mode: "2d"; renderingMethod: "pretrained-vton";
  runId: string; previewUrl: string; originalUrl: string;
  garmentCategory: string; timingSeconds: number;
  provenance: { backend: string; execution?: string };
  warnings: string[]; artifacts: Record<string, string>;
};
export async function apiError(response: Response): Promise<string> {
  const data = await response.json().catch(() => null);
  return data?.error?.message ?? (typeof data?.detail === "string" ? data.detail :
    "The request failed. Please check your inputs and try again.");
}
