import { useEffect, useState } from "react";
import { LoaderCircle } from "../../icons";
export default function GenerationProgress({ message }: { message: string }) {
  const [seconds, setSeconds] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(
      () => setSeconds(Math.floor((Date.now() - started) / 1000)),
      1000,
    );
    return () => clearInterval(timer);
  }, []);
  return (
    <div className="generation-progress" role="status" aria-live="polite">
      <div className="row-between">
        <strong>
          <LoaderCircle size={18} className="spin" />
          Creating your look
        </strong>
        <span>{seconds}s elapsed</span>
      </div>
      <div
        className="indeterminate-progress"
        role="progressbar"
        aria-label="Try-on generation in progress"
      />
      <p data-testid="job-progress">{message}</p>
      <small>
        Warm research runs can take around 25–30 seconds. Queues, startup and
        network delays may take longer. You can refresh and return to this same
        job.
      </small>
    </div>
  );
}
