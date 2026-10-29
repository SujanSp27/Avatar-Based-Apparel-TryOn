import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, LoaderCircle, Ruler, UserRound } from "../../icons";
import ImageUploader from "./ImageUploader";
import LandmarkCanvas from "./LandmarkCanvas";
import HeightInput from "./HeightInput";
import MeasurementGrid, { validMeasurements } from "./MeasurementGrid";
import WebcamCapture from "./WebcamCapture";
import { useMeasurement } from "./MeasurementProvider";
import { measurementService } from "../../services/measurementService";
import { useAuth } from "../auth/AuthProvider";
import AuthModal from "../auth/AuthModal";
import { useToast } from "../../components/ui/Toast";
import { ErrorNotice } from "../../components/feedback/Feedback";
import { thumbnail } from "../../utils/images";
import { usePublicConfig } from "../../services/usePublicConfig";
import { metricLabels, type Measurements } from "../../types/studio";
export default function MeasurementWorkspace() {
  const state = useMeasurement();
  const configuration = usePublicConfig();
  const auth = useAuth();
  const notify = useToast();
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [show, setShow] = useState(true);
  const [error, setError] = useState("");
  const [camera, setCamera] = useState(false);
  const [login, setLogin] = useState(false);
  const pending = useRef<AbortController | null>(null);
  const needsReview = (
    state.extraction?.quality.requires_manual_review ?? []
  ).filter((key) => !state.reviewedMetrics.includes(key));
  useEffect(() => {
    setError("");
  }, [state.file, state.height]);
  useEffect(() => {
    const cancel = () => {
      pending.current?.abort();
      setBusy(false);
    };
    window.addEventListener("formfit:clear-private", cancel);
    return () => {
      pending.current?.abort();
      window.removeEventListener("formfit:clear-private", cancel);
    };
  }, []);
  useEffect(() => {
    if (auth.user?.height_cm && !state.measurements)
      state.setHeight(auth.user.height_cm);
  }, [auth.user?.id]);
  async function sample() {
    setError("");
    try {
      const r = await fetch("/api/samples/person");
      if (!r.ok)
        throw new Error(
          "The sample photo is unavailable. Upload your own photo.",
        );
      state.setFile(
        new File([await r.blob()], "studio-person.jpg", { type: "image/jpeg" }),
      );
      notify(
        "Sample loaded. The default height is a test value; it is not measured ground truth.",
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function extract() {
    if (!state.file) return;
    pending.current?.abort();
    const controller = new AbortController();
    pending.current = controller;
    setBusy(true);
    setError("");
    // Keep the uploaded photo and height, but never reuse stale values after a failed retry.
    state.setExtraction(undefined);
    state.setMeasurements(undefined);
    state.setEdited(false);
    try {
      const result = await measurementService.extract(
        state.file,
        state.height,
        controller.signal,
      );
      if (controller.signal.aborted) return;
      state.setExtraction(result);
      // Zero is an empty editable field in this UI; it is never sent as a measurement.
      state.setMeasurements(
        Object.fromEntries(
          Object.entries(result.measurements).map(([key, value]) => [
            key,
            value ?? 0,
          ]),
        ) as Measurements,
      );
      state.setEdited(false);
      notify(
        result.quality.requires_manual_review?.length
          ? "Pose found. Review flagged measurements."
          : "Your six estimates are ready. Review and correct them before choosing a size.",
      );
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      if (!controller.signal.aborted) setBusy(false);
    }
  }
  async function save() {
    if (!auth.user) {
      setLogin(true);
      return;
    }
    if (!state.measurements || needsReview.length) return;
    setSaving(true);
    setError("");
    try {
      await measurementService.save(
        state.measurements,
        state.height,
        !state.file
          ? "manual"
          : state.edited
            ? "manually-corrected"
            : "photo-estimate",
        state.file ? await thumbnail(state.file) : undefined,
      );
      notify("Measurements saved to your private profile.");
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaving(false);
    }
  }
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">01 / KNOW YOUR MEASUREMENTS</span>
          <h1>
            A fit that starts
            <br className="mobile-only" /> with <em>you.</em>
          </h1>
          <p>One photo. Six measurements. A more personal starting point.</p>
        </div>
        <span className="privacy-pill">
          <span className="status-dot" />
          Measured locally
        </span>
      </div>
      <div className="measurement-workspace">
        <section className="photo-card">
          <div className="photo-card-top">
            <span className="small-caps">YOUR BODY PROFILE</span>
            <span className="badge">
              {state.extraction ? "33 landmarks detected" : "Full-body photo"}
            </span>
          </div>
          <div className="measurement-photo">
            {state.file ? (
              <LandmarkCanvas
                file={state.file}
                landmarks={state.extraction?.landmarks_normalized}
                presence={state.extraction?.landmark_presence}
                show={show}
              />
            ) : (
              <div className="photo-demo">
                {configuration?.sample_photos && (
                  <img
                    src="/api/samples/person"
                    alt="Example of a front-facing full-body photo on a plain background"
                  />
                )}
                <div className="demo-label">
                  A little space. A clear view. A better scan.
                </div>
              </div>
            )}
            {busy && (
              <div className="scan-overlay" role="status">
                <div className="scan-line" />
                <div>
                  <LoaderCircle className="spin" size={23} />
                  <strong>Finding your measurements</strong>
                  <span>Detecting pose & refining your outline…</span>
                </div>
              </div>
            )}
          </div>
          <div className="photo-card-footer">
            <span>
              <UserRound size={15} />
              {state.file
                ? "Your uploaded photo"
                : "Example photo · no scan yet"}
            </span>
            <label className="switch-label">
              <input
                type="checkbox"
                checked={show}
                onChange={(e) => setShow(e.target.checked)}
                disabled={!state.extraction}
              />
              <span>Landmark skeleton</span>
            </label>
          </div>
        </section>
        <aside className="scan-controls card">
          <div className="section-heading">
            <div>
              <span className="eyebrow">LET’S GET YOU SET UP</span>
              <h2>Your starting point.</h2>
            </div>
            <Ruler size={24} />
          </div>
          <ImageUploader
            file={state.file}
            onChange={state.setFile}
            disabled={busy}
          />
          <div className="two-actions">
            <button
              className="text-button"
              disabled={busy}
              onClick={() => setCamera(true)}
            >
              Use your camera
            </button>
            {configuration?.sample_photos && (
              <>
                <span>or</span>
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => void sample()}
                >
                  Try a sample
                </button>
              </>
            )}
          </div>
          <div className="divider" />
          <HeightInput
            value={state.height}
            onChange={(value) => {
              state.setHeight(value);
              state.setExtraction(undefined);
              state.setMeasurements(undefined);
              state.setEdited(false);
            }}
            disabled={busy}
          />
          <div className="photo-checklist">
            <strong>A good photo makes a difference</strong>
            {[
              "Head to feet, fully inside the frame",
              "Face forward, arms slightly apart",
              "Close-fitting clothes & a plain background",
            ].map((text) => (
              <span key={text}>
                <Check size={15} />
                {text}
              </span>
            ))}
          </div>
          {error && (
            <ErrorNotice message={error} retry={() => void extract()} />
          )}
          <button
            className="button full-width"
            disabled={
              !state.file || busy || state.height < 80 || state.height > 250
            }
            onClick={() => void extract()}
          >
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : (
              <Ruler size={17} />
            )}{" "}
            {busy ? "Measuring…" : "Extract measurements"}
            <ArrowRight size={17} />
          </button>
          <p className="fine-print">
            Estimated from your photo and height. Always review against a tape
            measure.
          </p>
        </aside>
      </div>
      <div className="section-heading measurements-heading">
        <div>
          <span className="eyebrow">THE DETAILS THAT MATTER</span>
          <h2>Your measurements.</h2>
        </div>
        <span className="badge">
          {state.edited
            ? "Manually corrected"
            : state.measurements
              ? "Photo estimates"
              : "6 dimensions · centimeters"}
        </span>
      </div>
      {needsReview.length > 0 && (
        <section
          className="estimate-details"
          role="status"
          aria-label="Measurement quality"
        >
          <strong>Some measurements need review</strong>
          <p>
            Your pose was detected, but the clothing outline cannot provide all
            body dimensions reliably. Edit the flagged dimensions using a tape
            measure, or retry with arms slightly apart and close-fitting
            clothing.
          </p>
          {needsReview.map((key) => (
            <p key={key}>
              <strong>{metricLabels[key]}:</strong>{" "}
              {state.extraction?.quality.metrics?.[key]?.message ??
                "Confirm this dimension with a tape measure before sizing."}
            </p>
          ))}
          <p>
            Landmark visibility is not measurement accuracy. Unavailable
            dimensions are left blank.
          </p>
        </section>
      )}
      <MeasurementGrid
        values={state.measurements}
        quality={state.extraction?.quality}
        reviewed={state.reviewedMetrics}
        onChange={(values, key) => state.correctMeasurement(key, values[key])}
      />
      {state.extraction && (
        <details className="estimate-details">
          <summary>What these estimates can and can’t tell you</summary>
          {state.extraction.warnings.map((w) => (
            <p key={w}>{w}</p>
          ))}
        </details>
      )}
      <div className="action-bar">
        <p>
          <strong>Your numbers, your control.</strong> Correct any estimate with
          your tape measurements.
        </p>
        <div className="actions">
          <button
            className="button secondary"
            disabled={
              !validMeasurements(state.measurements) ||
              !!needsReview.length ||
              saving
            }
            onClick={() => void save()}
          >
            {saving ? "Saving…" : "Save measurements"}
          </button>
          <Link
            className={`button ${!validMeasurements(state.measurements) || needsReview.length ? "disabled-link" : ""}`}
            aria-disabled={
              !validMeasurements(state.measurements) || !!needsReview.length
            }
            to="/sizing"
            onClick={(e) => {
              if (!validMeasurements(state.measurements) || needsReview.length)
                e.preventDefault();
            }}
          >
            Find my size <ArrowRight size={17} />
          </Link>
        </div>
      </div>
      <WebcamCapture
        open={camera}
        onClose={() => setCamera(false)}
        onCapture={state.setFile}
      />
      <AuthModal open={login} onClose={() => setLogin(false)} />
    </>
  );
}
