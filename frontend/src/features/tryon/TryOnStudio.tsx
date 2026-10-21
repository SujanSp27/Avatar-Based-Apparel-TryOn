import { useEffect, useState } from "react";
import { ArrowRight, LoaderCircle, Shirt, Sparkles } from "../../icons";
import { useTryOnJob } from "../../useTryOnJob";
import type { Result, VtonAvailability } from "../../types";
import ImageUploader from "../measurement/ImageUploader";
import { useMeasurement } from "../measurement/MeasurementProvider";
import SplitCompareViewer from "./SplitCompareViewer";
import GenerationProgress from "./GenerationProgress";
import { ErrorNotice } from "../../components/feedback/Feedback";
const categories = [
  ["t-shirt", "T-shirt"],
  ["shirt", "Shirt"],
  ["blouse", "Blouse"],
  ["sweater", "Sweater"],
  ["jacket", "Jacket"],
  ["trouser", "Trousers"],
  ["jeans", "Jeans"],
  ["shorts", "Shorts"],
  ["skirt", "Skirt"],
  ["dress", "Dress"],
  ["jumpsuit", "Jumpsuit"],
];
export default function TryOnStudio() {
  const active = useMeasurement();
  const [person, setPerson] = useState<File | undefined>(active.file);
  const [garment, setGarment] = useState<File>();
  const [category, setCategory] = useState("t-shirt");
  const [photoType, setPhotoType] = useState("flat-lay");
  const [result, setResult] = useState<Result>();
  const [error, setError] = useState("");
  const [availability, setAvailability] = useState<VtonAvailability>();
  const [offline, setOffline] = useState(false);
  const [preview, setPreview] = useState<string>();
  const [garmentPreview, setGarmentPreview] = useState<string>();
  const [samplesBusy, setSamplesBusy] = useState(false);
  const [filter, setFilter] = useState("all");
  const { busy, message, submit } = useTryOnJob(setResult, setError);
  useEffect(() => {
    if (!person) {
      setPreview(undefined);
      return;
    }
    const url = URL.createObjectURL(person);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [person]);
  useEffect(() => {
    if (!garment) {
      setGarmentPreview(undefined);
      return;
    }
    const url = URL.createObjectURL(garment);
    setGarmentPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [garment]);
  useEffect(() => {
    let stopped = false;
    let timer: ReturnType<typeof setTimeout>;
    let controller: AbortController;
    async function check() {
      controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 8000);
      try {
        const r = await fetch("/api/health", { signal: controller.signal });
        if (!r.ok) throw new Error();
        const data = await r.json();
        if (!stopped) {
          setAvailability(data.vton2d);
          setOffline(false);
        }
      } catch {
        if (!stopped) {
          setAvailability(undefined);
          setOffline(true);
        }
      } finally {
        clearTimeout(timeout);
        if (!stopped) timer = setTimeout(check, 4000);
      }
    }
    void check();
    return () => {
      stopped = true;
      clearTimeout(timer);
      controller?.abort();
    };
  }, []);
  async function sample(withPerson = true) {
    setSamplesBusy(true);
    setError("");
    try {
      if (withPerson) {
        const r = await fetch("/api/samples/person");
        if (!r.ok) throw new Error("Person sample unavailable.");
        setPerson(
          new File([await r.blob()], "studio-person.jpg", {
            type: "image/jpeg",
          }),
        );
      }
      const r = await fetch("/api/samples/garment");
      if (!r.ok) throw new Error("Garment sample unavailable.");
      setGarment(
        new File([await r.blob()], "garment-demo.png", { type: "image/png" }),
      );
      setCategory("t-shirt");
      setPhotoType("flat-lay");
      setResult(undefined);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSamplesBusy(false);
    }
  }
  async function generate() {
    if (!person || !garment || !availability?.available) return;
    setError("");
    setResult(undefined);
    const form = new FormData();
    form.append("personImage", person);
    form.append("garmentImage", garment);
    form.append("garmentCategory", category);
    form.append("garmentPhotoType", photoType);
    await submit(form);
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">03 / MEET YOUR NEXT LOOK</span>
          <h1>
            A new outfit.
            <br className="mobile-only" /> <em>Still you.</em>
          </h1>
          <p>
            Your photo and your garment, brought together in your virtual
            fitting room.
          </p>
        </div>
        <button
          className="button secondary"
          disabled={busy || samplesBusy}
          onClick={() => void sample()}
        >
          <Sparkles size={16} />
          Try sample photos
        </button>
      </div>
      <div className="tryon-layout">
        <aside className="card tryon-controls">
          <div className="section-heading">
            <h2>Style your scene.</h2>
            <Shirt size={22} />
          </div>
          <ImageUploader
            label="Your person photo"
            file={person}
            disabled={busy}
            onChange={(file) => {
              setPerson(file);
              setResult(undefined);
            }}
          />
          <ImageUploader
            label="Your garment"
            file={garment}
            disabled={busy}
            onChange={(file) => {
              setGarment(file);
              setResult(undefined);
            }}
          />
          {garmentPreview && (
            <img
              className="garment-thumb"
              src={garmentPreview}
              alt="Selected garment conditioning image"
            />
          )}
          <label className="field">
            Garment category
            <select
              aria-label="Garment category"
              disabled={busy}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
            >
              {categories.map(([value, label]) => (
                <option value={value} key={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            Garment photo type
            <select
              disabled={busy}
              value={photoType}
              onChange={(e) => setPhotoType(e.target.value)}
            >
              <option value="flat-lay">Product / flat lay</option>
              <option value="model">Worn by a person</option>
            </select>
          </label>
          <div
            className="model-status"
            role="status"
            data-testid="model-status"
            data-ready={!!availability?.available}
          >
            <span
              className={`status-dot ${availability?.available ? "" : "pending"}`}
            />
            <div>
              <strong>
                {availability?.available
                  ? "Ready to try on"
                  : offline
                    ? "Starting the app…"
                    : "Preparing try-on…"}
              </strong>
              <p>
                {offline
                  ? "Waiting for the app service. Retrying automatically."
                  : availability?.reason ||
                    (availability?.available
                      ? "Your private Colab GPU is ready."
                      : "Checking your Colab service automatically.")}
              </p>
            </div>
          </div>
          <button
            className="button"
            disabled={!person || !garment || busy || !availability?.available}
            onClick={() => void generate()}
          >
            {busy ? (
              <LoaderCircle size={16} className="spin" />
            ) : (
              <Sparkles size={16} />
            )}{" "}
            {busy ? "Generating…" : "Generate try-on"}
            <ArrowRight size={16} />
          </button>
          <p className="fine-print">
            Photos are processed only in your connected Colab. Your computer’s
            GPU is never used.
          </p>
        </aside>
        <div className="tryon-result">
          <SplitCompareViewer
            key={result?.runId ?? preview ?? "empty"}
            original={result?.originalUrl ?? preview}
            result={result?.previewUrl}
          />
          {busy && <GenerationProgress message={message} />}{" "}
          {error && <ErrorNotice message={error} />}{" "}
          {result && (
            <div className="card result-caption">
              <div className="row-between">
                <strong>Your new look is ready.</strong>
                <span className="badge">
                  {result.timingSeconds.toFixed(1)} seconds
                </span>
              </div>
              <p>
                Inspect the neckline, garment detail and body boundaries. A
                rendered image does not establish physical fit.
              </p>
              <details>
                <summary>Generation notes</summary>
                {result.warnings.map((warning, i) => (
                  <p key={i}>{warning}</p>
                ))}
              </details>
            </div>
          )}
          <div className="card garment-catalog">
            <div className="section-heading">
              <div>
                <span className="eyebrow">A PLACE TO START</span>
                <h3>The garment rail.</h3>
              </div>
              <select
                aria-label="Filter garment catalog"
                value={filter}
                onChange={(e) => setFilter(e.target.value)}
              >
                <option value="all">All garments</option>
                <option value="t-shirt">T-shirts</option>
                <option value="dress">Dresses</option>
                <option value="trouser">Trousers</option>
              </select>
            </div>
            {filter === "all" || filter === "t-shirt" ? (
              <button
                className="catalog-item"
                disabled={busy || samplesBusy}
                onClick={() => void sample(false)}
              >
                <img
                  src="/api/samples/garment"
                  alt="Sage striped T-shirt sample"
                />
                <div>
                  <strong>Sage stripe tee</strong>
                  <span>T-shirt · synthetic demo garment</span>
                  <small>
                    Use this garment <ArrowRight size={13} />
                  </small>
                </div>
              </button>
            ) : (
              <p className="muted">
                No sample is available in this category yet. Upload your own
                garment above.
              </p>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
