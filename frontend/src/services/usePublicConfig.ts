import { useEffect, useState } from "react";
type Configuration = {
  sample_photos: boolean;
  email_verification_required: boolean;
  guest_retention_hours: number;
  generated_retention_days: number;
};
let pending: Promise<Configuration> | undefined;
export function usePublicConfig() {
  const [config, setConfig] = useState<Configuration>();
  useEffect(() => {
    let stopped = false;
    pending ??= fetch("/api/v1/public-config", {
      signal: AbortSignal.timeout(8000),
    }).then((r) => {
      if (!r.ok) throw new Error("configuration");
      return r.json();
    });
    pending
      .then((c) => {
        if (!stopped) setConfig(c);
      })
      .catch(() => {
        pending = undefined;
      });
    return () => {
      stopped = true;
    };
  }, []);
  return config;
}
