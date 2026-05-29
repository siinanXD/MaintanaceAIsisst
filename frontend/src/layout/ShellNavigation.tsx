import { useEffect, useState, type ReactNode } from "react";

import { apiRequest } from "../api/client";
import { canViewStoredDashboard } from "../auth/permissions";
import type { MaintenanceUser } from "../auth/session";
import { useAuthSession } from "../auth/useAuthSession";
import { ShellGlobalSearch } from "./ShellGlobalSearch";

type ShellNavigationLink = {
  readonly dashboardKey: string;
  readonly featureKey?: string;
  readonly href: string;
  readonly iconId?: string;
  readonly label: string;
  readonly permissionKey?: string;
  readonly routePrefix?: string;
  readonly variant?: "admin" | "default";
};

type ShellNavigationSection = {
  readonly defaultOpen?: boolean;
  readonly links: readonly ShellNavigationLink[];
  readonly title: string;
};

type ShellNavigationProps = {
  readonly collapsed?: boolean;
  readonly currentPath: string;
  readonly onToggleCollapsed?: () => void;
};

type ShellNavigationCounts = {
  readonly errors: number;
  readonly tasks: number;
};

const EMPTY_NAVIGATION_COUNTS: ShellNavigationCounts = {
  errors: 0,
  tasks: 0
};

const SHELL_NAVIGATION_SECTIONS: readonly ShellNavigationSection[] = [
  {
    defaultOpen: true,
    title: "Cockpit",
    links: [{ dashboardKey: "dashboard", href: "/", iconId: "icon-dashboard", label: "Cockpit" }]
  },
  {
    defaultOpen: true,
    title: "Arbeit",
    links: [
      { dashboardKey: "errors", href: "/errors", iconId: "icon-alert", label: "Störungen" },
      { dashboardKey: "tasks", href: "/tasks", iconId: "icon-tasks", label: "Aufgaben" },
      {
        dashboardKey: "shiftplans",
        featureKey: "handover",
        href: "/handover",
        iconId: "icon-handover",
        label: "Schichtübergabe",
        permissionKey: "shiftplans"
      }
    ]
  },
  {
    title: "Wissen & Anlagen",
    links: [
      {
        dashboardKey: "machines",
        href: "/machines",
        iconId: "icon-machine",
        label: "Maschinen",
        routePrefix: "/machines"
      },
      { dashboardKey: "inventory", href: "/inventory", iconId: "icon-inventory", label: "Inventar" },
      { dashboardKey: "documents", href: "/documents", iconId: "icon-document", label: "Dokumente" }
    ]
  },
  {
    title: "Planung & Personal",
    links: [
      { dashboardKey: "shiftplans", href: "/shiftplans", iconId: "icon-calendar", label: "Schichtpläne" },
      {
        dashboardKey: "employees",
        featureKey: "vacations",
        href: "/vacations",
        iconId: "icon-vacation",
        label: "Urlaube",
        permissionKey: "employees"
      },
      { dashboardKey: "employees", href: "/employees", iconId: "icon-users", label: "Mitarbeiter" }
    ]
  },
  {
    title: "Administration",
    links: [
      {
        dashboardKey: "admin_users",
        href: "/admin/users",
        iconId: "icon-admin",
        label: "Benutzer",
        variant: "admin"
      },
      {
        dashboardKey: "admin_users",
        featureKey: "admin_ai",
        href: "/admin/ai",
        iconId: "icon-ai",
        label: "KI-Administration",
        permissionKey: "admin_ai",
        routePrefix: "/admin/ai",
        variant: "admin"
      }
    ]
  }
] as const;

/**
 * Return whether a navigation link represents the current path.
 */
function isActiveNavigationLink(link: ShellNavigationLink, currentPath: string): boolean {
  if (link.routePrefix) {
    return currentPath === link.href || currentPath.startsWith(link.routePrefix + "/");
  }
  return currentPath === link.href;
}

/**
 * Return whether the current session may see a shell navigation link.
 */
function canViewNavigationLink(link: ShellNavigationLink, user: MaintenanceUser | null): boolean {
  return Boolean(user) && canViewStoredDashboard(user, link.permissionKey ?? link.dashboardKey);
}

/**
 * Return whether the current session may see any link in a navigation section.
 */
function canViewNavigationSection(section: ShellNavigationSection, user: MaintenanceUser | null): boolean {
  return section.links.some((link) => canViewNavigationLink(link, user));
}

/**
 * Return true when a value is a plain API payload object.
 */
function isPayload(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * Return a numeric total from paginated API responses or list payloads.
 */
function totalFromPayload(payload: unknown): number {
  if (isPayload(payload)) {
    const pagination = payload.pagination;
    if (isPayload(pagination) && Number.isFinite(Number(pagination.total))) {
      return Number(pagination.total);
    }

    const data = payload.data;
    if (isPayload(data)) {
      const dataPagination = data.pagination;
      if (isPayload(dataPagination) && Number.isFinite(Number(dataPagination.total))) {
        return Number(dataPagination.total);
      }
    }

    if (Array.isArray(data)) {
      return data.length;
    }
  }

  return Array.isArray(payload) ? payload.length : 0;
}

/**
 * Load React-owned sidebar counters for task and active incident navigation badges.
 */
function useShellNavigationCounts(user: MaintenanceUser | null): ShellNavigationCounts {
  const [counts, setCounts] = useState<ShellNavigationCounts>(EMPTY_NAVIGATION_COUNTS);

  useEffect(() => {
    const controller = new AbortController();

    /**
     * Fetch visible shell counters from the existing list APIs.
     */
    async function loadCounts(): Promise<void> {
      if (!user) {
        setCounts(EMPTY_NAVIGATION_COUNTS);
        return;
      }

      const canViewTasks = canViewStoredDashboard(user, "tasks");
      const canViewErrors = canViewStoredDashboard(user, "errors");

      const [tasksResult, errorsResult] = await Promise.allSettled([
        canViewTasks
          ? apiRequest<unknown>("/api/v1/tasks?limit=1", { signal: controller.signal })
          : Promise.resolve([]),
        canViewErrors
          ? apiRequest<unknown>("/api/v1/errors?limit=1&active=1", { signal: controller.signal })
          : Promise.resolve([])
      ]);

      if (controller.signal.aborted) return;

      if (tasksResult.status === "rejected") {
        console.warn("Aufgabenzähler konnte nicht geladen werden.", tasksResult.reason);
      }
      if (errorsResult.status === "rejected") {
        console.warn("Störungszähler konnte nicht geladen werden.", errorsResult.reason);
      }

      setCounts({
        errors: errorsResult.status === "fulfilled" ? totalFromPayload(errorsResult.value) : 0,
        tasks: tasksResult.status === "fulfilled" ? totalFromPayload(tasksResult.value) : 0
      });
    }

    void loadCounts();

    return () => controller.abort();
  }, [user]);

  return counts;
}

/**
 * Build the shared navigation attributes used by permissions and active-state code.
 */
function navigationDataAttributes(link: ShellNavigationLink): Record<string, string> {
  return {
    "data-dashboard-nav": link.dashboardKey,
    ...(link.featureKey ? { "data-feature-key": link.featureKey } : {})
  };
}

/**
 * Render one sidebar navigation link with the legacy-compatible hooks intact.
 */
function SidebarNavigationLink({
  counts,
  currentPath,
  link,
  user
}: {
  readonly counts: ShellNavigationCounts;
  readonly currentPath: string;
  readonly link: ShellNavigationLink;
  readonly user: MaintenanceUser | null;
}): ReactNode {
  const isActive = isActiveNavigationLink(link, currentPath);
  const className = [
    "nav-link",
    link.variant === "admin" ? "is-admin-link" : "",
    isActive ? "is-active" : ""
  ].filter(Boolean).join(" ");

  return (
    <a
      {...navigationDataAttributes(link)}
      aria-current={isActive ? "page" : undefined}
      className={className}
      hidden={!canViewNavigationLink(link, user)}
      href={link.href}
    >
      {link.iconId ? (
        <svg className="nav-icon" aria-hidden="true">
          <use href={`#${link.iconId}`} />
        </svg>
      ) : null}
      <span>{link.label}</span>
      {link.dashboardKey === "errors" ? (
        <span className="nav-count is-alert" data-dashboard-machine-issue-count>
          {counts.errors}
        </span>
      ) : null}
      {link.dashboardKey === "tasks" ? (
        <span className="nav-count" data-dashboard-task-count>
          {counts.tasks}
        </span>
      ) : null}
    </a>
  );
}

/**
 * Render one mobile navigation link with the same permission hooks as the template.
 */
function MobileNavigationLink({
  currentPath,
  link,
  user
}: {
  readonly currentPath: string;
  readonly link: ShellNavigationLink;
  readonly user: MaintenanceUser | null;
}): ReactNode {
  const isActive = isActiveNavigationLink(link, currentPath);
  const className = [
    "top-nav-link",
    link.variant === "admin" ? "is-admin-link" : "",
    isActive ? "is-active" : ""
  ].filter(Boolean).join(" ");

  return (
    <a
      {...navigationDataAttributes(link)}
      aria-current={isActive ? "page" : undefined}
      className={className}
      hidden={!canViewNavigationLink(link, user)}
      href={link.href}
    >
      {link.label}
    </a>
  );
}

/**
 * Render the desktop sidebar navigation prepared for the final React shell.
 */
export function ShellSidebarNavigation({
  collapsed = false,
  currentPath,
  onToggleCollapsed
}: ShellNavigationProps): ReactNode {
  const { user } = useAuthSession();
  const counts = useShellNavigationCounts(user);
  const toggleLabel = collapsed ? "Menü erweitern" : "Menü minimieren";

  return (
    <aside className="app-sidebar hidden lg:flex lg:min-h-screen lg:flex-col">
      <a className="sidebar-brand" href="/">
        <span className="sidebar-brand-mark" aria-hidden="true">
          <svg viewBox="0 0 24 24" role="img">
            <path d="M19.4 13.5c.1-.5.1-1 .1-1.5s0-1-.1-1.5l2-1.5-2-3.4-2.4 1a8.2 8.2 0 0 0-2.6-1.5L14 2.5h-4l-.4 2.6A8.2 8.2 0 0 0 7 6.6l-2.4-1-2 3.4 2 1.5c-.1.5-.1 1-.1 1.5s0 1 .1 1.5l-2 1.5 2 3.4 2.4-1a8.2 8.2 0 0 0 2.6 1.5l.4 2.6h4l.4-2.6a8.2 8.2 0 0 0 2.6-1.5l2.4 1 2-3.4-2-1.5ZM12 15.5A3.5 3.5 0 1 1 12 8a3.5 3.5 0 0 1 0 7.5Z" />
          </svg>
        </span>
        <span>
          <span className="sidebar-brand-title">Maintenance</span>
          <span className="sidebar-brand-title">Assistant</span>
        </span>
      </a>
      <nav aria-label="Hauptnavigation" className="sidebar-nav">
        {SHELL_NAVIGATION_SECTIONS.map((section) => (
          <section
            className="sidebar-nav-group"
            data-nav-group
            data-nav-open={section.defaultOpen ? "true" : undefined}
            hidden={!canViewNavigationSection(section, user)}
            key={section.title}
          >
            <h2>{section.title}</h2>
            {section.links.map((link) => (
              <SidebarNavigationLink
                counts={counts}
                currentPath={currentPath}
                key={link.href}
                link={link}
                user={user}
              />
            ))}
          </section>
        ))}
      </nav>
      <button
        className="sidebar-minimize"
        type="button"
        aria-label={toggleLabel}
        aria-pressed={collapsed}
        data-sidebar-toggle
        onClick={onToggleCollapsed}
      >
        <span className="sidebar-minimize-icon" aria-hidden="true" />
        <span data-sidebar-toggle-label>{toggleLabel}</span>
      </button>
    </aside>
  );
}

/**
 * Render the mobile navigation prepared for the final React shell.
 */
export function ShellMobileNavigation({ currentPath }: ShellNavigationProps): ReactNode {
  const { user } = useAuthSession();

  return (
    <details className="mobile-nav" data-nav-root>
      <summary>Menü</summary>
      <div className="mobile-nav-panel">
        <ShellGlobalSearch inputId="global-search-mobile-react" isMobile />
        {SHELL_NAVIGATION_SECTIONS.map((section) => (
          <section
            className="mobile-nav-group"
            data-nav-group
            hidden={!canViewNavigationSection(section, user)}
            key={section.title}
          >
            <h2>{section.title}</h2>
            {section.links.map((link) => (
              <MobileNavigationLink currentPath={currentPath} key={link.href} link={link} user={user} />
            ))}
          </section>
        ))}
      </div>
    </details>
  );
}
