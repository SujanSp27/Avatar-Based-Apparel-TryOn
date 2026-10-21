import { lazy, Suspense } from "react";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, ProtectedLayout } from "./features/auth/AuthProvider";
import { MeasurementProvider } from "./features/measurement/MeasurementProvider";
import { ToastProvider } from "./components/ui/Toast";
import { ErrorBoundary, Skeleton } from "./components/feedback/Feedback";
import AppShell from "./components/layout/AppShell";
const MeasurementWorkspace = lazy(
  () => import("./features/measurement/MeasurementWorkspace"),
);
const SizeEngineView = lazy(() => import("./features/sizing/SizeEngineView"));
const TryOnStudio = lazy(() => import("./features/tryon/TryOnStudio"));
const ProfilePage = lazy(() => import("./features/profile/ProfilePage"));
const AuthPage = lazy(() =>
  import("./features/auth/AuthModal").then((module) => ({
    default: module.AuthPage,
  })),
);
const ResetPassword = lazy(() => import("./features/auth/ResetPassword"));
const Terms = lazy(() => import("./components/layout/Terms"));
export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <ToastProvider>
          <AuthProvider>
            <MeasurementProvider>
              <Suspense
                fallback={
                  <div className="page">
                    <Skeleton />
                  </div>
                }
              >
                <Routes>
                  <Route element={<AppShell />}>
                    <Route index element={<Navigate to="/measure" replace />} />
                    <Route path="measure" element={<MeasurementWorkspace />} />
                    <Route path="sizing" element={<SizeEngineView />} />
                    <Route path="tryon" element={<TryOnStudio />} />
                    <Route
                      path="profile"
                      element={
                        <ProtectedLayout>
                          <ProfilePage />
                        </ProtectedLayout>
                      }
                    />
                    <Route path="login" element={<AuthPage mode="login" />} />
                    <Route path="signup" element={<AuthPage mode="signup" />} />
                    <Route path="reset-password" element={<ResetPassword />} />
                    <Route path="terms" element={<Terms />} />
                    <Route
                      path="*"
                      element={
                        <div className="card narrow">
                          <h1>This page isn’t in the studio.</h1>
                          <a className="button" href="/measure">
                            Back to measurements
                          </a>
                        </div>
                      }
                    />
                  </Route>
                </Routes>
              </Suspense>
            </MeasurementProvider>
          </AuthProvider>
        </ToastProvider>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
