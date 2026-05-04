# agent.md — Maintenance Assistant: Projektkontext & Roadmap

Dieses Dokument beschreibt den aktuellen Stand der Codebasis, bekannte technische Schulden und priorisierte zukünftige Features. Es dient als Orientierung für neue Entwicklungssessions (Mensch oder KI-Agent).

---

## Projektüberblick

**Maintenance Assistant** ist eine modulare Flask-REST-API mit Jinja2-Frontend für Wartungs- und Produktionsteams in der Industrie. Die App verwaltet Tasks, Fehlerkataloge, Mitarbeiter, Maschinen, Lager, Schichtplanung, Schichtübergaben und Urlaubsanträge — mit optionaler OpenAI-Integration (lokaler Fallback immer vorhanden).

| Metrik | Wert |
|--------|------|
| Python-Dateien | 59 |
| Codezeilen (Python) | ~9.800 |
| Blueprints | 16 |
| Tests | 133 (pytest, in-memory SQLite) |
| Templates | 15 Jinja2-Seiten |
| Modelle | 15+ SQLAlchemy-Modelle in `app/models.py` |

---

## Architektur-Grundregeln

- **Routes** nehmen HTTP-Input an und delegieren sofort an Services
- **Services** in `app/services/` geben `(result, error_dict, http_status)` zurück
- **Responses** immer über `success_response()` / `error_response()` aus `app/responses.py`
- **Auth** via `@jwt_required()` + `@dashboard_permission_required()` + `@roles_required()`
- **Kein Type-Hint** im Produktionscode, kurze Docstrings, `snake_case`
- **KI-Calls** immer hinter `try/except` mit lokalem Fallback
- **Logger**: `logger = logging.getLogger(__name__)` pro Modul, `logger.exception()` für Fehler

---

## Bekannte technische Schulden (Priorität: hoch → niedrig)

### 🔴 Hoch

**1. `_run_lightweight_migrations()` in `app/__init__.py` ablösen**
- 130 Zeilen rohe `ALTER TABLE` Statements laufen bei jedem App-Start
- Flask-Migrate ist installiert aber nicht initialisiert (`flask db init` fehlt)
- Fix: `flask db init` → `flask db migrate` → `flask db upgrade` → Block entfernen
- Dateien: `app/__init__.py`, neue `migrations/` Ordnerstruktur

**2. `app/models.py` aufteilen**
- Alle 15+ Modelle in einer 658-Zeilen-Datei
- Risiko: bei weiteren Modellen schwer wartbar
- Fix: `app/models/` Package mit `__init__.py` Re-Export, je Domäne eine Datei
- Reihenfolge: `user.py`, `employee.py`, `task.py`, `error.py`, `machine.py`, `shift.py`, `vacation.py`

**3. `responses.py` Inkonsistenz**
- `success_payload()` legt Dict-Keys sowohl in `data` als auch auf Root-Ebene (`payload.update(data)`)
- Alle 9 betroffenen Routen-Dateien lesen Keys vom Root statt aus `data`
- Fix: alle Caller auf `response.data.key` umstellen, dann `update()`-Zeilen entfernen
- Dateien: `app/responses.py` + alle `*/routes.py` die dict an `success_response()` übergeben

### 🟡 Mittel

**4. `datetime.utcnow()` deprecation**
- 6+ Stellen im Code nutzen veraltetes `datetime.utcnow()`
- Fix: `datetime.now(timezone.utc)` — One-Liner-Änderungen
- Dateien: `app/vacations/routes.py`, `app/services/task_service.py`, `app/__init__.py`, `app/shiftplans/routes.py`

**5. `Query.get()` legacy SQLAlchemy**
- Mehrere Stellen nutzen veraltetes `Model.query.get(id)` statt `db.session.get(Model, id)`
- Dateien: `tests/test_permissions.py` und diverse routes

**6. SQLite → PostgreSQL Readiness**
- App läuft ausschließlich mit SQLite; `DATABASE_URL` ist konfigurierbar aber ungetestet mit Postgres
- `_run_lightweight_migrations()` nutzt SQLite-spezifische `exec_driver_sql` Syntax
- Fix: Alembic-Migrationen (siehe #1) + einmal gegen PostgreSQL testen

### 🟢 Niedrig

**7. `seed.py` und `seed_demo.py` zusammenführen**
- Zwei separate Seed-Skripte mit überlappender Logik
- Fix: ein `seed.py --demo` Flag

**8. JS-Module statt inline `<script>`**
- Alle 15 Templates haben ihren JS-Code inline als IIFE
- Fix: `app/static/js/` Ordner mit einem Modul pro Seite, Bundling via esbuild oder Vite

---

## Feature-Roadmap

### Priorität 1 — Quick Wins (1–3 Tage)

**Email-Benachrichtigungen**
- Task zugewiesen → Email an Empfänger
- Urlaubsantrag gestellt → Email an Admin
- Urlaubsantrag genehmigt/abgelehnt → Email an Mitarbeiter
- Stack: Flask-Mail + SMTP-Konfiguration in `.env`
- Neue Felder in `app/models.py`: `User.email` existiert bereits
- Neues Modul: `app/notifications/service.py`

**Excel/CSV-Export für Schichtpläne**
- `GET /api/v1/shiftplans/<id>/export?format=xlsx` 
- Stack: `openpyxl` (bereits als transitive Dependency vorhanden)
- Datei: `app/shiftplans/routes.py` + `app/shiftplans/services.py`

**Schichtplan-Druckansicht**
- `GET /shiftplans/<id>/print` → CSS `@media print` optimierte Seite
- Keine neue Logik, nur neues Template

**Arbeitstage-Kalender für Urlaubsanträge**
- Mini-Kalender der den ausgewählten Zeitraum visuell hervorhebt
- Feiertage (DE, konfigurierbar per Bundesland) als gesperrte Tage markieren
- Neue Dependency: `holidays` Python-Paket

### Priorität 2 — Mittlere Features (1–2 Wochen)

**Maschinenwartungs-Intervalle (Preventive Maintenance)**
- `MaintenanceInterval` Modell: `machine_id`, `interval_days`, `last_done_at`, `next_due_at`
- Dashboard-Widget: "Fällige Wartungen diese Woche"
- Auto-Task-Erstellung wenn Intervall überschritten
- Integration in Daily Briefing
- Dateien: `app/models.py`, neues `app/maintenance/` Blueprint

**QR-Code für Maschinen**
- `GET /api/v1/machines/<id>/qr` → PNG QR-Code der auf `/machines/<id>` zeigt
- Auf der Maschinen-Detailseite anzeigen + drucken
- Stack: `qrcode` Python-Paket
- Datei: `app/machines/routes.py`

**Benachrichtigungs-Center im Dashboard**
- `Notification` Modell: `user_id`, `type`, `title`, `body`, `read_at`, `created_at`
- Glocken-Icon im Header mit ungelesenen Badge
- Endpunkte: `GET /api/v1/notifications`, `PATCH /api/v1/notifications/<id>/read`
- Trigger: Task-Zuweisung, Urlaubsentscheidung, Schichtplan-Publish

**Zwei-Faktor-Authentifizierung (TOTP)**
- `User.totp_secret` Feld (nullable)
- Setup-Flow: QR-Code generieren → verifizieren → aktivieren
- Login-Flow: nach Passwort → TOTP-Code abfragen
- Stack: `pyotp` Python-Paket
- Dateien: `app/auth/routes.py`, `app/auth/services.py`, `app/models.py`

**Volltext-Suche verbessern**
- Aktuell: einfache LIKE-Queries in `app/services/search_service.py`
- Upgrade: SQLite FTS5 (Full-Text Search) für Tasks, Fehler, Dokumente
- Keine externe Dependency nötig — SQLite-native
- Ergebnis-Ranking und Snippet-Hervorhebung

### Priorität 3 — Größere Features (2–4 Wochen)

**Mobile App / PWA**
- Service Worker für Offline-Fähigkeit (Tasks lesen, Handover anlegen)
- Web App Manifest (`manifest.json`) für "Zum Startbildschirm hinzufügen"
- Push-Benachrichtigungen via Web Push API
- Responsive-Audit aller bestehenden Templates

**Echtzeit-Updates (WebSocket / SSE)**
- Server-Sent Events für Task-Status-Änderungen und neue Handover
- Stack: Flask + `flask-sse` oder direkt `EventSource` API
- Kein WebSocket-Server nötig — SSE reicht für Uni-Direktional

**Mitarbeiter-Self-Service Portal**
- Eigene Schichtzeiten einsehen
- Urlaubsantrag direkt stellen (ohne Admin-Zugang zur vollen App)
- Eigene Profildaten einsehen
- Separate Jinja2-Route `/portal` mit eingeschränkter Navigation

**Audit-Trail UI**
- `ShiftPlanChangeLog` hat bereits alle Daten (Zeile 55 in `models.py`)
- Fehlende UI: Timeline-Ansicht pro Schichtplan
- Endpunkt existiert: `GET /api/v1/shiftplans/<id>/changelog`
- Nur neues Template nötig, kein Backend-Change

**Berichts-Templates**
- Aktuell: ein festes HTML-Template für Wartungsberichte
- Upgrade: Admin kann Templates hochladen/bearbeiten
- `ReportTemplate` Modell mit Jinja2-Syntax in der Datenbank
- Gefährlich (SSTI) — Template-Engine muss sandboxed sein (`jinja2.sandbox`)

**Lager-Bestellvorschläge**
- Aktuell: Prognose zeigt nur Warnungen
- Upgrade: "Bestellung vorschlagen" Button generiert strukturierte Einkaufsliste
- PDF-Export der Einkaufsliste
- Optional: Integration mit Lieferanten-API (konfigurierbar per Umgebungsvariable)

### Priorität 4 — Langfristig / Optional

**PostgreSQL-Migration**
- `DATABASE_URL` auf Postgres umstellen
- Alembic-Migrationen (Voraussetzung: Schuld #1 abbauen)
- Docker Compose um PostgreSQL-Service erweitern
- Empfohlen ab ~10.000 Datenbankzeilen oder Multi-User-Produktion

**Multi-Mandanten-Fähigkeit**
- `Tenant` Modell, alle anderen Modelle bekommen `tenant_id` FK
- Jeder Mandant hat eigene Departments, Mitarbeiter, Maschinen
- Erfordert kompletten Query-Layer-Umbau — nicht rückwärtskompatibel

**REST API v2**
- Versionierter Endpunkt `/api/v2/` mit konsistenter Response-Struktur (Schuld #3 gelöst)
- Pagination für alle Listen-Endpunkte (bereits `paginate_query()` in `responses.py`)
- Cursor-basierte Pagination statt Offset für große Datasets

---

## Offene Kleinigkeiten (Issues-Backlog)

| # | Datei | Problem | Aufwand |
|---|-------|---------|---------|
| 1 | `app/responses.py` | `payload.update(data)` macht Root + data inkonsistent | M |
| 2 | `app/vacations/routes.py` | `datetime.utcnow()` deprecation | XS |
| 3 | `app/services/task_service.py` | `datetime.utcnow()` deprecation | XS |
| 4 | `app/shiftplans/services.py` | `914 Zeilen` — könnte in Sub-Module aufgeteilt werden | M |
| 5 | `tests/conftest.py` | `make_document` nutzt `datetime.utcnow()` | XS |
| 6 | Alle Routes | `Query.get()` → `db.session.get()` Legacy-Warnings | S |
| 7 | `app/__init__.py` | `_run_lightweight_migrations()` → Alembic | L |
| 8 | `app/models.py` | 658 Zeilen, alle Modelle in einer Datei | L |
| 9 | `seed.py` + `seed_demo.py` | zwei Skripte mit überlappender Logik | S |
| 10 | Alle Templates | Inline-JS → externe Modul-Dateien | L |

---

## Entwicklungs-Workflow

```bash
# Lokaler Start
python run.py --host 127.0.0.1 --port 5050

# Tests
PYTHONPATH=. .venv/Scripts/pytest tests/ -q --tb=short

# Lint
.venv/Scripts/python -m ruff check .

# CSS neu bauen (nur wenn Tailwind-Klassen geändert)
npm.cmd run build:css

# Demo-Daten
python seed.py
```

**Neue Route anlegen:**
1. `app/<domain>/routes.py` → Blueprint-Endpunkt
2. `app/services/<domain>_service.py` → Business-Logik
3. `app/__init__.py` → Blueprint registrieren (in passender Gruppe)
4. `tests/test_<domain>.py` → mindestens Happy-Path + Fehlerfall
5. `app/docs/openapi.py` → Endpunkt dokumentieren

**Neue Seite anlegen:**
1. `app/templates/<seite>.html` → `{% extends "base.html" %}`
2. `app/web/routes.py` → Web-Route ergänzen
3. `app/templates/base.html` → Nav-Eintrag (falls sichtbar)
4. Berechtigung: `@dashboard_permission_required("dashboard_name", "view")`

---

## KI-Kontext für neue Sessions

Wenn du als KI-Agent an diesem Projekt arbeitest:

- **Code-Stil**: keine Type-Hints, kurze Docstrings, `snake_case`, `logger.exception()` statt `pass`
- **Service-Pattern**: gibt immer `(result, error_dict, status_code)` zurück
- **Nicht anfassen ohne Absprache**: `app/models.py` (Risiko), `app/responses.py` (Breaking Change)
- **Tests laufen immer zuerst**: `pytest tests/ -q` muss grün sein vor dem Commit
- **Commit-Stil**: Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`, `docs:`)
- **Shims sind weg**: Imports immer direkt aus `app/services/<name>_service.py`
- **Blueprint-Gruppen** in `app/__init__.py`: Auth/Admin · Core · Workforce · Cross-cutting
