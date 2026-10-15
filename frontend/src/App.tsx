import { useCallback, useEffect, useState } from "react";
import { ArrowDownToLine, ArrowRight, CircleHelp, FlaskConical, LoaderCircle, Shirt, Sparkles, X } from "./icons";
import PhotoViewer from "./PhotoViewer";
import UploadCard from "./UploadCard";
import SizeRecommendation from "./SizeRecommendation";
import { useTryOnJob } from "./useTryOnJob";
import { apiError, type Result, type VtonAvailability } from "./types";

const categories = [
  ["t-shirt", "T-shirt"], ["shirt", "Shirt"], ["blouse", "Blouse"],
  ["sweater", "Sweater"], ["jacket", "Jacket"], ["trouser", "Trousers"],
  ["jeans", "Jeans"], ["shorts", "Shorts"], ["skirt", "Skirt"],
  ["dress", "Dress"], ["jumpsuit", "Jumpsuit"],
];

export default function App() {
  const [person, setPerson] = useState<File>();
  const [garment, setGarment] = useState<File>();
  const [category, setCategory] = useState("t-shirt");
  const [photoType, setPhotoType] = useState("flat-lay");
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState("");
  const [help, setHelp] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [vton, setVton] = useState<VtonAvailability>();
  const [checking, setChecking] = useState(false);
  const { busy, message, submit } = useTryOnJob(setResult, setError);
  const checkWorker = useCallback(async () => {
    setChecking(true);
    try {
      const r = await fetch("/api/health");
      if (!r.ok) throw new Error(await apiError(r));
      setVton((await r.json()).vton2d);
    } catch { setError("The local API could not be reached."); }
    finally { setChecking(false); }
  }, []);
  useEffect(() => { void checkWorker(); }, [checkWorker]);
  async function demo() {
    setDemoBusy(true); setError("");
    try {
      const responses = await Promise.all([fetch("/api/samples/person"), fetch("/api/samples/garment")]);
      if (responses.some(r => !r.ok)) throw new Error("Sample photos are unavailable.");
      const [p, g] = await Promise.all(responses.map(r => r.blob()));
      setPerson(new File([p], "studio-person.jpg", { type: "image/jpeg" }));
      setGarment(new File([g], "garment-demo.png", { type: "image/png" }));
      setCategory("t-shirt"); setPhotoType("flat-lay");
    } catch (e) { setError((e as Error).message); }
    finally { setDemoBusy(false); }
  }
  async function generate() {
    if (!person || !garment || !vton?.available) return;
    setError(""); setResult(undefined);
    const form = new FormData();
    form.append("personImage", person); form.append("garmentImage", garment);
    form.append("garmentCategory", category); form.append("garmentPhotoType", photoType);
    await submit(form);
  }
  return <>
    <header className="header">
      <a className="wordmark" href="/" aria-label="Form Fit home"><span className="logo-symbol"><Shirt size={21}/></span>form<span className="wordmark-slash">/</span>fit<span className="wordmark-studio">STUDIO</span></a>
      <nav><span className="nav-active">Virtual try-on</span><button onClick={() => setHelp(true)}>About the prototype <CircleHelp size={14}/></button></nav>
      <span className="research-tag">ONLINE GPU</span>
    </header>
    <main>
      <section className="intro"><div><div className="eyebrow">EXPLORE YOUR NEXT FIT</div><h1>A new perspective on fit<span>.</span></h1><p>Your photo, your garment. Generated on your connected Colab GPU.</p></div>
        <button className="demo-button" disabled={busy || demoBusy} onClick={demo}><Sparkles size={16}/>Try sample photos<ArrowRight size={15}/></button>
      </section>
      <div className="workspace">
        <aside className="input-panel">
          <div className="panel-title"><span className="step-number">01</span><h2>Make it yours</h2></div>
          <div className="uploads"><UploadCard label="Your photo" kind="person" file={person} onChange={setPerson} disabled={busy}/><UploadCard label="Your garment" kind="garment" file={garment} onChange={setGarment} disabled={busy}/><p>JPG, PNG or WebP · up to 12 MB</p></div>
          <div className="form-controls">
            <label className="field-label" htmlFor="category">Garment category</label>
            <select id="category" aria-label="Garment category" value={category} onChange={e => setCategory(e.target.value)} disabled={busy}>{categories.map(([v, label]) => <option key={v} value={v}>{label}</option>)}</select>
            <label className="field-label" htmlFor="photo-type">Garment photo</label>
            <select id="photo-type" value={photoType} onChange={e => setPhotoType(e.target.value)} disabled={busy}><option value="flat-lay">Product / flat lay</option><option value="model">Worn by a person</option></select>
            <p>Choose the correct photo type to guide garment preparation.</p>
            <div className="model-status" data-testid="model-status"><strong>{vton?.available ? "Colab worker configured" : "Colab connection needed"}</strong><p>{vton?.reason ?? "Photos are processed on your Colab GPU. Shared runtime and network delays affect generation time."}</p><button onClick={checkWorker} disabled={checking || busy}>{checking ? "Checking…" : "Check connection"}</button></div>
            <button className="generate-button" disabled={!person || !garment || !vton?.available || busy} onClick={generate}>{busy ? <LoaderCircle className="spin" size={18}/> : <Sparkles size={18}/>} {busy ? "Generating try-on…" : "Generate try-on"}</button>
            {busy && <p role="status" data-testid="job-progress">{message}. Refreshing returns to the same job.</p>}
            <p className="local-note">Online inference only. Your computer’s GPU is never used.</p>
          </div>
        </aside>
        <section className="visual-panel"><div className="visual-heading"><div><span className="step-number">02</span><h2>See the look</h2></div></div>
          <PhotoViewer key={result?.runId ?? "empty"} previewUrl={result?.previewUrl} originalUrl={result?.originalUrl} busy={busy} progressMessage={message}/>
          <div className="viewer-caption"><span>{result ? `Completed in ${result.timingSeconds.toFixed(1)}s` : "Ready when you are"}</span><span>Photo try-on · Colab GPU</span></div>
        </section>
        <aside className="results-panel"><div className="panel-title"><span className="step-number">03</span><h2>Your result</h2></div>
          {result ? <><div className="photo-result" data-testid="photo-result"><Shirt size={28}/><h3>Your virtual try-on</h3><p>{result.provenance.backend}</p><p>Compare with the original photo. Check fabric detail, seams and body shape.</p></div><details className="result-notes"><summary>Model limitations</summary>{result.warnings.map((w,i) => <p key={i}>{w}</p>)}</details><a className="result-download" href={result.artifacts.result} download><ArrowDownToLine size={14}/>Download result JSON</a></> : <div className="empty-results"><Shirt size={36}/><h3>A different outfit, the same you</h3><p>Upload a clear photo and one garment. Tops, bottoms, dresses and jumpsuits use their respective model categories.</p><p>Complex layering, sheer fabric and unusual outfits remain unvalidated.</p></div>}
          <SizeRecommendation/>
        </aside>
      </div>
      {error && <div className="error-banner" role="alert"><strong>We couldn’t complete that step.</strong><span>{error}</span><button aria-label="Dismiss error" onClick={() => setError("")}><X size={16}/></button></div>}
      <section className="scope-strip"><FlaskConical size={18}/><p><strong>A research prototype.</strong> Image generation does not measure your body or prove a physical fit. Size advice uses only measurements you enter and the selected chart.</p></section>
    </main>
    <footer><span>FORM / FIT STUDIO</span><span>Photo try-on · Online GPU</span></footer>
    {help && <div className="modal-backdrop" onClick={() => setHelp(false)}><section className="modal" role="dialog" aria-modal="true" aria-labelledby="help-title" onClick={e => e.stopPropagation()}><button className="modal-close icon-button" aria-label="Close help" onClick={() => setHelp(false)}><X size={20}/></button><h2 id="help-title">Clear photos make a better starting point</h2><p>Use one front-facing person with a visible face. Show the torso for tops and the entire body for trousers, skirts, dresses or jumpsuits. Avoid crossed arms and heavy occlusion.</p><p>Upload one garment and choose whether it is a product photo or worn by a person. Model support is not a guarantee for every dress, fabric or outfit.</p><p>Images are sent only to your connected Colab worker. The local app retains inputs and results until deleted. Colab sessions can disconnect; generation then returns an error without using your system GPU.</p><button className="generate-button" onClick={() => setHelp(false)}>Got it</button></section></div>}
  </>;
}
