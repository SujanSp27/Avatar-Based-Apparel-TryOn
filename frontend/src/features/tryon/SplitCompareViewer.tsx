import { useState } from "react";
import { Download, Expand, Shirt, ZoomIn } from "../../icons";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../components/ui/Toast";
export default function SplitCompareViewer({
  original,
  result,
}: {
  original?: string;
  result?: string;
}) {
  const [mode, setMode] = useState<"split" | "side">("split");
  const [position, setPosition] = useState(50);
  const [zoom, setZoom] = useState(false);
  const [scale, setScale] = useState(1);
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const toast = useToast();
  async function share() {
    try {
      const response = await fetch(result!);
      if (!response.ok) throw new Error("The render could not be downloaded.");
      const file = new File([await response.blob()], "formfit-tryon.png", {
        type: "image/png",
      });
      if (navigator.canShare?.({ files: [file] }))
        await navigator.share({ files: [file], title: "My FormFit look" });
      else
        toast(
          "Sharing is not supported here. Download the render to share it.",
        );
    } catch (e) {
      if ((e as Error).name !== "AbortError") toast((e as Error).message);
    }
  }
  return (
    <section
      className="comparison-card"
      data-testid="viewer"
      data-mode="2d"
      data-loaded={loaded}
    >
      <div className="photo-card-top">
        <span className="small-caps">THE SAME YOU. A NEW LOOK.</span>
        <div className="segmented compact">
          <button
            disabled={!result}
            onClick={() => setMode("split")}
            aria-pressed={mode === "split"}
          >
            Slider
          </button>
          <button
            disabled={!result}
            onClick={() => setMode("side")}
            aria-pressed={mode === "side"}
          >
            Side by side
          </button>
        </div>
      </div>
      {result && original ? (
        <>
          <div className={`compare-stage ${mode}`}>
            <div className="compare-original">
              <img
                src={original}
                alt="Original person photo"
                onError={() => setFailed(true)}
              />
              <span>BEFORE</span>
            </div>
            <div
              className="compare-result"
              style={
                mode === "split"
                  ? { clipPath: `inset(0 0 0 ${position}%)` }
                  : undefined
              }
            >
              <img
                src={result}
                alt="Generated virtual try-on"
                onLoad={() => setLoaded(true)}
                onError={() => setFailed(true)}
              />
              <span>AFTER</span>
            </div>
            {mode === "split" && (
              <>
                <div
                  className="compare-divider"
                  style={{ left: `${position}%` }}
                >
                  <span>‹ ›</span>
                </div>
                <input
                  className="compare-range"
                  type="range"
                  min="0"
                  max="100"
                  value={position}
                  onChange={(e) => setPosition(Number(e.target.value))}
                  aria-label="Before and after comparison slider"
                />
              </>
            )}
          </div>
          {failed && (
            <p role="alert" className="notice error">
              This image could not load. Please check the app connection.
            </p>
          )}
          <div className="photo-card-footer">
            <button className="text-button" onClick={() => setZoom(true)}>
              <ZoomIn size={16} />
              Inspect details
            </button>
            <div className="actions">
              <button className="text-button" onClick={() => void share()}>
                Share
              </button>
              <a
                className="button small"
                href={result}
                download="formfit-tryon.png"
              >
                <Download size={15} />
                Download render
              </a>
            </div>
          </div>
          <Modal
            wide
            open={zoom}
            onClose={() => setZoom(false)}
            title="A closer look"
          >
            <label className="zoom-control">
              <Expand size={16} />
              Zoom
              <input
                type="range"
                min="1"
                max="3"
                step=".25"
                value={scale}
                onChange={(e) => setScale(Number(e.target.value))}
              />
              {scale}×
            </label>
            <div className="zoom-scroll">
              <img
                src={result}
                alt="Generated outfit at adjustable zoom"
                style={{ width: `${scale * 100}%`, maxWidth: "none" }}
              />
            </div>
          </Modal>
        </>
      ) : (
        <div className="tryon-empty">
          {original ? (
            <img src={original} alt="Your selected person photo" />
          ) : (
            <>
              <div className="tryon-orbit">
                <Shirt size={72} strokeWidth={0.8} />
              </div>
              <span className="eyebrow">YOUR VIRTUAL FITTING ROOM</span>
              <h2>Imagine the possibilities.</h2>
              <p>
                Add your photo and a garment.
                <br />
                See the look, before you commit.
              </p>
              <div className="mini-tags">
                <span>Your original photo</span>
                <span>Real garment conditioning</span>
              </div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
