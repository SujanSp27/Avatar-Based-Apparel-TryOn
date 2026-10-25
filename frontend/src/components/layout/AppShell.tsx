import { useEffect, useRef, useState } from "react";
import {
  Link,
  NavLink,
  Outlet,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { ArrowRight, Layers3, Ruler, Shirt, UserRound } from "../../icons";
import { useAuth } from "../../features/auth/AuthProvider";
import { useToast } from "../ui/Toast";
import BrandLogo from "../ui/BrandLogo";
const nav = [
  {
    to: "/measure",
    label: "Body measurements",
    short: "Measure",
    icon: Ruler,
    step: "01",
  },
  {
    to: "/sizing",
    label: "Find my size",
    short: "Size",
    icon: Layers3,
    step: "02",
  },
  {
    to: "/tryon",
    label: "Virtual try-on",
    short: "Try on",
    icon: Shirt,
    step: "03",
  },
];
export default function AppShell() {
  const auth = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const toast = useToast();
  const main = useRef<HTMLElement>(null);
  const [logoutBusy, setLogoutBusy] = useState(false);
  useEffect(() => {
    window.scrollTo({ top: 0 });
    main.current?.focus({ preventScroll: true });
  }, [location.pathname]);
  const isAuth = ["/login", "/signup", "/reset-password"].includes(
    location.pathname,
  );
  return (
    <>
      <a className="skip-link" href="#main-content">
        Skip to content
      </a>
      <aside className="sidebar">
        <Link className="wordmark" to="/" aria-label="VastraView home">
          <BrandLogo />
        </Link>
        <div className="sidebar-section-label">YOUR FIT JOURNEY</div>
        <nav className="main-nav" aria-label="Main navigation">
          <NavLink to="/catalog">
            <Shirt size={19} />
            <span>Discover apparel</span>
          </NavLink>
          {nav.map(({ to, label, short, icon: Icon, step }) => (
            <NavLink to={to} key={to}>
              <Icon size={19} />
              <span className="nav-full">{label}</span>
              <span className="nav-short">{short}</span>
              <small>{step}</small>
            </NavLink>
          ))}
          <div className="nav-divider" />
          <NavLink to="/profile">
            <UserRound size={19} />
            <span className="nav-full">My profile & closet</span>
            <span className="nav-short">Profile</span>
          </NavLink>
        </nav>
        <div className="sidebar-bottom">
          <div className="studio-note">
            <span className="small-caps">LESS GUESSWORK.</span>
            <h3>More you.</h3>
            <p>A considered approach to your next great fit.</p>
            <span className="decorative-line" />
          </div>
          <Link to="/terms">Privacy & studio notes ↗</Link>
          <span className="version-label">
            VASTRAVIEW · PERSONAL FIT STUDIO
          </span>
        </div>
      </aside>
      <div className="app-body">
        <header className="topbar">
          <div className="breadcrumb">
            <span>THE STUDIO</span>
            <span>/</span>
            <strong>
              {nav.find((item) => item.to === location.pathname)?.label ??
                (location.pathname === "/profile"
                  ? "Your profile"
                  : location.pathname === "/catalog"
                    ? "Apparel catalog"
                    : "Welcome")}
            </strong>
          </div>
          <div className="topbar-actions">
            <span className="device-note">
              <span className="status-dot" />A personal fit experience
            </span>
            {auth.user ? (
              <>
                <Link className="account-chip" to="/profile">
                  <span>{auth.user.name.charAt(0)}</span>
                  <span>{auth.user.name.split(" ")[0]}</span>
                </Link>
                <button
                  className="text-button logout-button"
                  disabled={logoutBusy}
                  onClick={async () => {
                    setLogoutBusy(true);
                    try {
                      await auth.logout();
                      navigate("/measure");
                      toast("You’re signed out.");
                    } catch (e) {
                      toast((e as Error).message);
                    } finally {
                      setLogoutBusy(false);
                    }
                  }}
                >
                  {logoutBusy ? "Signing out…" : "Sign out"}
                </button>
              </>
            ) : (
              <Link
                className="button small secondary"
                to={`/login?returnTo=${encodeURIComponent(location.pathname)}`}
              >
                Sign in <ArrowRight size={14} />
              </Link>
            )}
          </div>
        </header>
        <main
          id="main-content"
          ref={main}
          tabIndex={-1}
          className={`page ${isAuth ? "page-auth" : ""}`}
        >
          <Outlet />
        </main>
        <footer className="footer">
          <span>
            <BrandLogo compact />
          </span>
          <span>Photo estimates · Thoughtful size advice</span>
          <Link to="/terms">Terms & privacy</Link>
        </footer>
      </div>
    </>
  );
}
