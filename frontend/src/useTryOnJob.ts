import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { apiError, type Result } from "./types";

const KEY = "form-fit-last-job";
const JOB_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
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
  uploading_online: "Sending images to your Colab worker",
  online_generating: "Your Colab GPU is generating the outfit",
  online_reconnecting: "Reconnecting to your existing generation; your images will not be resubmitted",
};

function savedJob(): string | undefined {
  try {
    const id = localStorage.getItem(KEY);
    return id && JOB_ID.test(id) ? id : undefined;
  } catch { return undefined; }
}

function forgetJob() {
  try { localStorage.removeItem(KEY); } catch { /* storage may be disabled */ }
}

export function useTryOnJob(onResult: (result: Result | undefined) => void, onError: (message: string) => void) {
  const [searchParams, setSearchParams] = useSearchParams();
  const linkedJob = searchParams.get("job");
  const [jobId, setJobId] = useState<string | undefined>(() =>
    linkedJob && JOB_ID.test(linkedJob) ? linkedJob : savedJob(),
  );
  const [busy, setBusy] = useState(!!jobId);
  const [message, setMessage] = useState(jobId ? "Recovering your previous try-on" : "");
  const submitting = useRef(false);
  const selection = useRef(0);
  const callbacks = useRef({ onResult, onError });
  callbacks.current = { onResult, onError };

  useEffect(() => {
    if (!linkedJob || !JOB_ID.test(linkedJob) || submitting.current) return;
    // Open an existing result through its real API job, including during a GPU
    // outage. Consume the link so a later generation survives page refresh.
    try { localStorage.setItem(KEY, linkedJob); } catch { /* retain in memory */ }
    setJobId(linkedJob);
    setBusy(true);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.delete("job");
      return next;
    }, { replace: true });
  }, [linkedJob, setSearchParams]);

  useEffect(() => {
    if (!jobId) return;
    const version = selection.current;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let missing = 0;
    let controller: AbortController;
    let failures = 0;
    async function poll() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const response = await fetch(`/api/tryon/jobs/${jobId}`, { signal: controller.signal });
        if (stopped || version !== selection.current) return;
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
        failures = 0;
        if (stopped || version !== selection.current) return;
        if (job.status === "success" || job.status === "failed") {
          setBusy(false); setJobId(undefined); setMessage("");
          if (job.status === "failed") {
            forgetJob();
            callbacks.current.onError(job.error?.message ?? "Try-on failed.");
          }
          else if (!job.result || job.result.mode !== "2d" || job.result.renderingMethod !== "pretrained-vton") {
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
        if (stopped || version !== selection.current) return;
        failures++;
        setMessage("Connection interrupted. Reconnecting to the same job; no duplicate will be started.");
      } finally {
        clearTimeout(timeout);
      }
      if (!stopped) timer = setTimeout(poll, Math.min(15000, 2000 * 2 ** Math.min(failures, 3)));
    }
    void poll();
    return () => { stopped = true; controller?.abort(); clearTimeout(timer); };
  }, [jobId]);

  async function submit(form: FormData) {
    if (busy || submitting.current) return;
    const id = crypto.randomUUID();
    callbacks.current.onResult(undefined);
    submitting.current = true;
    setBusy(true); setMessage("Uploading your photos"); setJobId(id);
    try { localStorage.setItem(KEY, id); } catch { /* still track the live job */ }
    try {
      const response = await fetch("/api/tryon", {
        method: "POST", body: form,
        headers: { Prefer: "respond-async", "Idempotency-Key": id },
        signal: AbortSignal.timeout(45000),
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
  function reset() {
    if (submitting.current) return;
    selection.current++;
    forgetJob();
    setJobId(undefined); setBusy(false); setMessage("");
    callbacks.current.onResult(undefined);
    callbacks.current.onError("");
  }
  return { busy, message, submit, reset };
}
