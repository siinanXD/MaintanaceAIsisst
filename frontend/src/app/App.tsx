import type { ReactNode } from "react";

import { readStoredSession } from "../auth/session";
import { AppShell } from "../layout/AppShell";

/**
 * Render a minimal smoke-test React app that is not mounted by existing Jinja pages.
 */
export function App(): ReactNode {
  const session = readStoredSession();
  const sessionLabel = session.user?.name ?? session.user?.username ?? "Nicht angemeldet";

  return (
    <AppShell>
      <section className="page-hero">
        <div>
          <p className="eyebrow">React Foundation</p>
          <h1>Maintenance Assistant</h1>
          <p>
            Dieses isolierte React-Fundament ist baubar, aber noch nicht in die bestehenden Seiten
            eingebunden.
          </p>
        </div>
      </section>
      <section className="panel-grid">
        <article className="info-panel">
          <h2>Session</h2>
          <p>{sessionLabel}</p>
          {session.error ? <p className="text-error">{session.error}</p> : null}
        </article>
      </section>
    </AppShell>
  );
}
