import { useEffect, useRef, useState } from "react";
import { apiError, type Result } from "./types";

const KEY = "form-fit-last-job";
type Job = {
  jobId: string;
  status: "queued" | "processing" | "success" | "failed";
  result?: Result;
  error?: { message: string };
  elapsedSeconds?: number;
  progress?: { stage: string; completed?: number; total?: number };
};
const stages: Record<string, string> = {
  queued: "Waiting to start",
  preprocessing: "Checking the uploaded photos",
  loading_model: "Loading the try-on model",
  parsing_person: "Finding clothing and protected body regions",
  preparing_garment: "Preparing your garment",
  encoding_images: "Preparing images for generation",
  generating: "Generating your try-on",
  checking_output: "Checking the generated image",
  refining_boundaries: "Refining clothing edges and preserving identity",
  saving_result: "Saving your result",
};

function savedJob(): string | undefined {
  try {
    const id = localStorage.getItem(KEY);
    return id && /^[0-9a-f-]{36}$/i.test(id) ? id : undefined;
  } catch { return undefined; }
}

function forgetJob() {
  try { localStorage.removeItem(KEY); } catch { /* storage may be disabled */ }
}

export function useTryOnJob(onResult: (result: Result) => void, onError: (message: string) => void) {
  const [jobId, setJobId] = useState<string | undefined>(savedJob);
  const [busy, setBusy] = useState(!!jobId);
  const [message, setMessage] = useState(jobId ? "Recovering your previous try-on" : "");
  const submitting = useRef(false);
  const callbacks = useRef({ onResult, onError });
  callbacks.current = { onResult, onError };

  useEffect(() => {
    if (!jobId) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let missing = 0;
    const controller = new AbortController();
    async function poll() {
      try {
        const response = await fetch(`/api/tryon/jobs/${jobId}`, { signal: controller.signal });
        if (stopped) return;
        if (response.status === 404 && (submitting.current || missing++ < 5)) {
          timer = setTimeout(poll, 2000);
          return;
        }
        if (!response.ok) {
          if (response.status >= 500) throw new Error("connection");
          callbacks.current.onError(await apiError(response));
          setBusy(false); setJobId(undefined); forgetJob();
          return;
        }
        const job: Job = await response.json();
        if (stopped) return;
        if (job.status === "success" || job.status === "failed") {
          setBusy(false); setJobId(undefined); setMessage("");
          if (job.status === "failed") {
            forgetJob();
            callbacks.current.onError(job.error?.message ?? "Try-on failed.");
          }
          else if (!job.result || (job.result.mode === "2d" && job.result.renderingMethod !== "pretrained-vton")) {
            forgetJob();
            callbacks.current.onError("The service did not return a pretrained try-on result.");
          } else callbacks.current.onResult(job.result);
          return;
        }
        const progress = job.progress;
        const steps = progress?.total ? ` · step ${progress.completed ?? 0} of ${progress.total}` : "";
        const elapsed = job.elapsedSeconds ? ` · ${Math.round(job.elapsedSeconds)}s elapsed` : "";
        setMessage(`${stages[progress?.stage ?? "queued"] ?? "Processing your try-on"}${steps}${elapsed}`);
      } catch {
        if (stopped) return;
        setMessage("Connection interrupted. Reconnecting to the same job; no duplicate will be started.");
      }
      if (!stopped) timer = setTimeout(poll, 2000);
    }
    void poll();
    return () => { stopped = true; controller.abort(); clearTimeout(timer); };
  }, [jobId]);

  async function submit(form: FormData) {
    if (busy || submitting.current) return;
    const id = crypto.randomUUID();
    submitting.current = true;
    setBusy(true); setMessage("Uploading your photos"); setJobId(id);
    try { localStorage.setItem(KEY, id); } catch { /* still track the live job */ }
    try {
      const response = await fetch("/api/tryon", {
        method: "POST", body: form,
        headers: { Prefer: "respond-async", "Idempotency-Key": id },
      });
      if (!response.ok) {
        callbacks.current.onError(await apiError(response));
        setBusy(false); setJobId(undefined);
        forgetJob();
      }
      // The response only acknowledges the job. Polling retrieves the real result.
    } catch {
      setMessage("Checking whether your upload was received. No duplicate request will be sent.");
    } finally { submitting.current = false; }
  }
  return { busy, message, submit };
}
