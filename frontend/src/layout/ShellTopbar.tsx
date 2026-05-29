import { type MouseEvent, type ReactNode } from "react";

import { legacyAuthRuntime, showLegacyToast } from "../app/runtimeBridge";
import { useAuthContext } from "../auth/AuthProvider";
import { currentPathWithSearch, displayStoredUserName, loginUrlForPath } from "../auth/session";
import { ShellGlobalSearch } from "./ShellGlobalSearch";
import { ShellMobileNavigation } from "./ShellNavigation";
import { useHighContrastPreference, useNotificationBadge, useShellShiftState } from "./ShellTopbarState";

type ShellTopbarProps = {
  readonly currentPath: string;
  readonly title: string;
};

/**
 * Render the topbar and global search hooks for the future React shell.
 */
export function ShellTopbar({ currentPath, title }: ShellTopbarProps): ReactNode {
  const loginClassName = currentPath === "/login" ? "btn btn-primary btn-sm btn-active" : "btn btn-primary btn-sm";
  const session = useAuthContext();
  const shiftState = useShellShiftState();
  const [highContrastEnabled, toggleHighContrast] = useHighContrastPreference();
  const isLoggedIn = Boolean(session.token);
  const [unreadNotifications, markNotificationsRead] = useNotificationBadge(isLoggedIn);
  const sessionName = displayStoredUserName(session.user);
  const loginHref = currentPath === "/login" ? "/login" : loginUrlForPath(currentPathWithSearch());

  /**
   * Delegate logout to the existing auth runtime while preserving a fallback path.
   */
  function handleLogout(event: MouseEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();

    const authRuntime = legacyAuthRuntime();
    if (authRuntime?.clearSession) {
      authRuntime.clearSession({ redirect: true });
      return;
    }
    window.localStorage.removeItem("maintenance_access_token");
    window.localStorage.removeItem("maintenance_user");
    window.dispatchEvent(new Event("maintenance-auth-changed"));
    if (window.location.pathname !== "/login") {
      window.location.href = loginUrlForPath(currentPathWithSearch());
    }
  }

  /**
   * Toggle high contrast through React without triggering the legacy delegated handler twice.
   */
  function handleContrastToggle(event: MouseEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();
    toggleHighContrast();
  }

  /**
   * Mark topbar notifications read and keep the legacy briefing navigation behavior.
   */
  function handleNotificationClick(event: MouseEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();

    if (isLoggedIn) {
      void markNotificationsRead();
    }

    const briefing = document.querySelector("#daily-briefing");
    if (briefing) {
      briefing.scrollIntoView({ behavior: "smooth", block: "start" });
      showLegacyToast("Briefing und kritische Hinweise geöffnet.");
      return;
    }

    if (window.location.pathname !== "/") {
      window.location.href = "/";
    }
  }

  /**
   * Show the current worksite status from the React-owned topbar.
   */
  function handleWorksiteClick(event: MouseEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();
    showLegacyToast("Werk 1 ist aktiv. Weitere Werke sind noch nicht konfiguriert.");
  }

  /**
   * Navigate to shift planning from date and shift controls.
   */
  function handleShiftplansClick(event: MouseEvent<HTMLButtonElement>): void {
    event.preventDefault();
    event.stopPropagation();
    window.location.href = "/shiftplans";
  }

  return (
    <header className="app-header">
      <div className="mobile-header lg:hidden">
        <a className="mobile-brand" href="/">
          <span className="sidebar-brand-mark" aria-hidden="true">MA</span>
          <span>Maintenance</span>
        </a>
        <ShellMobileNavigation currentPath={currentPath} />
      </div>
      <div className="desktop-topbar">
        <h1>{title}</h1>
        <div className="topbar-actions">
          <ShellGlobalSearch inputId="global-search-desktop-react" />
          <button
            className="topbar-select"
            type="button"
            aria-label="Werk auswählen"
            title="Aktives Werk anzeigen"
            data-topbar-work
            onClick={handleWorksiteClick}
          >
            <span className="topbar-control-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M4 20V8.5l5-3v4l5-3v4l6-3.5V20H4Zm3-2h10v-7.4l-5 2.9v-4l-5 3V18Z" /></svg>
            </span>
            <span>Werk 1</span>
          </button>
          <button
            className="topbar-select"
            type="button"
            aria-label="Aktuelles Datum"
            title="Zum Schichtplan wechseln"
            data-topbar-date
            onClick={handleShiftplansClick}
          >
            <span className="topbar-control-icon" aria-hidden="true">
              <svg viewBox="0 0 24 24"><path d="M7 2h2v2h6V2h2v2h3v18H4V4h3V2Zm11 8H6v10h12V10ZM6 8h12V6H6v2Z" /></svg>
            </span>
            <span data-current-date title={shiftState.dateTitle}>{shiftState.dateValue}</span>
          </button>
          <button
            className={`topbar-select shift-select is-${shiftState.key}`}
            type="button"
            aria-label={`Aktuell laufende Schicht: ${shiftState.label}`}
            title={`Aktuell: ${shiftState.label} (${shiftState.time})`}
            data-current-shift
            onClick={handleShiftplansClick}
          >
            <span className="status-dot" aria-hidden="true" />
            <span>
              <strong data-current-shift-label>{shiftState.label}</strong>
              <small data-current-shift-time>{shiftState.time}</small>
            </span>
          </button>
          <button
            className="notification-button"
            type="button"
            aria-label="Benachrichtigungen"
            title="Briefing und kritische Hinweise öffnen"
            data-topbar-notifications
            onClick={handleNotificationClick}
          >
            <svg aria-hidden="true" viewBox="0 0 24 24"><path d="M12 22a2.3 2.3 0 0 0 2.2-1.6H9.8A2.3 2.3 0 0 0 12 22Zm7-5-1.7-2.2V10a5.4 5.4 0 0 0-4.1-5.3V3a1.2 1.2 0 1 0-2.4 0v1.7A5.4 5.4 0 0 0 6.7 10v4.8L5 17v1.2h14V17Z" /></svg>
            <span className="notification-badge" data-notification-badge hidden={unreadNotifications <= 0}>{unreadNotifications}</span>
          </button>
          <div className="user-menu" data-auth-session hidden={!isLoggedIn}>
            <span className="user-avatar" aria-hidden="true">TW</span>
            <span>
              <strong data-session-name>{sessionName}</strong>
              <small>Instandhaltungsleiter</small>
            </span>
            <button
              className="btn btn-ghost btn-sm"
              type="button"
              data-contrast-toggle
              aria-pressed={highContrastEnabled}
              onClick={handleContrastToggle}
            >
              {highContrastEnabled ? "Standard-Kontrast" : "Hoher Kontrast"}
            </button>
            <button className="btn btn-ghost btn-sm" type="button" data-logout-button onClick={handleLogout}>Abmelden</button>
          </div>
          <a data-auth-login-link className={loginClassName} href={loginHref} hidden={isLoggedIn}>Anmelden</a>
        </div>
      </div>
    </header>
  );
}
