import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { authService } from "../../services/authService";
import { passwordRules } from "./AuthModal";
import { ErrorNotice } from "../../components/feedback/Feedback";
export default function ResetPassword() {
  const [token] = useState(
    () => new URLSearchParams(window.location.hash.slice(1)).get("token") ?? "",
  );
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    window.history.replaceState(null, "", window.location.pathname);
  }, []);
  return (
    <section className="card narrow">
      <span className="eyebrow">ACCOUNT RECOVERY</span>
      <h1>A fresh start.</h1>
      {done ? (
        <>
          <p>Password updated. All earlier sessions have been signed out.</p>
          <Link className="button" to="/login">
            Sign in
          </Link>
        </>
      ) : (
        <form
          className="stack"
          onSubmit={async (e) => {
            e.preventDefault();
            setError("");
            if (
              !passwordRules.every((r) => r.test(password)) ||
              password !== confirm
            ) {
              setError(
                "Use 12+ characters, uppercase, lowercase, a number and a symbol. Both passwords must match.",
              );
              return;
            }
            setBusy(true);
            try {
              await authService.reset(token, password);
              setDone(true);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {!token && (
            <ErrorNotice message="Open the complete reset link from your email." />
          )}
          <label className="field">
            New password
            <input
              type="password"
              autoComplete="new-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <label className="field">
            Confirm new password
            <input
              type="password"
              autoComplete="new-password"
              required
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          </label>
          <small>
            12+ characters · uppercase · lowercase · number · symbol
          </small>
          {error && <ErrorNotice message={error} />}
          <button className="button" disabled={busy || !token}>
            {busy ? "Updating…" : "Update password"}
          </button>
        </form>
      )}
    </section>
  );
}
