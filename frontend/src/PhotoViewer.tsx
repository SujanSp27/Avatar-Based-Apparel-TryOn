import { useRef, useState } from "react";
import { Download, Expand, Shirt } from "./icons";

export default function PhotoViewer({
  previewUrl,
  originalUrl,
  busy,
}: {
  previewUrl?: string;
  originalUrl?: string;
  busy: boolean;
}) {
  const [view, setView] = useState<"tryon" | "original">("tryon");
  const [loadedUrl, setLoadedUrl] = useState("");
  const [failedUrl, setFailedUrl] = useState("");
  const container = useRef<HTMLDivElement>(null);
  const url = view === "original" ? originalUrl : previewUrl;
  const loaded = !!url && loadedUrl === url;

  return (
    <div
      ref={container}
      className="viewer photo-viewer"
      data-testid="viewer"
      data-mode="2d"
      data-loaded={loaded}
    >
      <div className="viewer-top">
        <span className="eyebrow">
          {previewUrl ? "YOUR 2D TRY-ON RESULT" : "2D VIRTUAL TRY-ON"}
        </span>
        <button
          className="icon-button"
          title="Full screen"
          aria-label="Full screen viewer"
          onClick={() => {
            if (document.fullscreenElement) void document.exitFullscreen();
            else void container.current?.requestFullscreen();
          }}
        >
          <Expand size={17} />
        </button>
      </div>
      {url ? (
        <div className="photo-stage">
          <img
            key={url}
            src={url}
            alt={
              view === "original"
                ? "Original person photo"
                : "2D virtual try-on result"
            }
            onLoad={() => setLoadedUrl(url)}
            onError={() => setFailedUrl(url)}
          />
          {failedUrl === url && (
            <p className="viewer-error" role="alert">
              This try-on image could not be loaded. Generate again to retry.
            </p>
          )}
          {!loaded && failedUrl !== url && (
            <span className="photo-loading" role="status">
              Loading try-on image…
            </span>
          )}
        </div>
      ) : (
        <div className="photo-placeholder">
          <span className="photo-placeholder-icon">
            <Shirt size={56} strokeWidth={1.1} />
          </span>
          <h3>Your photo. A different look.</h3>
          <p>Add a front-facing photo with your shoulders and torso visible.</p>
        </div>
      )}
      {busy && (
        <div className="busy-view" role="status">
          <div className="spinner" />
          <strong>Generating your try-on</strong>
          <p>Running the pretrained garment replacement model…</p>
        </div>
      )}
      <div className="viewer-bottom">
        <div className="view-tabs" aria-label="Photo comparison">
          <button
            disabled={!originalUrl || busy}
            className={view === "original" ? "active" : ""}
            aria-pressed={view === "original"}
            onClick={() => setView("original")}
          >
            Original
          </button>
          <button
            disabled={!previewUrl || busy}
            className={view === "tryon" ? "active" : ""}
            aria-pressed={view === "tryon"}
            onClick={() => setView("tryon")}
          >
            Try-on
          </button>
        </div>
        <div className="viewer-hints">
          <span>Generated image · compare garment and identity details</span>
        </div>
      </div>
      {previewUrl && (
        <a
          className="download-model"
          href={previewUrl}
          download
          aria-label="Download try-on PNG"
        >
          <Download size={14} /> PNG
        </a>
      )}
    </div>
  );
}
