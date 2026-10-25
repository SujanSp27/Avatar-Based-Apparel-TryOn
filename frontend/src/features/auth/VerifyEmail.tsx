import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, jsonBody } from "../../services/api/client";
import { ErrorNotice } from "../../components/feedback/Feedback";
import BrandLogo from "../../components/ui/BrandLogo";

export default function VerifyEmail() {
  const [token] = useState(() => {
    const value =
      new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "";
    return value;
  });
  useEffect(() => {
    history.replaceState(null, "", window.location.pathname);
  }, []);
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <section className="card narrow stack">
      <BrandLogo />
      <h1>Verify your email</h1>
      <p>Keep your measurements and wardrobe personal.</p>
      <form
        className="stack"
        onSubmit={async (e) => {
          e.preventDefault();
          setBusy(true);
          setError("");
          try {
            const r = await api<{ message: string }>(
              `/api/v1/auth/${token ? "verify-email" : "request-verification"}`,
              jsonBody(token ? { token } : { email }),
            );
            setMessage(r.message);
          } catch (e) {
            setError((e as Error).message);
          } finally {
            setBusy(false);
          }
        }}
      >
        {!token && (
          <label className="field">
            Email address
            <input
              required
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
        )}
        {error && <ErrorNotice message={error} />}
        {message ? (
          <p role="status">{message}</p>
        ) : (
          <button className="button" disabled={busy}>
            {busy
              ? "Please wait…"
              : token
                ? "Verify my email"
                : "Send verification link"}
          </button>
        )}
      </form>
      <Link to="/login">Return to sign in</Link>
    </section>
  );
}
