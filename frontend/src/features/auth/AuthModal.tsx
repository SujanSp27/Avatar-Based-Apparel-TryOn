import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { authService } from "../../services/authService";
import { safeReturn } from "../../utils/images";
import { useAuth } from "./AuthProvider";
import Modal from "../../components/ui/Modal";
import { ErrorNotice } from "../../components/feedback/Feedback";
import { ArrowRight, Check, LoaderCircle } from "../../icons";
export const passwordRules = [
  { label: "12 characters", test: (s: string) => s.length >= 12 },
  {
    label: "Upper & lowercase",
    test: (s: string) => /[A-Z]/.test(s) && /[a-z]/.test(s),
  },
  { label: "Number", test: (s: string) => /\d/.test(s) },
  { label: "Symbol", test: (s: string) => /[^a-zA-Z0-9\s]/.test(s) },
];
function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState("");
  return (
    <form
      className="stack"
      onSubmit={async (e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        try {
          setDone((await authService.forgot(email)).message);
        } catch (e) {
          setError((e as Error).message);
        } finally {
          setBusy(false);
        }
      }}
    >
      <p>
        Enter your account email. We’ll send a secure, single-use reset link.
      </p>
      <label className="field">
        Email address
        <input
          type="email"
          required
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </label>
      {error && <ErrorNotice message={error} />}{" "}
      {done ? (
        <div className="notice" role="status">
          {done}
        </div>
      ) : (
        <button className="button" disabled={busy}>
          {busy ? "Sending…" : "Send reset link"}
        </button>
      )}
    </form>
  );
}
export function AuthForm({
  mode,
  onDone,
}: {
  mode: "login" | "signup";
  onDone?: () => void;
}) {
  const signup = mode === "signup";
  const auth = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [error, setError] = useState("");
  const [forgot, setForgot] = useState(false);
  const schema = z
    .object({
      name: z.string().optional(),
      email: z.email("Enter a valid email address."),
      password: z.string().min(1, "Enter your password.").max(128),
      confirm: z.string().optional(),
      terms: z.boolean().optional(),
      remember: z.boolean().optional(),
    })
    .superRefine((data, ctx) => {
      if (signup) {
        if (!data.name || data.name.trim().length < 2)
          ctx.addIssue({
            code: "custom",
            path: ["name"],
            message: "Please enter your name.",
          });
        if (!passwordRules.every((rule) => rule.test(data.password)))
          ctx.addIssue({
            code: "custom",
            path: ["password"],
            message: "Your password must meet all four requirements.",
          });
        if (data.confirm !== data.password)
          ctx.addIssue({
            code: "custom",
            path: ["confirm"],
            message: "Passwords must match.",
          });
        if (!data.terms)
          ctx.addIssue({
            code: "custom",
            path: ["terms"],
            message: "Please read and accept the terms.",
          });
      }
    });
  const {
    register,
    handleSubmit,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({ resolver: zodResolver(schema) });
  const password = watch("password", "");
  return (
    <>
      <form
        className="stack auth-form"
        noValidate
        onSubmit={handleSubmit(async (data) => {
          setError("");
          try {
            auth.accept(
              signup
                ? await authService.signup(
                    data.name!.trim(),
                    data.email,
                    data.password,
                  )
                : await authService.login(
                    data.email,
                    data.password,
                    !!data.remember,
                  ),
            );
            if (onDone) onDone();
            else
              navigate(safeReturn(params.get("returnTo")), { replace: true });
          } catch (e) {
            setError((e as Error).message);
          }
        })}
      >
        {signup && (
          <label className="field">
            Your name
            <input
              {...register("name")}
              aria-label="Your name"
              autoComplete="name"
              aria-invalid={!!errors.name}
            />
            {errors.name && (
              <small className="field-error">{errors.name.message}</small>
            )}
          </label>
        )}
        <label className="field">
          Email address
          <input
            {...register("email")}
            aria-label="Email address"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            aria-invalid={!!errors.email}
          />
          {errors.email && (
            <small className="field-error">{errors.email.message}</small>
          )}
        </label>
        <label className="field">
          Password
          <input
            {...register("password")}
            aria-label="Password"
            type="password"
            autoComplete={signup ? "new-password" : "current-password"}
            aria-invalid={!!errors.password}
          />
          {errors.password && (
            <small className="field-error">{errors.password.message}</small>
          )}
        </label>
        {signup ? (
          <>
            <div
              className="password-strength"
              aria-label="Password requirements"
            >
              <div className="strength-track">
                <span
                  style={{
                    width: `${passwordRules.filter((r) => r.test(password)).length * 25}%`,
                  }}
                />
              </div>
              <div className="password-rules">
                {passwordRules.map((rule) => (
                  <span key={rule.label} data-met={rule.test(password)}>
                    <Check size={12} />
                    {rule.label}
                  </span>
                ))}
              </div>
            </div>
            <label className="field">
              Confirm password
              <input
                {...register("confirm")}
                aria-label="Confirm password"
                type="password"
                autoComplete="new-password"
                aria-invalid={!!errors.confirm}
              />
              {errors.confirm && (
                <small className="field-error">{errors.confirm.message}</small>
              )}
            </label>
            <label className="check-label">
              <input type="checkbox" {...register("terms")} />
              <span>
                I accept the{" "}
                <Link to="/terms" target="_blank">
                  terms & privacy notice
                </Link>
                .
              </span>
            </label>
            {errors.terms && (
              <small className="field-error">{errors.terms.message}</small>
            )}
          </>
        ) : (
          <div className="row-between">
            <label className="check-label">
              <input type="checkbox" {...register("remember")} />
              Remember me
            </label>
            <button
              type="button"
              className="text-button"
              onClick={() => setForgot(true)}
            >
              Forgot password?
            </button>
          </div>
        )}
        {error && <ErrorNotice message={error} />}
        <button className="button" disabled={isSubmitting}>
          {isSubmitting ? <LoaderCircle className="spin" size={18} /> : null}
          {signup ? "Create your account" : "Sign in"}
          <ArrowRight size={17} />
        </button>
      </form>
      <Modal
        open={forgot}
        onClose={() => setForgot(false)}
        title="Reset your password"
      >
        <ForgotPassword />
      </Modal>
    </>
  );
}
export default function AuthModal({
  open,
  onClose,
}: {
  open: boolean;
  onClose: () => void;
}) {
  const [mode, setMode] = useState<"login" | "signup">("login");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={mode === "login" ? "Welcome back" : "Your personal fit profile"}
    >
      <p className="muted">
        Save measurements and keep your brand sizes in one place.
      </p>
      <AuthForm key={mode} mode={mode} onDone={onClose} />
      <p className="auth-switch">
        {mode === "login" ? "New to the studio?" : "Already have an account?"}{" "}
        <button
          className="text-button"
          onClick={() => setMode(mode === "login" ? "signup" : "login")}
        >
          {mode === "login" ? "Create account" : "Sign in"}
        </button>
      </p>
    </Modal>
  );
}
export function AuthPage({ mode }: { mode: "login" | "signup" }) {
  return (
    <div className="auth-page">
      <div className="auth-editorial">
        <span className="eyebrow">A BETTER FIT STARTS WITH YOU</span>
        <h1>
          Made for
          <br />
          <em>your shape.</em>
        </h1>
        <p>
          One personal profile. Thoughtful size advice.
          <br />A little more confidence in every choice.
        </p>
        <div className="auth-orbit">
          <span>F</span>
          <span>F</span>
        </div>
        <small>Your measurements stay in your private profile.</small>
      </div>
      <section className="auth-panel">
        <span className="eyebrow">FORMFIT MEMBERSHIP</span>
        <h2>
          {mode === "login"
            ? "Good to see you again."
            : "Make room for a better fit."}
        </h2>
        <p className="muted">
          {mode === "login"
            ? "Sign in to your measurements and saved sizes."
            : "Create an account to keep your results together."}
        </p>
        <AuthForm key={mode} mode={mode} />
        <p className="auth-switch">
          {mode === "login" ? "New here?" : "Already a member?"}{" "}
          <Link to={mode === "login" ? "/signup" : "/login"}>
            {mode === "login" ? "Create an account" : "Sign in"}
          </Link>
        </p>
        <Link className="guest-link" to="/measure">
          Continue as a guest <ArrowRight size={14} />
        </Link>
      </section>
    </div>
  );
}
