import { StrictMode, useEffect, useState, type ReactNode } from "react";
import { createRoot } from "react-dom/client";

import { ShellChatWidget } from "./ShellChatWidget";
import { ShellIconSprite } from "./ShellIconSprite";
import { ShellSidebarNavigation } from "./ShellNavigation";
import { ShellTopbar } from "./ShellTopbar";
import { readSidebarCollapsedPreference, writeSidebarCollapsedPreference } from "./shellPreferences";

const SHELL_MOUNTED_EVENT = "maintenance-shell-react-mounted";

type ShellRootConfig = {
  readonly rootId: string;
  readonly render: () => ReactNode;
};

declare global {
  interface Window {
    maintenanceShellReactMounted?: boolean;
    maintenanceShellReactMountedRoots?: number;
  }
}

/**
 * Return the current route path for shell active states.
 */
function currentPath(): string {
  return window.location.pathname;
}

/**
 * Return the page title from the fallback header when available.
 */
function currentHeaderTitle(): string {
  const topbarRoot = document.getElementById("maintenance-shell-topbar-root");
  return topbarRoot?.dataset.shellTitle?.trim() || "Maintenance Assistant";
}

/**
 * Show one React root after a successful mount.
 */
function revealReactRoot(rootElement: HTMLElement): void {
  rootElement.hidden = false;
  rootElement.dataset.reactMounted = "true";
}

/**
 * Render the global React sidebar while preserving the existing page content.
 */
function ShellSidebarChrome(): ReactNode {
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(readSidebarCollapsedPreference);

  useEffect(() => {
    document.querySelector(".app-shell-layout")?.classList.toggle(
      "is-sidebar-collapsed",
      isSidebarCollapsed
    );
  }, [isSidebarCollapsed]);

  /**
   * Toggle and persist the global React sidebar state.
   */
  function toggleSidebarCollapsed(): void {
    setIsSidebarCollapsed((currentValue) => {
      const nextValue = !currentValue;
      writeSidebarCollapsedPreference(nextValue);
      return nextValue;
    });
  }

  return (
    <ShellSidebarNavigation
      collapsed={isSidebarCollapsed}
      currentPath={currentPath()}
      onToggleCollapsed={toggleSidebarCollapsed}
    />
  );
}

const SHELL_ROOTS: readonly ShellRootConfig[] = [
  {
    rootId: "maintenance-shell-sidebar-root",
    render: () => <ShellSidebarChrome />
  },
  {
    rootId: "maintenance-shell-topbar-root",
    render: () => <ShellTopbar currentPath={currentPath()} title={currentHeaderTitle()} />
  },
  {
    rootId: "maintenance-shell-chat-root",
    render: () => <ShellChatWidget />
  }
] as const;

/**
 * Mount one global shell root if its placeholder exists.
 */
function mountShellRoot(config: ShellRootConfig): boolean {
  const rootElement = document.getElementById(config.rootId);
  if (!rootElement) return false;

  createRoot(rootElement).render(
    <StrictMode>
      {config.render()}
    </StrictMode>
  );
  revealReactRoot(rootElement);
  return true;
}

/**
 * Mount the shared SVG icon sprite for React shell navigation.
 */
function mountShellIconSprite(): boolean {
  const rootElement = document.getElementById("maintenance-shell-icons-root");
  if (!rootElement) return false;

  createRoot(rootElement).render(
    <StrictMode>
      <ShellIconSprite />
    </StrictMode>
  );
  rootElement.dataset.reactMounted = "true";
  return true;
}

/**
 * Mount all global React shell chrome roots.
 */
function bootstrapShellChrome(): void {
  mountShellIconSprite();
  const mountedCount = SHELL_ROOTS.filter(mountShellRoot).length;
  if (mountedCount > 0) {
    window.maintenanceShellReactMounted = true;
    window.maintenanceShellReactMountedRoots = mountedCount;
    window.dispatchEvent(new CustomEvent(SHELL_MOUNTED_EVENT, { detail: { mountedCount } }));
  }
}

bootstrapShellChrome();
