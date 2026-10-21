import { Component, type ReactNode } from "react";
import { ArrowRight, RotateCw } from "../../icons";
export function ErrorNotice({
  message,
  retry,
}: {
  message: string;
  retry?: () => void;
}) {
  return (
    <div className="notice error" role="alert">
      <span>{message}</span>
      {retry && (
        <button className="text-button" onClick={retry}>
          <RotateCw size={15} />
          Retry
        </button>
      )}
    </div>
  );
}
export function Skeleton({
  label = "Loading your studio…",
}: {
  label?: string;
}) {
  return (
    <div className="skeleton-wrap" role="status">
      <span>{label}</span>
      <div className="skeleton" />
      <div className="skeleton" />
    </div>
  );
}
export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: () => void;
}) {
  return (
    <div className="empty-state">
      <div className="empty-symbol">＋</div>
      <h3>{title}</h3>
      <p>{children}</p>
      {action && (
        <button className="button secondary" onClick={action}>
          Get started <ArrowRight size={16} />
        </button>
      )}
    </div>
  );
}
export class ErrorBoundary extends Component<
  { children: ReactNode },
  { failed: boolean }
> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? (
      <main className="page">
        <h1>The studio needs a refresh.</h1>
        <p>Your saved account results are still available.</p>
        <button className="button" onClick={() => window.location.reload()}>
          Reload studio
        </button>
      </main>
    ) : (
      this.props.children
    );
  }
}
