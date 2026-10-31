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
import ProductImage from "./ProductImage";
import {
  filterDiscoveredGarments,
} from "./discoveredGarments";

export type Product = Garment & {
  brand_name: string;
  audience: string;
  colors: string[];
  occasions?: string[];
  sizes: string[];
  size_note: string;
  license: string;
  source_url: string;
  commercial_use: boolean;
  attribution?: string;
  attribution_url?: string;
  license_url?: string;
  displayImage?: {
    source_url: string;
    license: string;
    license_url: string;
    attribution: string;
    attribution_url?: string;
    photoType: string;
  } | null;
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
  const [brand, setBrand] = useState("h-m");
  const [category, setCategory] = useState("");
  const [audience, setAudience] = useState("");
  const [color, setColor] = useState("");
  const [occasion, setOccasion] = useState("");
  const [sort, setSort] = useState("relevance");
  const [offset, setOffset] = useState(0);
  const [page, setPage] = useState<Page>();
  const [brands, setBrands] = useState<
    { id: string; name: string; product_count: number }[]
  >([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [quality, setQuality] = useState<{
    enforced: boolean;
    approvedCount: number;
    targetCount: number;
    message?: string;
  }>();
  const [facets, setFacets] = useState<{
    colors: string[];
    occasions: string[];
  }>({ colors: [], occasions: [] });
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
      api<typeof facets>("/api/v1/catalog/facets", {
        signal: controller.signal,
      }),
      api<NonNullable<typeof quality>>("/api/v1/catalog/quality", {
        signal: controller.signal,
      }),
    ])
      .then(([b, c, f, q]) => {
        const hmBrand = { id: "h-m", name: "H&M", product_count: 14 };
        const bFiltered = b.filter((brand) => brand.id !== "h-m" && brand.name.toLowerCase() !== "h&m");
        setBrands([hmBrand, ...bFiltered]);
        setCategories(
          c.length
            ? c
            : [
                { id: "jeans", name: "Jeans", group: "bottoms", model_category: "jeans", support_note: "Single garment preview." },
                { id: "trouser", name: "Trousers & Formal Trousers", group: "bottoms", model_category: "trouser", support_note: "Single garment preview." },
                { id: "t-shirt", name: "T-Shirts (Full Sleeve & Round Neck)", group: "tops", model_category: "t-shirt", support_note: "Single garment preview." },
                { id: "shirt", name: "Shirts (Half Sleeve & Oversized)", group: "tops", model_category: "shirt", support_note: "Single garment preview." },
                { id: "polo", name: "Polo T-Shirts", group: "tops", model_category: "t-shirt", support_note: "Single garment preview." },
              ],
        );
        setFacets(
          f.colors?.length
            ? f
            : {
                colors: ["beige", "black", "brown", "burgundy", "cream", "pink", "white"],
                occasions: ["business", "casual", "formal", "vacation"],
              },
        );
        setQuality(q);
      })
      .catch(() => {
        setBrands([{ id: "h-m", name: "H&M", product_count: 14 }]);
        setCategories([
          { id: "jeans", name: "Jeans", group: "bottoms", model_category: "jeans", support_note: "Single garment preview." },
          { id: "trouser", name: "Trousers & Formal Trousers", group: "bottoms", model_category: "trouser", support_note: "Single garment preview." },
          { id: "t-shirt", name: "T-Shirts (Full Sleeve & Round Neck)", group: "tops", model_category: "t-shirt", support_note: "Single garment preview." },
          { id: "shirt", name: "Shirts (Half Sleeve & Oversized)", group: "tops", model_category: "shirt", support_note: "Single garment preview." },
          { id: "polo", name: "Polo T-Shirts", group: "tops", model_category: "t-shirt", support_note: "Single garment preview." },
        ]);
        setFacets({
          colors: ["beige", "black", "brown", "burgundy", "cream", "pink", "white"],
          occasions: ["business", "casual", "formal", "vacation"],
        });
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
        limit: "18",
      });
      if (brand) params.set("brand_id", brand);
      if (category) params.set("subcategory", category);
      if (audience) params.set("audience", audience);
      if (color) params.set("color", color);
      if (occasion) params.set("occasion", occasion);

      const fallbackList = filterDiscoveredGarments({
        query,
        brand,
        category,
        audience,
        color,
        occasion,
        sort,
      });

      api<Page>(`/api/v1/products?${params}`, { signal: controller.signal })
        .then((data) => {
          if (!data?.items?.length) {
            setPage({
              items: fallbackList.slice(offset, offset + 18),
              total: fallbackList.length,
              limit: 18,
              offset,
            });
            return;
          }
          const existingIds = new Set(data.items.map((i) => i.id));
          const missing = fallbackList.filter((d) => !existingIds.has(d.id));
          const allItems = [...missing, ...data.items];
          setPage({
            items: allItems.slice(offset, offset + 18),
            total: allItems.length,
            limit: 18,
            offset,
          });
        })
        .catch(() => {
          setPage({
            items: fallbackList.slice(offset, offset + 18),
            total: fallbackList.length,
            limit: 18,
            offset,
          });
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false);
        });
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [query, brand, category, audience, color, occasion, sort, offset, retry]);
  const filter = (set: (v: string) => void, value: string) => {
    set(value);
    setOffset(0);
  };
  const support = categories.find((c) => c.id === category);
  return (
    <>
      <header className="page-heading">
        <div>
          <span className="eyebrow">DISCOVER NOW · H&amp;M COLLECTION</span>
          <h1>Discover Now</h1>
          <p>
            Explore our curated collection of 14 H&amp;M garment references, compare your size, and preview them with personalized virtual try-on.
          </p>
        </div>
      </header>
      {quality?.enforced && quality.approvedCount < quality.targetCount && (
        <div className="notice catalog-quality-notice" role="status">
          <strong>
            {quality.approvedCount} of {quality.targetCount} garments approved
          </strong>
          <p>
            References with unresolved fitting or garment-detail issues are
            excluded from this collection. Your saved results and measurements
            are unchanged.
          </p>
        </div>
      )}
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
          Color
          <select
            aria-label="Color"
            value={color}
            onChange={(e) => filter(setColor, e.target.value)}
          >
            <option value="">All colors</option>
            {facets.colors.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          Occasion
          <select
            aria-label="Occasion"
            value={occasion}
            onChange={(e) => filter(setOccasion, e.target.value)}
          >
            <option value="">All occasions</option>
            {facets.occasions.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
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
      <div className="catalog-summary">
        <p className="fine-print">
          Reference collection · no stock or size availability implied.
        </p>
        {(query || brand || category || audience || color || occasion) && (
          <button
            className="text-button"
            onClick={() => {
              setQuery("");
              setBrand("");
              setCategory("");
              setAudience("");
              setColor("");
              setOccasion("");
              setOffset(0);
            }}
          >
            Clear filters
          </button>
        )}
      </div>
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
                <EmptyState
                  title={
                    quality?.enforced && quality.approvedCount === 0
                      ? "No garments have passed the complete quality review yet."
                      : "No published garments match these filters."
                  }
                >
                  {quality?.enforced && quality.approvedCount === 0
                    ? "You can still "
                    : "Try another selection or "}
                  <Link to="/tryon">upload your own garment</Link>. New brands
                  and garments appear here when their required reviews pass.
                </EmptyState>
              </div>
            ) : (
              <div className="discovery-grid" id="discover-now">
                {page.items.map((p) => (
                  <article className="card product-card" key={p.id}>
                    <button
                      className="product-image"
                      onClick={() => setSelected(p)}
                      aria-label={`View ${p.name}`}
                    >
                      <ProductImage src={p.imageUrl} alt={p.name} />
                    </button>
                    <div className="product-info">
                      <span className="eyebrow">{p.brand_name}</span>
                      <h2>{p.name}</h2>
                      <p>{p.description}</p>
                      <div className="row-between">
                        <small>
                          {p.audience} · {p.colors.join(", ")}
                        </small>
                        <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
                          <button
                            className="text-button"
                            onClick={() => setSelected(p)}
                          >
                            Details
                          </button>
                          <button
                            className="button small"
                            style={{ padding: "6px 12px", fontSize: "13px" }}
                            onClick={() =>
                              navigate(
                                `/tryon?product=${encodeURIComponent(p.id)}`,
                              )
                            }
                          >
                            Try On
                          </button>
                        </div>
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
                onClick={() => setOffset((n) => Math.max(0, n - 18))}
              >
                Previous
              </button>
              <span>{page?.total ?? 0} garments</span>
              <button
                className="button secondary small"
                disabled={offset + 18 >= (page?.total ?? 0)}
                onClick={() => setOffset((n) => n + 18)}
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
            <ProductImage
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
            <small>{selected.displayImage?.license ?? selected.license}</small>
            {(selected.displayImage?.attribution ?? selected.attribution) && (
              <small>
                Photography:{" "}
                {selected.displayImage?.attribution ?? selected.attribution}
              </small>
            )}
            {(selected.displayImage
              ? selected.displayImage.license_url
              : selected.license_url) && (
              <a
                className="text-button"
                href={
                  selected.displayImage
                    ? selected.displayImage.license_url
                    : selected.license_url
                }
                target="_blank"
                rel="noreferrer"
              >
                Photograph license
              </a>
            )}
            {(selected.displayImage
              ? selected.displayImage.attribution_url
              : selected.attribution_url) && (
              <a
                className="text-button"
                href={
                  selected.displayImage
                    ? selected.displayImage.attribution_url
                    : selected.attribution_url
                }
                target="_blank"
                rel="noreferrer"
              >
                Photographer / original seller
              </a>
            )}
            {selected.qualityReview && (
              <p className="notice" role="status">
                <strong>
                  {selected.qualityReview.status === "approved"
                    ? "Reviewed garment"
                    : "Garment quality review"}
                </strong>{" "}
                {selected.qualityReview.message}
              </p>
            )}
            {selected.tryon_supported === false && (
              <p className="notice">
                Editorial inspiration only. The current try-on model has not
                been validated for this layered or draped outfit. You can save
                it or explore the size guides.
              </p>
            )}
            <a
              className="text-button"
              href={selected.displayImage?.source_url ?? selected.source_url}
              target="_blank"
              rel="noreferrer"
            >
              Image source and attribution ↗
            </a>
            {selected.displayImage && selected.referenceImageUrl && (
              <details>
                <summary>View the garment reference used for try-on</summary>
                <ProductImage
                  className="product-detail-photo"
                  src={selected.referenceImageUrl}
                  alt={`${selected.name} — try-on reference`}
                />
                <small>
                  {selected.license}
                  {selected.attribution ? ` · ${selected.attribution}` : ""}
                </small>
                <a
                  className="text-button"
                  href={selected.source_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Reference source and attribution
                </a>
              </details>
            )}
            <div className="actions">
              <button
                className="button"
                disabled={selected.tryon_supported === false}
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
