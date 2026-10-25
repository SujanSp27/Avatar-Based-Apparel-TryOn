import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useAuth } from "../auth/AuthProvider";
import { useMeasurement } from "../measurement/MeasurementProvider";
import { measurementService } from "../../services/measurementService";
import { sizingService } from "../../services/sizingService";
import { authService } from "../../services/authService";
import { apiResponse } from "../../services/api/client";
import type { SavedScan, SavedSize } from "../../types/studio";
import { dateLabel } from "../../utils/images";
import {
  Skeleton,
  EmptyState,
  ErrorNotice,
} from "../../components/feedback/Feedback";
import { useToast } from "../../components/ui/Toast";
import Modal from "../../components/ui/Modal";
import { ArrowRight, Ruler, UserRound } from "../../icons";
import AccountPrivacy from "./AccountPrivacy";
function PrivateThumbnail({ url }: { url: string | null }) {
  const [src, setSrc] = useState<string>();
  useEffect(() => {
    if (!url) return;
    let stopped = false;
    let objectUrl: string;
    apiResponse(url)
      .then((r) => r.blob())
      .then((blob) => {
        objectUrl = URL.createObjectURL(blob);
        if (!stopped) setSrc(objectUrl);
        else URL.revokeObjectURL(objectUrl);
      })
      .catch(() => {});
    return () => {
      stopped = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url]);
  return src ? (
    <img src={src} alt="Private saved scan thumbnail" />
  ) : (
    <div className="scan-thumbnail-fallback">
      <UserRound size={36} />
    </div>
  );
}
function AccountSettings() {
  const auth = useAuth();
  const toast = useToast();
  const [error, setError] = useState("");
  const schema = z.object({
    unit: z.enum(["cm", "in"]),
    name: z.string().trim().min(2).max(80),
    height: z
      .string()
      .refine(
        (v) => v === "" || (Number(v) >= 80 && Number(v) <= 250),
        "Enter a height between 80 and 250 cm.",
      ),
  });
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      unit: auth.user!.measurement_unit ?? "cm",
      name: auth.user!.name,
      height: auth.user!.height_cm ? String(auth.user!.height_cm) : "",
    },
  });
  return (
    <form
      className="card settings-card stack"
      onSubmit={handleSubmit(async (value) => {
        setError("");
        try {
          auth.update(
            await authService.update(
              value.name,
              value.height ? Number(value.height) : null,
              value.unit,
            ),
          );
          toast("Profile updated.");
        } catch (e) {
          setError((e as Error).message);
        }
      })}
    >
      <span className="eyebrow">THE BASICS</span>
      <label className="field">
        Preferred measurement units
        <select {...register("unit")}>
          <option value="cm">Centimetres</option>
          <option value="in">Inches</option>
        </select>
      </label>
      <h2>Account details.</h2>
      <label className="field">
        Your name
        <input {...register("name")} autoComplete="name" />
        {errors.name && (
          <small className="field-error">{errors.name.message}</small>
        )}
      </label>
      <label className="field">
        Email address
        <input value={auth.user!.email} readOnly type="email" />
        <small>Your sign-in email.</small>
      </label>
      <label className="field">
        Default height (cm)
        <input
          {...register("height")}
          type="number"
          step=".1"
          min="80"
          max="250"
        />
        {errors.height && (
          <small className="field-error">{errors.height.message}</small>
        )}
      </label>
      {error && <ErrorNotice message={error} />}
      <button className="button" disabled={isSubmitting}>
        {isSubmitting ? "Saving…" : "Save changes"}
      </button>
      <p className="fine-print">
        Passwords are never stored in your browser. Use “Forgot password” on the
        sign-in screen to request a secure reset.
      </p>
    </form>
  );
}
export default function ProfilePage() {
  const auth = useAuth();
  const active = useMeasurement();
  const navigate = useNavigate();
  const toast = useToast();
  const [tab, setTab] = useState<"scans" | "closet" | "settings">("scans");
  const [scans, setScans] = useState<SavedScan[]>([]);
  const [sizes, setSizes] = useState<SavedSize[]>([]);
  const [offset, setOffset] = useState(0);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<SavedScan>();
  const [deleteError, setDeleteError] = useState("");
  const [busy, setBusy] = useState(false);
  async function load() {
    setLoading(true);
    setError("");
    try {
      const [history, saved] = await Promise.all([
        measurementService.history(offset),
        sizingService.saved(),
      ]);
      setScans(history.items);
      setTotal(history.total);
      setSizes(saved);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [offset, auth.user?.id]);
  return (
    <>
      <div className="page-heading">
        <div>
          <span className="eyebrow">YOUR PERSONAL FIT PROFILE</span>
          <h1>
            Welcome back,
            <br className="mobile-only" />{" "}
            <em>{auth.user?.name.split(" ")[0]}.</em>
          </h1>
          <p>Your measurements, your favourite brands, your next great fit.</p>
        </div>
        <button
          className="button secondary"
          onClick={() => navigate("/measure")}
        >
          <Ruler size={16} />
          New measurement
        </button>
      </div>
      <div className="profile-summary">
        <div>
          <span className="profile-avatar">
            {auth.user?.name.charAt(0).toUpperCase()}
          </span>
          <div>
            <strong>{auth.user?.name}</strong>
            <span>{auth.user?.email}</span>
          </div>
        </div>
        <div>
          <span>DEFAULT HEIGHT</span>
          <strong>
            {auth.user?.height_cm ?? "—"} <small>cm</small>
          </strong>
        </div>
        <div>
          <span>SAVED SCANS</span>
          <strong>{total}</strong>
        </div>
        <div>
          <span>BRAND SIZES</span>
          <strong>{sizes.length}</strong>
        </div>
      </div>
      <div className="profile-tabs" role="tablist" aria-label="Your profile">
        {(["scans", "closet", "settings"] as const).map((value) => (
          <button
            key={value}
            role="tab"
            aria-selected={tab === value}
            aria-controls={`panel-${value}`}
            id={`tab-${value}`}
            tabIndex={tab === value ? 0 : -1}
            onKeyDown={(event) => {
              const tabs = ["scans", "closet", "settings"] as const;
              const index = tabs.indexOf(value);
              const next =
                event.key === "ArrowRight"
                  ? (index + 1) % 3
                  : event.key === "ArrowLeft"
                    ? (index + 2) % 3
                    : event.key === "Home"
                      ? 0
                      : event.key === "End"
                        ? 2
                        : undefined;
              if (next === undefined) return;
              event.preventDefault();
              setTab(tabs[next]);
              document.getElementById(`tab-${tabs[next]}`)?.focus();
            }}
            onClick={() => setTab(value)}
          >
            {value === "scans"
              ? "Measurement history"
              : value === "closet"
                ? "My Closet"
                : "Account settings"}
          </button>
        ))}
      </div>
      {error && <ErrorNotice message={error} retry={() => void load()} />}
      <section
        id={`panel-${tab}`}
        role="tabpanel"
        aria-labelledby={`tab-${tab}`}
      >
        {tab === "settings" ? (
          <>
            <AccountSettings />
            <AccountPrivacy />
          </>
        ) : loading ? (
          <Skeleton label="Opening your private profile…" />
        ) : tab === "scans" ? (
          <>
            {scans.length ? (
              <div className="history-grid">
                {scans.map((scan) => (
                  <article className="scan-history-card" key={scan.id}>
                    <PrivateThumbnail url={scan.thumbnail_url} />
                    <div>
                      <span className="eyebrow">
                        {dateLabel(scan.created_at)}
                      </span>
                      <h3>{scan.label}</h3>
                      <span className="badge">
                        {scan.source.replaceAll("-", " ")}
                      </span>
                      <div className="history-metrics">
                        <span>
                          Chest
                          <strong>
                            {scan.measurements.chest_circumference.toFixed(1)}{" "}
                            cm
                          </strong>
                        </span>
                        <span>
                          Waist
                          <strong>
                            {scan.measurements.waist_circumference.toFixed(1)}{" "}
                            cm
                          </strong>
                        </span>
                      </div>
                      <div className="row-between">
                        <button
                          className="text-button"
                          onClick={() => {
                            active.setFile(undefined);
                            active.setHeight(scan.height_cm);
                            active.setMeasurements(scan.measurements);
                            active.setEdited(scan.source !== "photo-estimate");
                            navigate("/sizing");
                          }}
                        >
                          Use measurements <ArrowRight size={14} />
                        </button>
                        <button
                          className="text-button danger-text"
                          onClick={() => {
                            setDeleteError("");
                            setDeleting(scan);
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            ) : (
              <div className="card">
                <EmptyState
                  title="Your fit story starts here."
                  action={() => navigate("/measure")}
                >
                  Save your first measurement scan and return to it whenever you
                  need a size recommendation.
                </EmptyState>
              </div>
            )}
            <div className="pagination">
              <button
                className="button secondary small"
                disabled={!offset}
                onClick={() => setOffset(Math.max(0, offset - 12))}
              >
                Previous
              </button>
              <span>
                {total
                  ? `${offset + 1}–${Math.min(offset + 12, total)} of ${total}`
                  : "No saved scans"}
              </span>
              <button
                className="button secondary small"
                disabled={offset + 12 >= total}
                onClick={() => setOffset(offset + 12)}
              >
                Next
              </button>
            </div>
          </>
        ) : sizes.length ? (
          <div className="closet-grid">
            {sizes.map((size) => (
              <article key={size.id} className="card closet-card">
                <span className="eyebrow">
                  {size.result.chart.category} · {size.result.chart.gender}
                </span>
                <h2>{size.result.chart.brand_name}</h2>
                <strong className="closet-size">
                  {size.result.recommended_size}
                </strong>
                <p>{size.result.fit_confidence.toFixed(1)}% chart similarity</p>
                <small>
                  Guide v{size.result.chart.version} ·{" "}
                  {dateLabel(size.updated_at)}
                </small>
                <button
                  className="text-button danger-text"
                  onClick={async () => {
                    try {
                      await sizingService.remove(size.id);
                      setSizes((items) =>
                        items.filter((s) => s.id !== size.id),
                      );
                      toast("Saved size removed.");
                    } catch (e) {
                      setError((e as Error).message);
                    }
                  }}
                >
                  Remove saved size
                </button>
              </article>
            ))}
          </div>
        ) : (
          <div className="card">
            <EmptyState
              title="Your brands, all in one place."
              action={() => navigate("/sizing")}
            >
              Save a size recommendation to keep a personal guide for your next
              shopping trip.
            </EmptyState>
          </div>
        )}
      </section>
      <Modal
        open={!!deleting}
        onClose={() => {
          if (!busy) setDeleting(undefined);
        }}
        title="Delete this saved scan?"
      >
        <p>
          This removes the measurements and private thumbnail from your profile.
        </p>
        {deleteError && <ErrorNotice message={deleteError} />}
        <div className="actions">
          <button
            className="button secondary"
            disabled={busy}
            onClick={() => setDeleting(undefined)}
          >
            Keep scan
          </button>
          <button
            className="button danger-button"
            disabled={busy}
            onClick={async () => {
              if (!deleting) return;
              setBusy(true);
              setDeleteError("");
              try {
                await measurementService.remove(deleting.id);
                setDeleting(undefined);
                await load();
                toast("Saved scan deleted.");
              } catch (e) {
                setDeleteError((e as Error).message);
              } finally {
                setBusy(false);
              }
            }}
          >
            {busy ? "Deleting…" : "Delete scan"}
          </button>
        </div>
      </Modal>
    </>
  );
}
