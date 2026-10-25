import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api } from "../../services/api/client";
import { usePublicConfig } from "../../services/usePublicConfig";
import { ArrowRight, LoaderCircle, Shirt, Sparkles } from "../../icons";
import { useTryOnJob } from "../../useTryOnJob";
import type { Result, VtonAvailability } from "../../types";
import ImageUploader from "../measurement/ImageUploader";
import { useMeasurement } from "../measurement/MeasurementProvider";
import SplitCompareViewer from "./SplitCompareViewer";
import GenerationProgress from "./GenerationProgress";
import GarmentPicker, { type Garment } from "./GarmentPicker";
import "./comparison.css";
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
  const configuration = usePublicConfig();
  const [params, setParams] = useSearchParams();
  const productId = params.get("product");
  const active = useMeasurement();
  const [person, setPerson] = useState<File | undefined>(active.file);
  const [garment, setGarment] = useState<File>();
  const [category, setCategory] = useState("t-shirt");
  const [photoType, setPhotoType] = useState("flat-lay");
  const [result, setResult] = useState<Result>();
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState("");
  const [availability, setAvailability] = useState<VtonAvailability>();
  const [offline, setOffline] = useState(false);
  const [checkVersion, setCheckVersion] = useState(0);
  const [retryBusy, setRetryBusy] = useState(false);
  const [preview, setPreview] = useState<string>();
  const [garmentPreview, setGarmentPreview] = useState<string>();
  const [samplesBusy, setSamplesBusy] = useState(false);
  const [selectedGarment, setSelectedGarment] = useState<string>();
  const { busy, message, submit, reset } = useTryOnJob(
    (next) => {
      setResult(next);
      if (next) {
        setEditing(false);
        setCategory(next.garmentCategory);
      }
    },
    setError,
    () => {
      // A result selected in another tab has its own original photo. Do not keep
      // this tab's old uploads poised for an unrelated generation.
      setPerson(undefined);
      setGarment(undefined);
      setSelectedGarment(undefined);
    },
  );
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
        const r = await fetch("/api/tryon/availability", {
          signal: controller.signal,
          cache: "no-store",
        });
        if (!r.ok) throw new Error();
        const data = await r.json();
        if (!stopped) {
          setAvailability(data);
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
  }, [checkVersion]);
  async function retryConnection() {
    setRetryBusy(true);
    try {
      const response = await fetch("/api/tryon/retry", {
        method: "POST",
        signal: AbortSignal.timeout(8000),
      });
      if (!response.ok)
        throw new Error(
          "The app service is not responding. Automatic checks will continue.",
        );
      setAvailability(await response.json());
      setOffline(false);
    } catch {
      setOffline(true);
    } finally {
      setRetryBusy(false);
      setCheckVersion((value) => value + 1);
    }
  }
  async function sample(withPerson = true) {
    setSamplesBusy(true);
    reset();
    try {
      const [personFile, garmentFile] = await Promise.all([
        withPerson
          ? downloadPhoto("/api/samples/person", "studio-person.jpg")
          : Promise.resolve(person),
        downloadPhoto("/api/garments/navy-tee/image", "navy-tee.jpg"),
      ]);
      setPerson(personFile);
      setGarment(garmentFile);
      setCategory("t-shirt");
      setPhotoType("model");
      setSelectedGarment("navy-tee");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSamplesBusy(false);
    }
  }
  async function selectGarment(item: Garment) {
    if (item.tryon_supported === false || !item.category) {
      setError(
        "This editorial outfit is not supported by the try-on model. Choose a supported single garment.",
      );
      return;
    }
    const original = result?.originalUrl;
    setSamplesBusy(true);
    reset();
    try {
      const [file, originalFile] = await Promise.all([
        downloadPhoto(item.imageUrl, item.id),
        original
          ? downloadPhoto(original, "original-person.png")
          : Promise.resolve(person),
      ]);
      setPerson(originalFile);
      setGarment(file);
      setCategory(item.category);
      setPhotoType(item.photoType);
      setSelectedGarment(item.id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSamplesBusy(false);
    }
  }
  useEffect(() => {
    if (!productId) return;
    let stopped = false;
    api<Garment>(`/api/v1/products/${encodeURIComponent(productId)}`)
      .then((item) => {
        if (!stopped) {
          void selectGarment(item);
          setParams(
            (current) => {
              const next = new URLSearchParams(current);
              next.delete("product");
              return next;
            },
            { replace: true },
          );
        }
      })
      .catch((e) => {
        if (!stopped) setError(e.message);
      });
    return () => {
      stopped = true;
    };
  }, [productId]);
  async function generate() {
    if (!person || !garment || !availability?.available) return;
    setError("");
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
        <div className="tryon-heading-actions">
          {result && (
            <button
              className="button secondary"
              aria-expanded={editing}
              aria-controls="tryon-inputs"
              onClick={() => setEditing((value) => !value)}
            >
              <Shirt size={16} />
              {editing ? "Focus on result" : "Change outfit"}
            </button>
          )}
          {configuration?.sample_photos && (
            <button
              className="button secondary"
              disabled={busy || samplesBusy}
              onClick={() => void sample()}
            >
              <Sparkles size={16} />
              Try sample photos
            </button>
          )}
        </div>
      </div>
      <div
        className={`tryon-layout ${result && !editing ? "results-focus" : ""}`}
      >
        <aside
          id="tryon-inputs"
          className="card tryon-controls"
          hidden={!!result && !editing}
        >
          <div className="section-heading">
            <h2>Style your scene.</h2>
            <Shirt size={22} />
          </div>
          <ImageUploader
            label="Your person photo"
            file={person}
            disabled={busy || samplesBusy}
            onChange={(file) => {
              reset();
              setPerson(file);
            }}
          />
          <ImageUploader
            label="Your garment"
            file={garment}
            disabled={busy || samplesBusy}
            onChange={(file) => {
              reset();
              setGarment(file);
              setSelectedGarment(undefined);
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
              disabled={busy || samplesBusy}
              value={category}
              onChange={(e) => {
                reset();
                setCategory(e.target.value);
              }}
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
              aria-label="Garment photo type"
              disabled={busy || samplesBusy}
              value={photoType}
              onChange={(e) => {
                reset();
                setPhotoType(e.target.value);
              }}
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
                    ? "Temporarily unavailable"
                    : (availability?.displayState ?? "Preparing try-on…")}
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
          {!availability?.available && (
            <button
              className="button secondary"
              disabled={retryBusy}
              onClick={() => void retryConnection()}
            >
              {retryBusy ? "Checking…" : "Retry connection"}
            </button>
          )}
          <button
            className="button"
            disabled={
              !person ||
              !garment ||
              busy ||
              samplesBusy ||
              !availability?.available
            }
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
            original={result?.originalUrl ?? preview}
            result={result?.previewUrl}
            busy={busy}
            message={message}
            details={result}
          />
          {busy && <GenerationProgress message={message} />}{" "}
          {error && (
            <ErrorNotice
              message={error}
              retry={
                person &&
                garment &&
                !busy &&
                !samplesBusy &&
                availability?.available
                  ? () => void generate()
                  : undefined
              }
            />
          )}{" "}
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
          <GarmentPicker
            disabled={busy || samplesBusy}
            selected={selectedGarment}
            onSelect={(item) => void selectGarment(item)}
          />
        </div>
      </div>
    </>
  );
}

async function downloadPhoto(url: string, name: string): Promise<File> {
  const response = await fetch(url, { signal: AbortSignal.timeout(15000) });
  if (!response.ok)
    throw new Error(
      "The sample photo is unavailable. Retry or upload your own photo.",
    );
  const blob = await response.blob();
  if (!blob.type.startsWith("image/"))
    throw new Error("The sample did not return an image.");
  return new File([blob], name, { type: blob.type });
}
