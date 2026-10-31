import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "../../icons";
import ProductImage from "../catalog/ProductImage";
import { DISCOVERED_GARMENTS } from "../catalog/discoveredGarments";
export type Garment = {
  id: string;
  name: string;
  category: string;
  photoType: string;
  imageUrl: string;
  referenceImageUrl?: string;
  displayImage?: { photoType: string } | null;
  description: string;
  tryon_supported?: boolean;
  qualityReview?: {
    status: "approved" | "unreviewed" | "unsupported" | "stale";
    message: string;
  };
};
export default function GarmentPicker({
  disabled,
  selected,
  onSelect,
}: {
  disabled: boolean;
  selected?: string;
  onSelect: (garment: Garment) => void;
}) {
  const [items, setItems] = useState<Garment[]>([]);
  const [filter, setFilter] = useState("all");
  const [error, setError] = useState(false);
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  useEffect(() => {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    let active = true;
    setLoading(true);
    setError(false);
    fetch("/api/v1/products?limit=48&sort=newest&tryon_supported=true", {
      signal: controller.signal,
    })
      .then(async (r) => {
        if (!r.ok) throw new Error();
        const data = await r.json();
        if (active) {
          const apiItems: Garment[] = data.items || [];
          const existingIds = new Set(apiItems.map((item) => item.id));
          const combined = [
            ...DISCOVERED_GARMENTS.filter((g) => !existingIds.has(g.id)),
            ...apiItems,
          ];
          setItems(combined);
          setFilter((current) =>
            combined.some((item: Garment) => item.category === current)
              ? current
              : "all",
          );
        }
      })
      .catch(() => {
        if (active) {
          setItems(DISCOVERED_GARMENTS);
          setError(false);
        }
      })
      .finally(() => {
        clearTimeout(timer);
        if (active) setLoading(false);
      });
    return () => {
      active = false;
      clearTimeout(timer);
      controller.abort();
    };
  }, [retry]);
  const labels: Record<string, string> = {
    "t-shirt": "Tops & polos",
    blouse: "Blouses",
    dress: "Dresses",
    skirt: "Skirts",
    shirt: "Shirts",
    jeans: "Jeans",
    trouser: "Trousers",
    shorts: "Shorts",
    sweater: "Sweaters & hoodies",
    jacket: "Jackets",
    jumpsuit: "Jumpsuits",
  };
  return (
    <section className="card garment-catalog">
      <div className="section-heading">
        <div>
          <h3>Discover another look</h3>
          <p className="muted">Select a real garment, or upload your own.</p>
          <Link className="text-button" to="/catalog">
            Browse the full collection
          </Link>
        </div>
        <select
          aria-label="Filter garment catalog"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        >
          <option value="all">All garments</option>
          {[...new Set(items.map((item) => item.category))]
            .sort()
            .map((category) => (
              <option key={category} value={category}>
                {labels[category] || category}
              </option>
            ))}
        </select>
      </div>
      {loading && <p role="status">Loading the collection…</p>}
      {error && (
        <div role="alert">
          <p>The collection could not load. Your uploads still work.</p>
          <button
            className="button secondary"
            onClick={() => setRetry((n) => n + 1)}
          >
            Retry collection
          </button>
        </div>
      )}
      {!loading && !error && (
        <div className="garment-grid">
          {items
            .filter((item) => filter === "all" || item.category === filter)
            .map((item) => (
              <button
                className="catalog-item"
                key={item.id}
                disabled={disabled}
                aria-pressed={selected === item.id}
                onClick={() => onSelect(item)}
              >
                <div className="catalog-photo">
                  <ProductImage src={item.imageUrl} alt={item.name} />
                  {selected === item.id && (
                    <span>
                      <Check size={15} />
                      Selected
                    </span>
                  )}
                </div>
                <div className="catalog-copy">
                  <strong>{item.name}</strong>
                  <span>{item.description}</span>
                  <small>
                    {(item.displayImage?.photoType ?? item.photoType) ===
                    "model"
                      ? "Model photograph"
                      : "Product photograph"}
                    <ArrowRight size={15} />
                  </small>
                </div>
              </button>
            ))}
        </div>
      )}
      {!loading &&
        !error &&
        !items.some((item) => filter === "all" || item.category === filter) && (
          <p>
            No approved garments in this collection yet. You can upload your own
            supported garment; generated results still require review.
          </p>
        )}
    </section>
  );
}
