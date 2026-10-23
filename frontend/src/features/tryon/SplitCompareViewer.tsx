import { useEffect, useRef, useState, type CSSProperties, type PointerEvent } from "react";
import { Link } from "react-router-dom";
import { Download, Expand, LoaderCircle, RotateCw, Shirt, ZoomIn } from "../../icons";
import type { Result } from "../../types";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../components/ui/Toast";

type Props = { original?: string; result?: string; busy?: boolean; message?: string; details?: Result };
type Size = { width: number; height: number };

export default function SplitCompareViewer(props: Props) {
  // Reset only image loading when a pair changes; preserve the selected mode.
  const [mode, setMode] = useState<"split" | "side">("side");
  return <ComparisonImages key={`${props.original ?? ""}|${props.result ?? ""}`} {...props}
    mode={mode} onMode={setMode} />;
}
function ComparisonImages({ original, result, busy = false, message, details, mode, onMode }:
  Props & { mode: "split" | "side"; onMode: (mode: "split" | "side") => void }) {
  const [position, setPosition] = useState(50);
  const [zoom, setZoom] = useState(false);
  const [scale, setScale] = useState(1);
  const [sourceSize, setSourceSize] = useState<Size>();
  const [resultSize, setResultSize] = useState<Size>();
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [sharing, setSharing] = useState(false);
  const stage = useRef<HTMLDivElement>(null);
  const toast = useToast();
  const mismatch = !!(sourceSize && resultSize && (sourceSize.width !== resultSize.width || sourceSize.height !== resultSize.height));
  const ready = !!(original && result && sourceSize && resultSize && !failed && !mismatch);
  const paired = !!(original && result);
  useEffect(() => {
    if (!paired || ready || failed) return;
    const timer = setTimeout(() => setFailed(true), 15000);
    return () => clearTimeout(timer);
  }, [paired, ready, failed, retry]);
  const imageUrl = (url: string) => retry ? `${url}${url.includes("?") ? "&" : "?"}retry=${retry}` : url;
  function retryImages() { setFailed(false); setSourceSize(undefined); setResultSize(undefined); setRetry((n) => n + 1); }
  function drag(event: PointerEvent<HTMLInputElement>) {
    if (!ready || busy || !stage.current) return;
    const rect = stage.current.getBoundingClientRect();
    setPosition(Math.max(0, Math.min(100, (event.clientX - rect.left) / rect.width * 100)));
  }
  async function share() {
    if (!ready || busy) return;
    setSharing(true);
    try {
      const response = await fetch(result!, { signal: AbortSignal.timeout(15000) });
      if (!response.ok) throw new Error("The render could not be downloaded. Please retry.");
      const file = new File([await response.blob()], "formfit-tryon.png", { type: "image/png" });
      if (navigator.canShare?.({ files: [file] })) {
        await navigator.share({ files: [file], title: "My FormFit look" });
      } else {
        const link = new URL(result!, window.location.origin).href;
        if (!navigator.clipboard) throw new Error("Use Download render to share this image.");
        await navigator.clipboard.writeText(link);
        toast("Image link copied. This local link works where your studio is accessible.");
      }
    } catch (error) {
      if ((error as Error).name !== "AbortError") toast((error as Error).message);
    } finally { setSharing(false); }
  }
  const ratio = sourceSize ? sourceSize.width / sourceSize.height : 2 / 3;
  return <section className="comparison-card premium-comparison" data-testid="viewer" data-mode="2d" data-loaded={ready} aria-busy={busy || (paired && !ready && !failed && !mismatch)}>
    <header className="comparison-header">
      <div><h2>Your New Look</h2><p>Compare your original outfit with your virtual try-on.</p></div>
      <div className="comparison-controls" role="group" aria-label="Comparison view">
        <button disabled={!ready || busy} onClick={() => onMode("split")} aria-pressed={mode === "split"}>Slider</button>
        <button disabled={!ready || busy} onClick={() => onMode("side")} aria-pressed={mode === "side"}>Side by side</button>
      </div>
    </header>
    <div className="comparison-surface">
      {paired ? <div ref={stage} className={`compare-stage ${mode}`} style={{ "--photo-ratio": ratio, aspectRatio: mode === "side" ? ratio * 2 : ratio } as CSSProperties}>
        <div className="compare-original" style={{ visibility: ready ? "visible" : "hidden" }}>
          <img key={`before-${retry}`} src={imageUrl(original!)} alt="Original person photo" onLoad={(e) => setSourceSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })} onError={() => setFailed(true)} />
        </div>
        <div className="compare-result" style={{ visibility: ready && !busy ? "visible" : "hidden", clipPath: mode === "split" ? `inset(0 0 0 ${position}%)` : undefined }}>
          <img key={`after-${retry}`} src={imageUrl(result!)} alt="Generated virtual try-on" onLoad={(e) => setResultSize({ width: e.currentTarget.naturalWidth, height: e.currentTarget.naturalHeight })} onError={() => setFailed(true)} />
        </div>
        {ready && !busy && <><span className="compare-label before">Before</span><span className="compare-label after">After</span></>}
        {ready && !busy && mode === "split" && <>
          <div className="compare-divider" style={{ left: `${position}%` }} aria-hidden="true"><span>? <i /> ?</span></div>
          <input className="compare-range" type="range" min="0" max="100" step="0.1" value={position} onChange={(e) => setPosition(Number(e.target.value))}
            onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); drag(e); }}
            onPointerMove={(e) => { if (e.currentTarget.hasPointerCapture(e.pointerId)) drag(e); }}
            aria-label="Before and after comparison slider" aria-valuetext={`${Math.round(position)}% original photo`} />
        </>}
        {(!ready || busy) && <div className="comparison-state" role={failed || mismatch ? "alert" : "status"}>
          {failed || mismatch ? <><RotateCw size={25} /><h3>{mismatch ? "These images cannot be aligned" : "We could not load this comparison"}</h3><p>{mismatch ? "The result dimensions differ from the original. Generate a new try-on; the person will not be stretched or cropped." : "Your result is saved. Check the connection and reload the images."}</p>{!mismatch && <button className="button secondary" onClick={retryImages}>Retry images</button>}</> : <><LoaderCircle size={25} className="spin" /><h3>{busy ? "Creating your next look" : "Loading your comparison"}</h3><p>{busy ? message : "Preparing both images at the same scale."}</p></>}
        </div>}
      </div> : <div className="comparison-empty">
        {original && <img src={original} alt="Your selected person photo" />}
        <div>{busy ? <LoaderCircle size={30} className="spin" /> : <Shirt size={34} strokeWidth={1.3} />}<h3>{busy ? "Creating your next look" : original ? "Ready for a new look" : "Your fitting room awaits"}</h3><p>{busy ? message : "Choose a garment and generate your try-on. Your new outfit will appear here."}</p></div>
      </div>}
    </div>
    <footer className="comparison-footer">
      <button className="button secondary" disabled={!ready || busy} onClick={() => setZoom(true)}><ZoomIn size={17} />Inspect details</button>
      <div className="comparison-actions">
        <button className="button secondary" disabled={!ready || busy || sharing} onClick={() => void share()}>{sharing ? "Sharing?" : "Share"}</button>
        {ready && !busy ? <a className="button" href={result} download="formfit-tryon.png"><Download size={17} />Download render</a> : <button className="button" disabled><Download size={17} />Download render</button>}
      </div>
    </footer>
    <Modal wide open={zoom && ready && !busy} onClose={() => setZoom(false)} title="Outfit & fit details">
      <div className="outfit-details"><div><strong>{details?.garmentCategory?.replaceAll("-", " ") ?? "Virtual try-on"}</strong><p>Original framing ? {sourceSize?.width} ? {sourceSize?.height} pixels</p></div><div><strong>About your fit</strong><p>This image previews appearance. Measurements and brand sizes are calculated separately.</p><Link to="/sizing">View my size recommendations <span aria-hidden="true">?</span></Link></div></div>
      <label className="zoom-control"><Expand size={16} />Zoom<input type="range" min="1" max="3" step=".25" value={scale} onChange={(e) => setScale(Number(e.target.value))} />{scale}?</label>
      <div className="zoom-scroll"><img src={result} alt="Generated outfit at adjustable zoom" style={{ width: `${scale * 100}%`, maxWidth: "none" }} /></div>
    </Modal>
  </section>;
}
