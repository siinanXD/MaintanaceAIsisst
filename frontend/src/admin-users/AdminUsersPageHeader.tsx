import { type ReactNode } from "react";

/**
 * Render the page hero.
 */
export function AdminUsersPageHeader(): ReactNode {
  return (
    <section className="page-hero">
      <div>
        <p className="page-kicker">Admin</p>
        <h1 className="page-title">Nutzerverwaltung</h1>
        <p className="page-description">Nutzer anzeigen, sperren, entsperren, Passwort zurücksetzen und löschen.</p>
      </div>
    </section>
  );
}

