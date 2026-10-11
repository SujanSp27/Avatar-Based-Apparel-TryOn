export type Brand = { id: number; name: string; slug: string; isDemo: boolean };
export type TryonMode = "auto" | "3d" | "2d";
export type VtonAvailability = {
  available: boolean;
  reason: string | null;
  backend: string;
  nativeResolution: [number, number];
};

type ResultBase = {
  status: string;
  runId: string;
  brandId: number;
  brandName: string;
  garmentCategory: string;
  fit: string;
  explanation: Record<string, string>;
  warnings: string[];
  previewUrl: string;
  provenance: {
    backend: string;
    shapeRecovery: string;
    validatedAnthropometry: boolean;
  };
  chartVersion: number;
  timingSeconds: number;
  candidates: { sizeLabel: string; score: number }[];
  artifacts: Record<string, string>;
};

export type Result3D = ResultBase & {
  mode: "3d";
  recommendedSize: string;
  score: number;
  measurements: Record<string, number | string | Record<string, number>>;
  avatarUrl: string;
  bodyUrl: string;
  garmentUrl: string;
};

export type Result2D = ResultBase & {
  mode: "2d";
  renderingMethod: "pretrained-vton";
  recommendedSize: null;
  score: null;
  measurements: null;
  avatarUrl: null;
  bodyUrl: null;
  garmentUrl: null;
  originalUrl: string;
  fallbackReason: { code: string; message: string } | null;
};

export type Result = Result3D | Result2D;

export async function apiError(response: Response): Promise<string> {
  const data = await response.json().catch(() => null);
  return (
    data?.error?.message ??
    (typeof data?.detail === "string"
      ? data.detail
      : "The request failed. Please check your inputs and try again.")
  );
}
