import {
  createContext,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { Navigate, useLocation } from "react-router-dom";
import { refreshSession, setAccessToken } from "../../services/api/client";
import { authService } from "../../services/authService";
import type { Session, User } from "../../types/studio";
import { Skeleton, ErrorNotice } from "../../components/feedback/Feedback";
type Auth = {
  user: User | null;
  loading: boolean;
  error: string;
  accept: (session: Session) => void;
  update: (user: User) => void;
  logout: () => Promise<void>;
  restore: () => Promise<void>;
};
const Context = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  async function restore() {
    setLoading(true);
    setError("");
    try {
      const session = await refreshSession();
      setUser(session?.user ?? null);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void restore();
    const expired = () => {
      setUser(null);
      setAccessToken(null);
      window.dispatchEvent(new Event("formfit:clear-private"));
    };
    window.addEventListener("formfit:session-expired", expired);
    return () => window.removeEventListener("formfit:session-expired", expired);
  }, []);
  const accept = (session: Session) => {
    setAccessToken(session.access_token);
    setUser(session.user);
    setError("");
  };
  useEffect(() => {
    if (!user) return;
    // Refresh before the short-lived image-access cookie expires, using the
    // same cross-tab rotation lock as API requests.
    const timer = window.setInterval(
      () => {
        void refreshSession()
          .then((s) => {
            if (s) accept(s);
          })
          .catch(() => {});
      },
      10 * 60 * 1000,
    );
    return () => window.clearInterval(timer);
  }, [user?.id]);
  async function logout() {
    await authService.logout();
    setAccessToken(null);
    setUser(null);
    window.dispatchEvent(new Event("formfit:clear-private"));
  }
  return (
    <Context.Provider
      value={{ user, loading, error, accept, logout, restore, update: setUser }}
    >
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const auth = useContext(Context);
  if (!auth) throw new Error("AuthProvider is missing");
  return auth;
}
export function ProtectedLayout({ children }: { children: ReactNode }) {
  const auth = useAuth();
  const location = useLocation();
  if (auth.loading) return <Skeleton label="Restoring your private session…" />;
  if (auth.error)
    return (
      <ErrorNotice message={auth.error} retry={() => void auth.restore()} />
    );
  if (!auth.user)
    return (
      <Navigate
        to={`/login?returnTo=${encodeURIComponent(location.pathname + location.search)}`}
        replace
      />
    );
  return <>{children}</>;
}
