import { useEffect, useState } from "react";
import { apiError, type Brand } from "./types";

type Sizing = { recommendedSize: string; score: number; explanation: Record<string,string>; chartSource: string };
export default function SizeRecommendation() {
  const [brands, setBrands] = useState<Brand[]>([]);
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("t-shirt");
  const [fit, setFit] = useState("regular");
  const [values, setValues] = useState({chest: "", waist: "", hip: "", shoulderWidth: ""});
  const [result, setResult] = useState<Sizing>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { fetch("/api/brands").then(async r => { if (!r.ok) throw new Error(await apiError(r)); return r.json(); }).then((rows: Brand[]) => { setBrands(rows); setBrand(String(rows[0]?.id ?? "")); }).catch(() => setError("Size charts could not be loaded.")); }, []);
  async function recommend() {
    setBusy(true); setError(""); setResult(undefined);
    try {
      const measurements = Object.fromEntries(Object.entries(values).filter(([,v]) => v !== "").map(([k,v]) => [k,Number(v)]));
      const r = await fetch("/api/sizing/recommend", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({brandId:Number(brand),garmentCategory:category,fitPreference:fit,measurements})});
      if (!r.ok) throw new Error(await apiError(r));
      setResult(await r.json());
    } catch (e) { setError((e as Error).message); } finally { setBusy(false); }
  }
  return <details className="size-tool"><summary>Size recommendation (optional)</summary><p>Enter tape measurements in cm. This runs independently of image generation. Demo charts are fictional.</p>
    <label>Brand<select aria-label="Brand" value={brand} onChange={e=>{setBrand(e.target.value);setResult(undefined);}}>{brands.map(b=><option value={b.id} key={b.id}>{b.name}{b.isDemo ? " (demo)" : ""}</option>)}</select></label>
    <label>Size chart category<select value={category} onChange={e=>{setCategory(e.target.value);setResult(undefined);}}>{["t-shirt","shirt","dress","trouser"].map(c=><option key={c}>{c}</option>)}</select></label>
    <label>Fit preference<select value={fit} onChange={e=>{setFit(e.target.value);setResult(undefined);}}>{["tight","regular","loose"].map(f=><option key={f}>{f}</option>)}</select></label>
    {Object.entries(values).map(([key,value])=><label key={key}>{key === "shoulderWidth" ? "Shoulders (optional)" : key}<input aria-label={`${key} measurement`} type="number" min="1" max="300" step="0.1" value={value} onChange={e=>{setValues({...values,[key]:e.target.value});setResult(undefined);}}/></label>)}
    <button onClick={recommend} disabled={busy || !brand || !values.chest || !values.waist || !values.hip}>{busy ? "Checking chart…" : "Recommend size"}</button>
    {error && <p role="alert">{error}</p>}{result && <div className="size-result"><strong data-testid="recommended-size">{result.recommendedSize}</strong>{Object.entries(result.explanation).map(([k,v])=><p key={k}>{k}: {v}</p>)}<p>Distance score {result.score.toFixed(3)} · lower is better</p><p>{result.chartSource}</p></div>}
  </details>;
}
