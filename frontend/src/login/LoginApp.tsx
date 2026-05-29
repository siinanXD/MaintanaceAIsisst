import { useEffect, useState, type ReactNode } from "react";

import { markIslandMounted } from "../app/islandMount";
import { readStoredSession } from "../auth/session";
import { LoginForm } from "./LoginForm";
import type { LoginData } from "./loginTypes";

const LOGIN_ISLAND = {
  mountedFlag: "maintenanceLoginReactMounted",
  mountEvent: "maintenance-login-react-mounted"
};

/**
 * Render the logged-in panel matching the current Jinja markup.
 */
function LoggedInPanel(): ReactNode {
  return (
    <article className="card app-card lg:col-span-8" data-logged-in-panel>
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Du bist eingeloggt</h2>
            <p className="panel-meta">Die Sitzung ist aktiv. Oben rechts kannst du dich wieder abmelden.</p>
          </div>
          <span className="badge badge-success badge-outline">aktiv</span>
        </div>
        <div className="toolbar">
          <a className="btn btn-primary" href="/">Zum Cockpit</a>
          <button className="btn btn-ghost" type="button" data-logout-button>Abmelden</button>
        </div>
      </div>
    </article>
  );
}

/**
 * Render the static role overview matching the current Jinja login page.
 */
function RoleOverview(): ReactNode {
  return (
    <aside className="card app-card lg:col-span-4">
      <div className="card-body">
        <div className="panel-header">
          <div>
            <h2 className="panel-title">Rollen</h2>
            <p className="panel-meta">Zugriff nach Bereich</p>
          </div>
        </div>
        <p className="stat-label">master_admin, it, verwaltung, instandhaltung, produktion</p>
      </div>
    </aside>
  );
}

/**
 * Render the React login island without changing the existing visual layout.
 */
export function LoginApp(): ReactNode {
  const [session, setSession] = useState(() => readStoredSession());
  const loggedIn = Boolean(session.token && session.user);

  useEffect(() => {
    markIslandMounted(LOGIN_ISLAND);
  }, []);

  useEffect(() => {
    /**
     * Sync the island when the existing auth runtime changes localStorage.
     */
    function handleAuthChange(): void {
      markIslandMounted(LOGIN_ISLAND);
      setSession(readStoredSession());
    }

    window.addEventListener("maintenance-auth-changed", handleAuthChange);
    return () => window.removeEventListener("maintenance-auth-changed", handleAuthChange);
  }, []);

  /**
   * Mark the React island as authenticated immediately after a successful login.
   */
  function handleLogin(data: LoginData): void {
    setSession({
      token: data.access_token,
      user: data.user,
      error: null
    });
  }

  return (
    <>
      <section className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px] lg:items-start">
        <div className="page-hero mb-0">
          <div>
            <p className="page-kicker">Zugang</p>
            <h1 className="page-title">Einloggen</h1>
            <p className="page-description">
              Melde dich an, um Wartungsaufgaben, Fehlerwissen und KI-Funktionen rollenbasiert zu nutzen.
            </p>
          </div>
        </div>
        {loggedIn ? null : <LoginForm onLogin={handleLogin} />}
      </section>

      <section className="dashboard-grid mt-6">
        <RoleOverview />
        {loggedIn ? <LoggedInPanel /> : null}
      </section>
    </>
  );
}
