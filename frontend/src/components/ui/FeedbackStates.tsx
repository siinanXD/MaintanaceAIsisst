import type { ReactNode } from "react";

type LoadingStateProps = {
  readonly title?: string;
  readonly description?: string;
};

type ErrorStateProps = {
  readonly title?: string;
  readonly message: string;
  readonly children?: ReactNode;
};

/**
 * Render a compact loading state using existing application classes.
 */
export function LoadingState({
  title = "Wird geladen",
  description = "Die Daten werden vorbereitet."
}: LoadingStateProps): ReactNode {
  return (
    <section className="status-card" aria-live="polite" aria-busy="true">
      <span className="loading loading-spinner loading-sm" aria-hidden="true" />
      <div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
    </section>
  );
}

/**
 * Render a scoped error state without exposing stack traces in the UI.
 */
export function ErrorState({
  title = "Bereich konnte nicht geladen werden",
  message,
  children
}: ErrorStateProps): ReactNode {
  return (
    <section className="status-card is-warning" role="alert">
      <div>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {children}
    </section>
  );
}
