import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api, jsonBody } from "../../services/api/client";
import { ErrorNotice } from "../../components/feedback/Feedback";
import Modal from "../../components/ui/Modal";
import { useAuth } from "../auth/AuthProvider";
import { useToast } from "../../components/ui/Toast";
import type { Product } from "../catalog/CatalogPage";
import type { Result } from "../../types";
type Session = {
  id: string;
  created_at: string | null;
  expires_at: string;
  current: boolean;
};
type History = {
  items: { id: string; status: string; created_at: string; result?: Result }[];
  has_more: boolean;
};
export default function AccountPrivacy() {
  const auth = useAuth(),
    navigate = useNavigate(),
    toast = useToast();
  const [sessions, setSessions] = useState<Session[]>([]),
    [favorites, setFavorites] = useState<Product[]>([]);
  const [history, setHistory] = useState<History>({
    items: [],
    has_more: false,
  });
  const [offset, setOffset] = useState(0),
    [favoriteOffset, setFavoriteOffset] = useState(0),
    [favoriteTotal, setFavoriteTotal] = useState(0);
  const [error, setError] = useState(""),
    [retry, setRetry] = useState(0),
    [busy, setBusy] = useState(false);
  const [deleting, setDeleting] = useState<string>(),
    [password, setPassword] = useState("");
  useEffect(() => {
    const c = new AbortController();
    setError("");
    Promise.all([
      api<Session[]>("/api/v1/profile/sessions", { signal: c.signal }),
      api<{ items: Product[]; total: number }>(
        `/api/v1/favorites?limit=6&offset=${favoriteOffset}`,
        { signal: c.signal },
      ),
      api<History>(`/api/v1/history?limit=6&offset=${offset}`, {
        signal: c.signal,
      }),
    ])
      .then(([s, f, h]) => {
        setSessions(s);
        setFavorites(f.items);
        setFavoriteTotal(f.total);
        setHistory(h);
      })
      .catch((e) => {
        if (!c.signal.aborted) setError(e.message);
      });
    return () => c.abort();
  }, [retry, offset, favoriteOffset]);
  const mutate = async (path: string) => {
    try {
      await api(path, { method: "DELETE" });
      setRetry((n) => n + 1);
    } catch (e) {
      setError((e as Error).message);
    }
  };
  return (
    <div className="private-account-grid">
      {error && (
        <ErrorNotice message={error} retry={() => setRetry((n) => n + 1)} />
      )}
      <section className="card">
        <h2>Account privacy</h2>
        <p>
          Your saved measurements are private. Only save scans you want to keep;
          you can delete individual scans, results, or your account.
        </p>
        <p>
          Email {auth.user?.email_verified ? "verified" : "not yet verified"}.{" "}
          {!auth.user?.email_verified && (
            <Link to="/verify-email">Verify your email</Link>
          )}
        </p>
        <Link to="/terms">How your photos are processed and retained</Link>
      </section>
      <section className="card">
        <h2>Active sessions</h2>
        {sessions.map((s) => (
          <div className="private-session" key={s.id}>
            <div>
              <strong>
                {s.current ? "This session" : "Another signed-in session"}
              </strong>
              <br />
              <small>
                Expires {new Date(s.expires_at).toLocaleDateString()}
              </small>
            </div>
            <button
              className="button secondary small"
              onClick={async () => {
                if (s.current) {
                  try {
                    await auth.logout();
                    navigate("/login");
                  } catch (e) {
                    setError((e as Error).message);
                  }
                } else await mutate(`/api/v1/profile/sessions/${s.id}`);
              }}
            >
              Sign out
            </button>
          </div>
        ))}
      </section>
      <section>
        <h2>Favorite garments</h2>
        {!favorites.length && (
          <p className="muted">
            No saved garments. <Link to="/catalog">Explore the catalog</Link>.
          </p>
        )}
        <div className="discovery-grid">
          {favorites.map((p) => (
            <article className="card private-history" key={p.id}>
              <img src={p.imageUrl} alt={p.name} loading="lazy" />
              <h3>{p.name}</h3>
              <Link to={`/tryon?product=${encodeURIComponent(p.id)}`}>
                Try this garment
              </Link>
              <button
                className="text-button danger-text"
                onClick={() => void mutate(`/api/v1/favorites/${p.id}`)}
              >
                Remove favorite
              </button>
            </article>
          ))}
        </div>
        {favoriteTotal > 6 && (
          <div className="pagination">
            <button
              className="button secondary small"
              disabled={!favoriteOffset}
              onClick={() => setFavoriteOffset((n) => n - 6)}
            >
              Previous favorites
            </button>
            <button
              className="button secondary small"
              disabled={favoriteOffset + 6 >= favoriteTotal}
              onClick={() => setFavoriteOffset((n) => n + 6)}
            >
              More favorites
            </button>
          </div>
        )}
      </section>
      <section>
        <h2>Your try-on history</h2>
        <p className="muted">
          Results created while signed in appear here. Previous anonymous
          results remain in their original browser session.
        </p>
        {!history.items.length && <p>No results on this page yet.</p>}
        <div className="discovery-grid">
          {history.items.map((h) => (
            <article className="card private-history" key={h.id}>
              {h.result?.previewUrl && (
                <img
                  src={h.result.previewUrl}
                  alt={`Your ${h.result.garmentCategory} try-on`}
                  loading="lazy"
                />
              )}
              <h3>{h.result?.garmentCategory ?? "Try-on"}</h3>
              <p>
                {new Date(h.created_at).toLocaleDateString()} · {h.status}
              </p>
              {h.result && (
                <a
                  className="text-button"
                  href={h.result.previewUrl}
                  download={`vastraview-${h.id}.png`}
                >
                  Download result
                </a>
              )}
              <button
                className="text-button danger-text"
                disabled={h.status === "processing"}
                onClick={() => setDeleting(h.id)}
              >
                Delete photos & result
              </button>
            </article>
          ))}
        </div>
        <div className="pagination">
          <button
            className="button secondary small"
            disabled={!offset}
            onClick={() => setOffset((n) => n - 6)}
          >
            Previous results
          </button>
          <button
            className="button secondary small"
            disabled={!history.has_more}
            onClick={() => setOffset((n) => n + 6)}
          >
            More results
          </button>
        </div>
      </section>
      <section className="card">
        <h2>Delete your account</h2>
        <p>
          Permanently remove your profile, saved measurements, favorites,
          sessions and owned local photos and results. Your Colab runtime and
          external backups follow their separate retention policy.
        </p>
        <button
          className="button secondary danger-text"
          onClick={() => setDeleting("account")}
        >
          Delete account
        </button>
      </section>
      <Modal
        open={!!deleting}
        onClose={() => {
          if (!busy) setDeleting(undefined);
        }}
        title={
          deleting === "account"
            ? "Permanently delete your account?"
            : "Delete these photos and this result?"
        }
      >
        <form
          className="stack"
          onSubmit={async (e) => {
            e.preventDefault();
            setBusy(true);
            setError("");
            try {
              await api(
                deleting === "account"
                  ? "/api/v1/profile"
                  : `/api/v1/history/${deleting}`,
                deleting === "account"
                  ? jsonBody({ password }, "DELETE")
                  : { method: "DELETE" },
              );
              if (deleting === "account") {
                // The server already revoked sessions and cleared cookies.
                // Discard all in-memory private state as we leave the account.
                window.location.replace("/");
                return;
              } else {
                setRetry((n) => n + 1);
                toast("Photos and result deleted.");
              }
              setDeleting(undefined);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <p>
            This cannot be undone. Active inference must finish before deletion.
          </p>
          {deleting === "account" && (
            <label className="field">
              Confirm your password
              <input
                required
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </label>
          )}
          {error && <ErrorNotice message={error} />}
          <div className="actions">
            <button
              type="button"
              className="button secondary"
              disabled={busy}
              onClick={() => setDeleting(undefined)}
            >
              Cancel
            </button>
            <button className="button danger-button" disabled={busy}>
              {busy ? "Deleting…" : "Delete permanently"}
            </button>
          </div>
        </form>
      </Modal>
    </div>
  );
}
