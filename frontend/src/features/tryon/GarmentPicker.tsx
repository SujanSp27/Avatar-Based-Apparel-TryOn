import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, Check } from "../../icons";
import ProductImage from "../catalog/ProductImage";
export type Garment = {
  id: string;
  name: string;
  category: string;
  photoType: string;
  imageUrl: string;
  description: string;
  tryon_supported?: boolean;
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
    fetch(
      `/api/v1/products?limit=12&sort=newest&tryon_supported=true${filter === "all" ? "" : `&category=${encodeURIComponent(filter)}`}`,
      {
        signal: controller.signal,
      },
    )
      .then(async (r) => {
        if (!r.ok) throw new Error();
        const data = await r.json();
        if (active) setItems(data.items);
      })
      .catch(() => {
        if (active) setError(true);
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
  }, [retry, filter]);
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
          <option value="t-shirt">Tops & polos</option>
          <option value="blouse">Blouses</option>
          <option value="dress">Dresses</option>
          <option value="skirt">Skirts</option>
          <option value="shirt">Shirts</option>
          <option value="jeans">Jeans</option>
          <option value="trouser">Trousers</option>
          <option value="shorts">Shorts</option>
          <option value="sweater">Sweaters & hoodies</option>
          <option value="jacket">Jackets</option>
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
          {!items.length && (
            <p>
              No published garments yet. Upload a supported garment photo to
              continue.
            </p>
          )}
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
                    {item.photoType === "model"
                      ? "Worn garment reference"
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
            No garments in this collection yet. Upload your own to try this
            category.
          </p>
        )}
    </section>
  );
}
