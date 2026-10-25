import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../services/api/client";
import { useAuth } from "../auth/AuthProvider";
import {
  ErrorNotice,
  EmptyState,
  Skeleton,
} from "../../components/feedback/Feedback";
import Modal from "../../components/ui/Modal";
import { useToast } from "../../components/ui/Toast";
import type { Garment } from "../tryon/GarmentPicker";

export type Product = Garment & {
  brand_name: string;
  audience: string;
  colors: string[];
  sizes: string[];
  size_note: string;
  license: string;
  source_url: string;
  commercial_use: boolean;
};
type Page = { items: Product[]; total: number; limit: number; offset: number };
type Category = {
  id: string;
  name: string;
  group: string;
  model_category: string | null;
  support_note: string;
};
export default function CatalogPage() {
  const [query, setQuery] = useState("");
  const [brand, setBrand] = useState("");
  const [category, setCategory] = useState("");
  const [audience, setAudience] = useState("");
  const [sort, setSort] = useState("relevance");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page>();
  const [brands, setBrands] = useState<
    { id: string; name: string; product_count: number }[]
  >([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [selected, setSelected] = useState<Product>();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [saving, setSaving] = useState(false);
  const auth = useAuth(),
    navigate = useNavigate(),
    toast = useToast();
  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      api<typeof brands>("/api/v1/brands", { signal: controller.signal }),
      api<Category[]>("/api/v1/categories", { signal: controller.signal }),
    ])
      .then(([b, c]) => {
        setBrands(b);
        setCategories(c);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [retry]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    const timer = setTimeout(() => {
      const params = new URLSearchParams({
        q: query,
        sort,
        offset: String(offset),
        limit: "12",
      });
      if (brand) params.set("brand_id", brand);
      if (category) params.set("subcategory", category);
      if (audience) params.set("audience", audience);
      api<Page>(`/api/v1/products?${params}`, { signal: controller.signal })
        .then(setPage)
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, brand, category, audience, sort, offset, retry]);
  const filter = (set: (v: string) => void, value: string) => {
    set(value);
    setOffset(0);
  };
  const support = categories.find((c) => c.id === category);
  return (
    <>
      <header className="page-heading">
        <div>
          <span className="eyebrow">THE VASTRAVIEW EDIT</span>
          <h1>A wardrobe worth exploring.</h1>
          <p>
            Discover garment references, compare your size, and see a new look
            on you.
          </p>
        </div>
      </header>
      <section className="card catalog-filters" aria-label="Filter apparel">
        <label className="field catalog-search">
          Search apparel
          <input
            type="search"
            placeholder="Garment name or brand"
            value={query}
            onChange={(e) => filter(setQuery, e.target.value)}
          />
        </label>
        <label className="field">
          Brand
          <select
            aria-label="Brand"
            value={brand}
            onChange={(e) => filter(setBrand, e.target.value)}
          >
            <option value="">All brands</option>
            {brands.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name} ({b.product_count})
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Garment type
          <select
            aria-label="Garment type"
            value={category}
            onChange={(e) => filter(setCategory, e.target.value)}
          >
            <option value="">All types</option>
            {categories.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Audience
          <select
            aria-label="Audience"
            value={audience}
            onChange={(e) => filter(setAudience, e.target.value)}
          >
            <option value="">Everyone</option>
            <option value="men">Men</option>
            <option value="women">Women</option>
            <option value="unisex">Unisex</option>
          </select>
        </label>
        <label className="field">
          Sort by
          <select
            aria-label="Sort by"
            value={sort}
            onChange={(e) => filter(setSort, e.target.value)}
          >
            <option value="relevance">Relevance</option>
            <option value="name">Name</option>
            <option value="newest">Newest</option>
          </select>
        </label>
      </section>
      <p className="fine-print">
        Brand names are a discovery directory, not partnerships or a promise of
        stock. Reference images carry their source and usage information.
      </p>
      {support && !support.model_category && (
        <div className="notice">{support.support_note}</div>
      )}
      {error && (
        <ErrorNotice message={error} retry={() => setRetry((n) => n + 1)} />
      )}
      {loading ? (
        <Skeleton label="Opening the collection…" />
      ) : (
        !error && (
          <>
            {!page?.items.length ? (
              <div className="card">
                <EmptyState title="No published garments match these filters.">
                  Try another selection or{" "}
                  <Link to="/tryon">upload your own garment</Link>. New brands
                  appear here when sourced products are available.
                </EmptyState>
              </div>
            ) : (
              <div className="discovery-grid">
                {page.items.map((p) => (
                  <article className="card product-card" key={p.id}>
                    <button
                      className="product-image"
                      onClick={() => setSelected(p)}
                      aria-label={`View ${p.name}`}
                    >
                      <img src={p.imageUrl} alt={p.name} loading="lazy" />
                    </button>
                    <div className="product-info">
                      <span className="eyebrow">{p.brand_name}</span>
                      <h2>{p.name}</h2>
                      <p>{p.description}</p>
                      <div className="row-between">
                        <small>
                          {p.audience} · {p.colors.join(", ")}
                        </small>
                        <button
                          className="text-button"
                          onClick={() => setSelected(p)}
                        >
                          Details
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            )}
            <div className="pagination">
              <button
                className="button secondary small"
                disabled={!offset}
                onClick={() => setOffset((n) => Math.max(0, n - 12))}
              >
                Previous
              </button>
              <span>{page?.total ?? 0} garments</span>
              <button
                className="button secondary small"
                disabled={offset + 12 >= (page?.total ?? 0)}
                onClick={() => setOffset((n) => n + 12)}
              >
                Next
              </button>
            </div>
          </>
        )
      )}
      <Modal
        open={!!selected}
        onClose={() => setSelected(undefined)}
        title={selected?.name ?? "Garment details"}
      >
        {selected && (
          <div className="stack">
            <img
              className="product-detail-photo"
              src={selected.imageUrl}
              alt={selected.name}
            />
            <span className="eyebrow">{selected.brand_name}</span>
            <p>{selected.description}</p>
            <p>
              Colors: {selected.colors.join(", ")}
              <br />
              Sizes:{" "}
              {selected.sizes.length
                ? selected.sizes.join(", ")
                : selected.size_note}
            </p>
            <small>{selected.license}</small>
            <a
              className="text-button"
              href={selected.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Image source and attribution ↗
            </a>
            <div className="actions">
              <button
                className="button"
                onClick={() =>
                  navigate(`/tryon?product=${encodeURIComponent(selected.id)}`)
                }
              >
                Try this garment
              </button>
              <button
                className="button secondary"
                disabled={saving}
                onClick={async () => {
                  if (!auth.user) {
                    navigate("/login?returnTo=/catalog");
                    return;
                  }
                  setSaving(true);
                  try {
                    await api(`/api/v1/favorites/${selected.id}`, {
                      method: "PUT",
                    });
                    toast("Saved to your favorites.");
                  } catch (e) {
                    toast((e as Error).message);
                  } finally {
                    setSaving(false);
                  }
                }}
              >
                Save favorite
              </button>
            </div>
            <Link to="/sizing">Check a sourced brand size guide</Link>
          </div>
        )}
      </Modal>
    </>
  );
}
