import type { ReactNode } from "react";

type AppShellProps = {
  readonly children: ReactNode;
};

const NAVIGATION_SECTIONS = [
  {
    title: "Cockpit",
    links: [{ href: "/", label: "Cockpit" }]
  },
  {
    title: "Arbeit",
    links: [
      { href: "/errors", label: "Störungen" },
      { href: "/tasks", label: "Aufgaben" },
      { href: "/handover", label: "Schichtübergabe" }
    ]
  },
  {
    title: "Wissen & Anlagen",
    links: [
      { href: "/machines", label: "Maschinen" },
      { href: "/inventory", label: "Inventar" },
      { href: "/documents", label: "Dokumente" }
    ]
  },
  {
    title: "Administration",
    links: [
      { href: "/admin/users", label: "Benutzer" },
      { href: "/admin/ai", label: "KI-Administration" }
    ]
  }
] as const;

/**
 * Render the future React shell with class names aligned to the current Jinja layout.
 */
export function AppShell({ children }: AppShellProps): ReactNode {
  return (
    <div className="app-shell-layout min-h-screen lg:grid lg:grid-cols-[var(--sidebar-width)_minmax(0,1fr)]">
      <aside className="app-sidebar hidden lg:flex lg:min-h-screen lg:flex-col">
        <a className="sidebar-brand" href="/">
          <span className="sidebar-brand-mark" aria-hidden="true">
            MA
          </span>
          <span>
            <span className="sidebar-brand-title">Maintenance</span>
            <span className="sidebar-brand-title">Assistant</span>
          </span>
        </a>
        <nav aria-label="Hauptnavigation" className="sidebar-nav">
          {NAVIGATION_SECTIONS.map((section) => (
            <section className="sidebar-nav-group" data-nav-group key={section.title}>
              <h2>{section.title}</h2>
              {section.links.map((link) => (
                <a className="nav-link" href={link.href} key={link.href}>
                  <span>{link.label}</span>
                </a>
              ))}
            </section>
          ))}
        </nav>
      </aside>
      <div className="app-content min-w-0">
        <main className="app-main" id="main-content" tabIndex={-1}>
          {children}
        </main>
      </div>
    </div>
  );
}
