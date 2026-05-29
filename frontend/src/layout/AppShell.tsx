import { useState, type ReactNode } from "react";

import { ShellChatWidget } from "./ShellChatWidget";
import { ShellIconSprite } from "./ShellIconSprite";
import { ShellSidebarNavigation } from "./ShellNavigation";
import { ShellTopbar } from "./ShellTopbar";
import { readSidebarCollapsedPreference, writeSidebarCollapsedPreference } from "./shellPreferences";

type AppShellProps = {
  readonly children: ReactNode;
  readonly currentPath?: string;
  readonly title?: string;
};

/**
 * Resolve the current browser path without making server rendering mandatory.
 */
function currentBrowserPath(): string {
  return typeof window === "undefined" ? "/" : window.location.pathname;
}

/**
 * Render the future React shell with class names and hooks aligned to base.html.
 */
export function AppShell({
  children,
  currentPath = currentBrowserPath(),
  title = "Maintenance Assistant"
}: AppShellProps): ReactNode {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(readSidebarCollapsedPreference);
  const layoutClassName = [
    "app-shell-layout min-h-screen lg:grid lg:grid-cols-[var(--sidebar-width)_minmax(0,1fr)]",
    isSidebarCollapsed ? "is-sidebar-collapsed" : ""
  ].filter(Boolean).join(" ");

  /**
   * Toggle and persist the React shell sidebar state.
   */
  function toggleSidebarCollapsed(): void {
    setIsSidebarCollapsed((currentValue) => {
      const nextValue = !currentValue;
      writeSidebarCollapsedPreference(nextValue);
      return nextValue;
    });
  }

  return (
    <>
      <a className="skip-link" href="#main-content">Zum Hauptinhalt springen</a>
      <ShellIconSprite />
      <div className={layoutClassName}>
        <ShellSidebarNavigation
          collapsed={isSidebarCollapsed}
          currentPath={currentPath}
          onToggleCollapsed={toggleSidebarCollapsed}
        />
        <div className="app-content min-w-0">
          <ShellTopbar currentPath={currentPath} title={title} />
          <main className="app-main" id="main-content" tabIndex={-1}>
            <div className="sr-only" aria-live="polite" aria-atomic="true" data-global-live-region />
            {children}
          </main>
        </div>
      </div>
      <ShellChatWidget />
    </>
  );
}
