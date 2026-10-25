import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check, LoaderCircle, Ruler } from "../../icons";
import { sizingService } from "../../services/sizingService";
import type {
  Brand,
  Chart,
  Measurements,
  Metric,
  Recommendation,
} from "../../types/studio";
import { metricLabels } from "../../types/studio";
import { useMeasurement } from "../measurement/MeasurementProvider";
import { useAuth } from "../auth/AuthProvider";
import AuthModal from "../auth/AuthModal";
import {
  ErrorNotice,
  EmptyState,
  Skeleton,
} from "../../components/feedback/Feedback";
import { useToast } from "../../components/ui/Toast";
import FitConfidenceGauge from "./FitConfidenceGauge";
import SizeChartModal from "./SizeChartModal";
import DeviationHeatmap from "./DeviationHeatmap";
import ChartProvenance, { marketName } from "./ChartProvenance";
const categories = [
  ["t-shirt", "T-shirt"],
  ["shirt", "Shirt"],
  ["trouser", "Trousers"],
  ["dress", "Dress"],
  ["skirt", "Skirt"],
  ["jumpsuit", "Jumpsuit"],
  ["blouse", "Blouse"],
  ["jeans", "Jeans"],
  ["shorts", "Shorts"],
  ["kurta", "Kurta"],
  ["kurti", "Kurti"],
  ["salwar-suit", "Salwar suit"],
];
export default function SizeEngineView() {
  const active = useMeasurement();
  const auth = useAuth();
  const toast = useToast();
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brandId, setBrandId] = useState("nike");
  const [category, setCategory] = useState("t-shirt");
  const [gender, setGender] = useState("men");
  const [market, setMarket] = useState("");
  const [unit, setUnit] = useState<"cm" | "in">(
    auth.user?.measurement_unit ?? "cm",
  );
  const factor = unit === "in" ? 2.54 : 1;
  const [apparel, setApparel] = useState("");
  const [chart, setChart] = useState<Chart>();
  const [result, setResult] = useState<Recommendation>();
  const [selected, setSelected] = useState("");
  const [modal, setModal] = useState(false);
  const [login, setLogin] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [saving, setSaving] = useState(false);
  const [manual, setManual] = useState(!active.measurements);
  const brand = brands.find((b) => b.brand_id === brandId);
  const options =
    brand?.available_charts.filter(
      (c) =>
        c.category === category &&
        (!market || c.market === market) &&
        (c.gender === gender || c.gender === "unisex"),
    ) ?? [];
  const metrics = chart
    ? (chart.active_metrics ?? (Object.keys(chart.sizes[0].bounds) as Metric[]))
    : (Object.keys(metricLabels) as Metric[]);
  const valid =
    !!active.measurements &&
    metrics.every((key) => {
      const n = active.measurements![key];
      return (
        Number.isFinite(n) &&
        n > 0 &&
        n <=
          (key === "shoulder_width" ? 100 : key === "inseam_length" ? 200 : 400)
      );
    });
  async function load() {
    setLoading(true);
    setError("");
    try {
      setBrands(await sizingService.brands());
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  useEffect(() => {
    setApparel(options[0]?.apparel_id ?? "");
    setResult(undefined);
  }, [brandId, category, gender, market, brands]);
  useEffect(() => {
    let stopped = false;
    setChart(undefined);
    setResult(undefined);
    const summary = options.find((c) => c.apparel_id === apparel);
    if (summary)
      sizingService
        .chart(summary)
        .then((data) => {
          if (!stopped) setChart(data);
        })
        .catch((e) => {
          if (!stopped) setError(e.message);
        });
    return () => {
      stopped = true;
    };
  }, [apparel, brandId, category, gender, market, brands]);
  useEffect(() => {
    setResult(undefined);
  }, [active.measurements]);
  async function run() {
    if (!chart || !active.measurements) return;
    setBusy(true);
    setError("");
    try {
      const next = await sizingService.recommend(chart, active.measurements);
      setResult(next);
      setSelected(next.recommended_size);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function save() {
    if (!auth.user) {
      setLogin(true);
      return;
    }
    if (!chart || !active.measurements) return;
    setSaving(true);
    try {
      await sizingService.save(chart, active.measurements);
      toast("Size saved to My Closet.");
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
          <span className="eyebrow">02 / FIND YOUR BRAND FIT</span>
          <h1>
            Different brands.
            <br className="mobile-only" /> <em>Your size.</em>
          </h1>
          <p>
            Match your measurements to a real size guide, one detail at a time.
          </p>
        </div>
        <Link className="button secondary" to="/measure">
          <Ruler size={16} />
          Review measurements
        </Link>
      </div>
      <div className="sizing-layout">
        <aside className="card sizing-controls">
          <span className="eyebrow">MAKE IT PERSONAL</span>
          <h2>Find your fit.</h2>
          {loading ? (
            <Skeleton label="Loading brand guides…" />
          ) : (
            <div className="stack">
              <label className="field">
                Brand
                <select
                  aria-label="Brand"
                  disabled={busy}
                  value={brandId}
                  onChange={(e) => setBrandId(e.target.value)}
                >
                  {brands.map((b) => (
                    <option key={b.brand_id} value={b.brand_id}>
                      {b.brand_name}
                      {!b.recommendation_available
                        ? " · guide unavailable"
                        : ""}
                    </option>
                  ))}
                </select>
              </label>
              <div className="two-fields">
                <label className="field">
                  Collection
                  <select
                    disabled={busy}
                    value={gender}
                    onChange={(e) => setGender(e.target.value)}
                  >
                    <option value="men">Men</option>
                    <option value="women">Women</option>
                  </select>
                </label>
                <label className="field">
                  Category
                  <select
                    disabled={busy}
                    value={category}
                    onChange={(e) => setCategory(e.target.value)}
                  >
                    {categories.map(([v, l]) => (
                      <option key={v} value={v}>
                        {l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <label className="field">
                Country / region
                <select
                  aria-label="Country / region"
                  value={market}
                  onChange={(e) => setMarket(e.target.value)}
                  disabled={busy}
                >
                  <option value="">All published markets</option>
                  {[
                    ...new Set([
                      "IN",
                      ...(brand?.available_charts.map((c) => c.market) ?? []),
                    ]),
                  ].map((m) => (
                    <option value={m} key={m}>
                      {marketName(m)}
                    </option>
                  ))}
                </select>
              </label>
              {options.length > 0 ? (
                <label className="field">
                  Product size guide
                  <select
                    disabled={busy}
                    value={apparel}
                    onChange={(e) => setApparel(e.target.value)}
                  >
                    {options.map((c) => (
                      <option value={c.apparel_id} key={c.apparel_id}>
                        {marketName(c.market)} · {c.source || c.apparel_id}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <div className="notice">
                  No verified body chart is available for this brand, category
                  and collection. Choose another guide; we won’t invent size
                  ranges.
                  {brand?.available_charts.map((c) => (
                    <button
                      key={c.apparel_id}
                      className="text-button"
                      onClick={() => {
                        setCategory(c.category);
                        setGender(c.gender === "unisex" ? "men" : c.gender);
                        setMarket(c.market);
                      }}
                    >
                      View {c.category} · {c.gender} · {marketName(c.market)}
                    </button>
                  ))}
                </div>
              )}
              {chart && <ChartProvenance chart={chart} />}
              {chart && (
                <button className="text-button" onClick={() => setModal(true)}>
                  Explore the size chart ↗
                </button>
              )}
              <div className="divider" />
              <label className="field">
                Measurement units
                <select
                  aria-label="Measurement units"
                  value={unit}
                  onChange={(e) => setUnit(e.target.value as "cm" | "in")}
                >
                  <option value="cm">Centimetres</option>
                  <option value="in">Inches</option>
                </select>
              </label>
              <details className="estimate-details">
                <summary>How to measure</summary>
                <p>
                  Keep the tape level around the fullest chest and hips and the
                  natural waist. Measure shoulders tip to tip. Measure the upper
                  thigh around its fullest part. Check the source instructions
                  for inseam: some guides use the ankle, others the floor.
                </p>
                <p>
                  Use tape measurements when possible. Image-derived values are
                  estimates and can be affected by clothing and pose.
                </p>
              </details>
              <div className="row-between">
                <strong>Your measurements</strong>
                <button
                  className="text-button"
                  onClick={() => setManual(!manual)}
                  aria-expanded={manual}
                >
                  {manual ? "Collapse" : "Edit values"}
                </button>
              </div>
              {manual ? (
                <div className="manual-grid">
                  {metrics.map((key) => (
                    <label className="field" key={key}>
                      {metricLabels[key]}
                      <div className="input-unit">
                        <input
                          disabled={busy}
                          type="number"
                          aria-label={metricLabels[key]}
                          step=".1"
                          min="0.1"
                          max={
                            (key === "shoulder_width"
                              ? 100
                              : key === "inseam_length"
                                ? 200
                                : 400) / factor
                          }
                          value={
                            active.measurements?.[key]
                              ? Number(
                                  (active.measurements[key] / factor).toFixed(
                                    2,
                                  ),
                                )
                              : ""
                          }
                          onChange={(e) => {
                            const empty = Object.fromEntries(
                              Object.keys(metricLabels).map((k) => [k, 0]),
                            ) as Measurements;
                            active.setMeasurements({
                              ...empty,
                              ...active.measurements,
                              [key]: Number(e.target.value) * factor,
                            });
                            active.setEdited(true);
                          }}
                        />
                        <span>{unit}</span>
                      </div>
                    </label>
                  ))}
                </div>
              ) : (
                <div className="measurement-summary">
                  {active.measurements ? (
                    <>
                      <Check size={17} />
                      <span>
                        Values from your{" "}
                        {active.edited
                          ? "corrected measurements"
                          : "latest scan"}
                        .
                      </span>
                    </>
                  ) : (
                    <p>Extract measurements or enter tape measurements here.</p>
                  )}
                </div>
              )}
              <button
                className="button"
                disabled={
                  !chart ||
                  chart.measurement_basis === "garment" ||
                  !valid ||
                  busy
                }
                onClick={() => void run()}
              >
                {busy ? <LoaderCircle size={17} className="spin" /> : null}
                {busy ? "Comparing sizes…" : "Find my size"}
                <ArrowRight size={17} />
              </button>
              <small>
                Six-metric engine. Only dimensions published by the selected
                guide are scored.
              </small>
            </div>
          )}
          {error && <ErrorNotice message={error} retry={() => void load()} />}
        </aside>
        <section className="size-results">
          {result && chart ? (
            <>
              <div className="recommendation-hero">
                <div>
                  <span className="eyebrow">YOUR CLOSEST CHART MATCH</span>
                  <div className="size-hero">
                    <span>Size</span>
                    <strong data-testid="recommended-size">
                      {result.recommended_size}
                    </strong>
                  </div>
                  <p>
                    {chart.brand_name} · {category} · {gender}
                  </p>
                  <span className="badge inverse">
                    Weighted error {result.minimum_error.toFixed(4)}
                  </span>
                </div>
                <div className="size-hero-art" aria-hidden="true">
                  <Ruler size={80} strokeWidth={0.65} />
                </div>
              </div>
              <div className="card">
                <FitConfidenceGauge value={result.fit_confidence} />
                {result.size_rankings[1] && (
                  <p className="fine-print">
                    Next closest chart match: {result.size_rankings[1].size}.
                    Compare its dimensions below; a closer score is not a
                    guarantee of comfort or fit.
                  </p>
                )}
                <div className="divider" />
                <div className="section-heading">
                  <h3>A closer look at the fit.</h3>
                  <button
                    className="text-button"
                    onClick={() => setModal(true)}
                  >
                    Size guide ↗
                  </button>
                </div>
                <div className="size-tabs" aria-label="Compare candidate sizes">
                  {result.size_rankings.map((r) => (
                    <button
                      key={r.size}
                      className={selected === r.size ? "active" : ""}
                      aria-pressed={selected === r.size}
                      onClick={() => setSelected(r.size)}
                    >
                      {r.size}
                      {r.size === result.recommended_size && (
                        <Check size={13} />
                      )}
                    </button>
                  ))}
                </div>
                <DeviationHeatmap result={result} size={selected} />
                <details className="estimate-details">
                  <summary>How this recommendation is calculated</summary>
                  <p>
                    Each measurement is compared with the midpoint of its size
                    range. Relative deviations are weighted and added. The
                    lowest error wins. Fit confidence = 100 / (1 + error).
                  </p>
                  <p>
                    Base weights: shoulder 20%, chest 25%, waist 20%, hip 20%,
                    thigh 10%, inseam 5%. Available dimensions are normalized to
                    100%.
                  </p>
                  {result.warnings.map((w) => (
                    <p key={w}>{w}</p>
                  ))}
                </details>
                <div className="actions">
                  <button
                    className="button secondary"
                    disabled={saving}
                    onClick={() => void save()}
                  >
                    {saving ? "Saving…" : "Save to My Closet"}
                  </button>
                  <Link className="button" to="/tryon">
                    Try the look <ArrowRight size={16} />
                  </Link>
                </div>
              </div>
            </>
          ) : (
            <div className="card size-empty">
              <div className="size-illustration" aria-hidden="true">
                <span>S</span>
                <span>M</span>
                <span>L</span>
              </div>
              <EmptyState title="Your next size, with less guesswork.">
                Choose a brand guide and add your measurements. See your closest
                size and exactly how each dimension compares.
              </EmptyState>
              <div className="size-explainer">
                <span>
                  01 <strong>Pick a guide</strong>
                </span>
                <span>
                  02 <strong>Compare dimensions</strong>
                </span>
                <span>
                  03 <strong>Find your fit</strong>
                </span>
              </div>
            </div>
          )}
        </section>
      </div>
      {chart && (
        <SizeChartModal
          chart={chart}
          open={modal}
          onClose={() => setModal(false)}
          selected={selected}
          onSelect={(size) => {
            setSelected(size);
            setModal(false);
          }}
        />
      )}
      <AuthModal open={login} onClose={() => setLogin(false)} />
    </>
  );
}
