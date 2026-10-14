import { useCallback, useEffect, useRef, useState } from "react";
import {
  ArrowDownToLine,
  ArrowRight,
  Check,
  ChevronDown,
  CircleHelp,
  FlaskConical,
  Layers3,
  LoaderCircle,
  Plus,
  Ruler,
  Shirt,
  Sparkles,
  Upload,
  UserRound,
  X,
} from "./icons";
import Viewer from "./Viewer";
import PhotoViewer from "./PhotoViewer";
import { useTryOnJob } from "./useTryOnJob";
import {
  apiError,
  type Brand,
  type Result,
  type TryonMode,
  type VtonAvailability,
} from "./types";

function UploadCard({
  label,
  kind,
  file,
  onChange,
  disabled,
}: {
  label: string;
  kind: "person" | "garment";
  file?: File;
  onChange: (f?: File) => void;
  disabled: boolean;
}) {
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (!file) {
      setPreview("");
      return;
    }
    const url = URL.createObjectURL(file);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [file]);
  function choose(f?: File) {
    if (!f) return;
    if (!["image/jpeg", "image/png", "image/webp"].includes(f.type)) {
      setError("Choose a JPG, PNG or WebP.");
      return;
    }
    if (f.size > 12 * 1024 * 1024) {
      setError("Maximum file size is 12 MB.");
      return;
    }
    setError("");
    onChange(f);
  }
  return (
    <div className="upload-group">
      <span className="field-label">{label}</span>
      <input
        ref={input}
        aria-label={`Upload ${kind} image`}
        aria-describedby={
          kind === "person" ? "person-photo-guidance" : undefined
        }
        type="file"
        accept="image/jpeg,image/png,image/webp"
        disabled={disabled}
        onChange={(e) => choose(e.target.files?.[0])}
        className="file-input"
      />
      <div
        className={`upload-card ${file ? "has-file" : ""}`}
        onDragOver={(e) => e.preventDefault()}
        onDrop={(e) => {
          e.preventDefault();
          if (!disabled) choose(e.dataTransfer.files[0]);
        }}
      >
        <button
          className="upload-target"
          disabled={disabled}
          onClick={() => input.current?.click()}
          aria-label={`Choose ${kind} photo`}
        >
          {preview ? (
            <img src={preview} alt={`${kind} upload preview`} />
          ) : (
            <span className="upload-icon">
              {kind === "person" ? (
                <UserRound size={24} strokeWidth={1.4} />
              ) : (
                <Shirt size={24} strokeWidth={1.4} />
              )}
            </span>
          )}
          <span>
            <strong>
              {file
                ? file.name
                : `Add ${kind === "person" ? "your" : "garment"} photo`}
            </strong>
            <small>
              {file
                ? `${(file.size / 1024).toFixed(0)} KB · Click to replace`
                : kind === "person"
                  ? "Front-facing · torso visible"
                  : "Flat lay · plain background"}
            </small>
          </span>
          {!file && <Plus size={17} />}
        </button>
        {file && (
          <button
            className="remove-file"
            disabled={disabled}
            aria-label={`Remove ${kind} photo`}
            onClick={() => {
              onChange(undefined);
              if (input.current) input.current.value = "";
            }}
          >
            <X size={13} />
          </button>
        )}
      </div>
      {kind === "person" && (
        <p className="upload-guidance" id="person-photo-guidance">
          For 2D try-on, show both shoulders and your torso. For 3D, include
          your head, hands and feet with arms slightly apart. Face-only photos
          are not supported.
        </p>
      )}
      {error && (
        <p className="field-error" role="alert">
          {error}
        </p>
      )}
    </div>
  );
}

const measurementLabels: Record<string, string> = {
  height: "Height",
  shoulderWidth: "Shoulders",
  chest: "Chest / bust",
  waist: "Waist",
  hip: "Hip",
  armLength: "Arm length",
  inseam: "Inseam",
  thigh: "Thigh",
};

export default function App() {
  const [person, setPerson] = useState<File>();
  const [garment, setGarment] = useState<File>();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("t-shirt");
  const [fit, setFit] = useState("regular");
  const [height, setHeight] = useState("172");
  const [tryonMode, setTryonMode] = useState<TryonMode>("2d");
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState("");
  const [loaded, setLoaded] = useState(false);
  const [asset, setAsset] = useState("dressed");
  const [help, setHelp] = useState(false);
  const [demoBusy, setDemoBusy] = useState(false);
  const [connected, setConnected] = useState(false);
  const [vton, setVton] = useState<VtonAvailability>();
  const [checkingVton, setCheckingVton] = useState(false);
  const [vtonCheckError, setVtonCheckError] = useState("");
  const { busy, message: jobMessage, submit } = useTryOnJob((generated) => {
    setResult(generated);
    setAsset("dressed");
    setLoaded(false);
  }, setError);
  const loadedCallback = useCallback(() => setLoaded(true), []);
  const checkVton = useCallback(async () => {
    setCheckingVton(true);
    setVtonCheckError("");
    try {
      const response = await fetch("/api/health");
      if (!response.ok) throw new Error(await apiError(response));
      const health = await response.json();
      if (typeof health.vton2d?.available !== "boolean") {
        throw new Error("The server did not report the 2D model status.");
      }
      setVton(health.vton2d as VtonAvailability);
    } catch {
      setVtonCheckError(
        "Could not check the 2D model. Check that the local API is running, then retry.",
      );
    } finally {
      setCheckingVton(false);
    }
  }, []);
  useEffect(() => {
    void checkVton();
  }, [checkVton]);
  useEffect(() => {
    fetch("/api/brands")
      .then(async (r) => {
        if (!r.ok) throw new Error(await apiError(r));
        return r.json();
      })
      .then((b: Brand[]) => {
        setBrands(b);
        setBrand(String(b[0]?.id ?? ""));
        setConnected(true);
      })
      .catch(() =>
        setError("Backend unavailable. Check that the local API is running."),
      );
  }, []);
  async function demo() {
    setDemoBusy(true);
    setError("");
    try {
      const responses = await Promise.all([
        fetch("/api/samples/person"),
        fetch("/api/samples/garment"),
      ]);
      if (responses.some((r) => !r.ok))
        throw new Error(
          "Demo assets are unavailable. Run the asset setup script.",
        );
      const blobs = await Promise.all(responses.map((r) => r.blob()));
      setPerson(
        new File([blobs[0]], "studio-person.jpg", { type: "image/jpeg" }),
      );
      setGarment(
        new File([blobs[1]], "garment-demo.png", { type: "image/png" }),
      );
      setCategory("t-shirt");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setDemoBusy(false);
    }
  }
  async function generate() {
    if (
      !person ||
      !garment ||
      (tryonMode === "2d" && vton?.available === false)
    )
      return;
    setError("");
    setResult(undefined);
    setLoaded(false);
    const form = new FormData();
    form.append("personImage", person);
    form.append("garmentImage", garment);
    form.append("brandId", brand);
    form.append("garmentCategory", category);
    form.append("fitPreference", fit);
    form.append("tryonMode", tryonMode);
    if (height && tryonMode !== "2d") form.append("heightCm", height);
    await submit(form);
  }
  const avatar =
    result && result.mode !== "2d"
      ? asset === "body"
        ? result.bodyUrl
        : asset === "garment"
          ? result.garmentUrl
          : result.avatarUrl
      : undefined;
  const showPhotoViewer =
    result?.mode === "2d" || (!result && tryonMode === "2d");
  return (
    <>
      <header className="header">
        <a className="wordmark" href="/" aria-label="Form Fit home">
          <span className="logo-symbol">
            <Layers3 size={21} />
          </span>
          form<span className="wordmark-slash">/</span>fit
          <span className="wordmark-studio">STUDIO</span>
        </a>
        <nav>
          <span className="nav-active">Virtual try-on</span>
          <button onClick={() => setHelp(true)}>
            About the prototype <CircleHelp size={14} />
          </button>
        </nav>
        <span className="research-tag">
          <FlaskConical size={13} />
          RESEARCH EDITION
        </span>
      </header>
      <main>
        <section className="intro">
          <div>
            <div className="eyebrow">EXPLORE YOUR NEXT FIT</div>
            <h1>
              A new perspective on fit<span>.</span>
            </h1>
            <p>
              Explore your garment with virtual try-on or an interactive avatar.
            </p>
          </div>
          <button
            className="demo-button"
            disabled={busy || demoBusy}
            onClick={demo}
          >
            {demoBusy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Sparkles size={16} />
            )}
            Try sample photos
            <ArrowRight size={15} />
          </button>
        </section>
        <div className="workspace">
          <aside className="input-panel">
            <div className="panel-title">
              <span className="step-number">01</span>
              <h2>Make it yours</h2>
            </div>
            <div className="uploads">
              <UploadCard
                kind="person"
                label="Your photo"
                file={person}
                onChange={setPerson}
                disabled={busy}
              />
              <UploadCard
                kind="garment"
                label="Your garment"
                file={garment}
                onChange={setGarment}
                disabled={busy}
              />
              <span className="upload-note">
                <Upload size={11} />
                JPG, PNG or WebP · up to 12 MB
              </span>
            </div>
            <div className="form-fields">
              <label className="mode-field">
                Try-on mode
                <div className="select-wrap">
                  <select
                    aria-label="Try-on mode"
                    value={tryonMode}
                    disabled={busy}
                    onChange={(e) => {
                      const mode = e.target.value as TryonMode;
                      setTryonMode(mode);
                      if (
                        mode === "2d" &&
                        category !== "t-shirt" &&
                        category !== "shirt"
                      ) {
                        setCategory("t-shirt");
                      }
                    }}
                  >
                    <option value="auto">Auto · 3D or 2D try-on</option>
                    <option value="2d">2D virtual try-on</option>
                    <option value="3d">3D avatar only</option>
                  </select>
                  <ChevronDown size={14} />
                </div>
              </label>
              <p className="mode-note">
                {tryonMode === "auto"
                  ? "Tries 3D first. T-shirts and shirts can use 2D try-on if 3D is unsuitable; dresses and trousers require a valid full-body 3D input."
                  : tryonMode === "2d"
                    ? "CatVTON supports T-shirts and shirts at 384 × 512 model resolution. Fine details may be lost. No body measurements or size recommendation."
                    : "Requires a full-body photo with head, hands and feet visible."}
              </p>
              {tryonMode !== "3d" &&
                (vton?.available === false || vtonCheckError) && (
                  <div
                    className="model-status"
                    role="status"
                    data-testid="model-status"
                  >
                    <strong>
                      {vton?.available === false
                        ? "2D model unavailable"
                        : "2D model status unknown"}
                    </strong>
                    <p>
                      {vtonCheckError ||
                        vton?.reason ||
                        "The pretrained model is not ready."}
                    </p>
                    {tryonMode === "auto" && vton?.available === false && (
                      <p>
                        Auto mode can still try 3D, but 2D fallback is
                        unavailable.
                      </p>
                    )}
                    <button
                      type="button"
                      disabled={checkingVton || busy}
                      onClick={() => void checkVton()}
                    >
                      {checkingVton ? "Checking model…" : "Check model again"}
                    </button>
                  </div>
                )}
              <div className="field-row">
                <label>
                  Height <span className="unit">cm</span>
                  <input
                    aria-label="Height in cm"
                    type="number"
                    min="120"
                    max="220"
                    step="0.1"
                    value={height}
                    placeholder="170 assumed"
                    disabled={busy || tryonMode === "2d"}
                    onChange={(e) => setHeight(e.target.value)}
                  />
                </label>
                <label>
                  Category
                  <div className="select-wrap">
                    <select
                      aria-label="Garment category"
                      value={category}
                      disabled={busy}
                      onChange={(e) => setCategory(e.target.value)}
                    >
                      <option value="t-shirt">T-shirt</option>
                      <option value="shirt">Shirt</option>
                      {tryonMode !== "2d" && (
                        <>
                          <option value="dress">Dress</option>
                          <option value="trouser">Trouser</option>
                        </>
                      )}
                    </select>
                    <ChevronDown size={14} />
                  </div>
                </label>
              </div>
              <label>
                Brand
                <div className="select-wrap">
                  <select
                    aria-label="Brand"
                    value={brand}
                    disabled={busy}
                    onChange={(e) => setBrand(e.target.value)}
                  >
                    {!brands.length && <option>Loading brands…</option>}
                    {brands.map((b) => (
                      <option key={b.id} value={b.id}>
                        {b.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} />
                </div>
              </label>
              <span className="chart-note">
                {brands.find((b) => String(b.id) === brand)?.isDemo
                  ? "Sample chart · not a retailer size guide"
                  : "Versioned brand size chart"}
              </span>
              <label>
                {tryonMode === "2d"
                  ? "Fit preference (3D only)"
                  : "How do you like your fit?"}
              </label>
              <div className="fit-selector">
                {["tight", "regular", "loose"].map((f) => (
                  <button
                    key={f}
                    disabled={busy || tryonMode === "2d"}
                    className={fit === f ? "selected" : ""}
                    aria-pressed={fit === f}
                    onClick={() => setFit(f)}
                  >
                    {f}
                    {fit === f && <Check size={12} />}
                  </button>
                ))}
              </div>
              <button
                className="generate-button"
                disabled={
                  !person ||
                  !garment ||
                  !brand ||
                  busy ||
                  (tryonMode === "2d" && vton?.available === false) ||
                  (tryonMode !== "2d" &&
                    !!height &&
                    (+height < 120 || +height > 220))
                }
                onClick={generate}
              >
                {busy ? (
                  <LoaderCircle className="spin" size={18} />
                ) : (
                  <Layers3 size={18} />
                )}{" "}
                {busy ? "Generating try-on…" : "Generate try-on"}
                {!busy && <ArrowRight size={17} />}
              </button>
              {busy && <p role="status" data-testid="job-progress">{jobMessage}. You can refresh this page and return to the same job.</p>}
              <p className="local-note">
                <span className={`status-dot ${connected ? "on" : ""}`} />
                Photos are processed on this computer
              </p>
            </div>
          </aside>
          <section className="visual-panel">
            <div className="visual-heading">
              <div>
                <span className="step-number">02</span>
                <h2>See the fit</h2>
              </div>
              {!showPhotoViewer && (
                <div className="asset-tabs">
                  {["dressed", "body", "garment"].map((a) => (
                    <button
                      key={a}
                      disabled={!result}
                      className={asset === a ? "active" : ""}
                      onClick={() => {
                        setAsset(a);
                        setLoaded(false);
                      }}
                    >
                      {a}
                    </button>
                  ))}
                </div>
              )}
            </div>
            {showPhotoViewer ? (
              <PhotoViewer
                key={result?.runId ?? "empty-photo"}
                previewUrl={
                  result?.mode === "2d" ? result.previewUrl : undefined
                }
                originalUrl={
                  result?.mode === "2d" ? result.originalUrl : undefined
                }
                busy={busy}
                progressMessage={jobMessage}
              />
            ) : (
              <Viewer
                url={avatar}
                busy={busy}
                loaded={loaded}
                onLoad={loadedCallback}
              />
            )}
            <div className="viewer-caption">
              <span>
                <span className="status-dot on" />
                {result
                  ? `Generated in ${result.timingSeconds.toFixed(1)}s`
                  : "Ready when you are"}
              </span>
              <span>
                {showPhotoViewer
                  ? "Model-generated image · single photo"
                  : "Approximate 3D template · single photo"}
              </span>
            </div>
          </section>
          <aside className="results-panel">
            <div className="panel-title">
              <span className="step-number">03</span>
              <h2>
                {result?.mode === "2d"
                  ? "Your try-on result"
                  : "Your fit profile"}
              </h2>
            </div>
            {result ? (
              <>
                {result.mode === "2d" ? (
                  <>
                    <div className="photo-result" data-testid="photo-result">
                      <span className="photo-result-icon">
                        <Shirt size={28} strokeWidth={1.4} />
                      </span>
                      <h3>2D virtual try-on</h3>
                      <p>
                        {result.fallbackReason
                          ? "This photo could not produce a 3D avatar. A pretrained try-on model generated this image instead."
                          : "A pretrained try-on model generated garment replacement using your uploaded images."}
                      </p>
                      <span className="fit-badge">Model-generated image</span>
                      <p>
                        CatVTON generates clothing at 384 × 512 resolution.
                        Inspect neckline, sleeves and fine garment details; this
                        research model can still produce artifacts.
                      </p>
                    </div>
                    <div className="photo-size-note">
                      <h3>
                        <Ruler size={15} /> Size unavailable
                      </h3>
                      <p>
                        The 2D model does not estimate body measurements or
                        clothing size. The separate size engine uses measured
                        dimensions and the selected brand chart.
                      </p>
                      <p>
                        Selected brand: <strong>{result.brandName}</strong>,
                        chart v{result.chartVersion}. Check the brand’s size
                        guide using your measured dimensions.
                      </p>
                    </div>
                  </>
                ) : (
                  <>
                    <div className="size-result">
                      <span className="eyebrow">RECOMMENDED SIZE</span>
                      <strong data-testid="recommended-size">
                        {result.recommendedSize}
                      </strong>
                      <span className="fit-badge">{result.fit} fit</span>
                      <p>
                        {result.brandName} · chart v{result.chartVersion}
                      </p>
                    </div>
                    <div className="fit-explanation">
                      <h3>Why this size</h3>
                      {Object.entries(result.explanation).map(
                        ([key, value]) => (
                          <div key={key}>
                            <span>{measurementLabels[key] ?? key}</span>
                            <strong>{value}</strong>
                          </div>
                        ),
                      )}
                      <p>
                        Distance score {result.score.toFixed(3)} · lower is
                        better
                      </p>
                    </div>
                    <div className="measurements">
                      <h3>
                        <Ruler size={15} />
                        Estimated measurements <span>cm</span>
                      </h3>
                      {Object.entries(measurementLabels).map(([key, label]) => (
                        <div key={key}>
                          <span>{label}</span>
                          <strong>
                            {Number(result.measurements[key]).toFixed(1)}
                          </strong>
                        </div>
                      ))}
                    </div>
                  </>
                )}
                <details className="result-notes">
                  <summary>Assumptions & uncertainty</summary>
                  {result.warnings.map((w, i) => (
                    <p key={i}>{w}</p>
                  ))}
                  {result.mode !== "2d" && (
                    <p>
                      Uncertainty bounds are heuristics, not calibrated
                      confidence intervals. Score is not a probability.
                    </p>
                  )}
                </details>
                <a
                  className="result-download"
                  href={result.artifacts.result}
                  download
                >
                  <ArrowDownToLine size={14} />
                  Download result JSON
                </a>
              </>
            ) : (
              <div className="empty-results">
                <div className="empty-ruler">
                  <Ruler size={29} strokeWidth={1.2} />
                </div>
                <h3>A fit profile, just for you</h3>
                <p>
                  A 3D result includes estimated measurements and a size
                  recommendation. A 2D model generates an image of the requested
                  garment on the person.
                </p>
                <div className="empty-metrics">
                  {[
                    "Recommended size",
                    "Body measurements",
                    "Fit explanation",
                  ].map((t) => (
                    <div key={t}>
                      <span>{t}</span>
                      <span>—</span>
                    </div>
                  ))}
                </div>
                <span className="estimate-note">
                  Research estimates.
                  <br />
                  Always check a brand’s actual size guide.
                </span>
              </div>
            )}
          </aside>
        </div>
        {error && (
          <div className="error-banner" role="alert">
            <strong>We couldn’t complete that step.</strong>
            <span>{error}</span>
            <button aria-label="Dismiss error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        <section className="scope-strip">
          <FlaskConical size={18} />
          <p>
            <strong>A working research prototype.</strong> 3D uses approximate
            body geometry and template garments. 2D uses a pretrained virtual
            try-on model. Inspect generated images for garment, identity and
            background changes. Clothing fit is unvalidated.
          </p>
          <button onClick={() => setHelp(true)}>
            Supported inputs <ArrowRight size={14} />
          </button>
        </section>
      </main>
      <footer>
        <span>FORM / FIT STUDIO</span>
        <span>Look around. Find your perspective.</span>
        <span>LOCAL PROTOTYPE · V0.1</span>
      </footer>
      {help && (
        <div className="modal-backdrop" onClick={() => setHelp(false)}>
          <section
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="help-title"
            onClick={(e) => e.stopPropagation()}
          >
            <button
              className="modal-close icon-button"
              aria-label="Close help"
              onClick={() => setHelp(false)}
            >
              <X size={20} />
            </button>
            <FlaskConical size={27} />
            <h2 id="help-title">Good inputs. More useful estimates.</h2>
            <p>
              Use one front-facing adult against a plain background. For 2D,
              show both shoulders and your torso; upper-body portraits can work.
              Face-only photos cannot position a garment. For 3D, include your
              complete head, hands and feet, standing with arms slightly apart.
            </p>
            <p>
              Upload one flat garment on a contrasting background. 2D supports
              T-shirts and shirts; 3D also supports dresses and trousers.
              Include your known height for 3D scale; leaving it blank assumes
              170 cm. Auto mode uses the configured 2D try-on model when a
              supported photo cannot produce a 3D avatar.
            </p>
            <p>
              The 3D pipeline uses MediaPipe pose and segmentation with
              deterministic geometry. It does not recover hidden body shape or
              facial identity. The optional HMR2/SMPL component requires
              licensed assets and remains unavailable here.
            </p>
            <p>
              2D virtual try-on uses pretrained CatVTON at 384 × 512 model
              resolution. Fine patterns and boundaries may contain artifacts.
              Preserving the person's face and background is a target, not a
              guarantee. The image does not establish clothing fit, body
              measurements or a size recommendation. Compare Original and Try-on
              to inspect the result. If the model is unavailable, generation
              returns an error.
            </p>
            <p>
              Sample charts are fictional. This is not a reliable purchasing or
              tailoring measurement tool. Local uploads and results remain in
              the project’s storage until deleted.
            </p>
            <button className="generate-button" onClick={() => setHelp(false)}>
              Got it <Check size={16} />
            </button>
          </section>
        </div>
      )}
    </>
  );
}
