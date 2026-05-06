# Changelog

All notable changes to the Maintenance Assistant are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

---

## [Unreleased]

### Added
- Edit and delete UI for employees, errors, and machines (PUT/DELETE routes were
  already in place; this wires up the missing frontend for all three entities)
- `.ruff_cache/` added to `.gitignore`

### Fixed
- Docstrings added to all public model classes and `to_dict` methods in `models.py`

---

## [0.9.0] — 2026-05-06

### Added
- Mitarbeiter- und Urlaubsanträge-UI auf Card-Standard umgestellt
- Realistische Demo-Daten mit vollständigen Verknüpfungen zwischen Modellen
- Nutzersuche mit Attribut-Filtern (Rolle, Status, Freitext)

### Fixed
- `datetime.utcnow()` Deprecation-Warnungen behoben
- `Query.get()` Legacy-Warnungen behoben
- `/api/v1/` Prefix-Fehler im Login und `auth.js` korrigiert

---

## [0.8.0] — 2026-04-15

### Added
- Schichtübergabe-Protokoll (ShiftHandover)
- Urlaubsplanung mit Genehmigungsworkflow (VacationRequest)
- Drag-and-Drop im Schichtplan
- ArbZG-konforme Schichtgenerierung mit Fairness-Algorithmus
- Schichtplan: farbige Zellen, Sticky-Spalte, Veröffentlichen-Workflow, Audit-Log

### Changed
- Flask-Migrate eingerichtet, `_run_lightweight_migrations()` entfernt

---

## [0.7.0] — 2026-03-20

### Added
- API-Versionierung `/api/v1/`, Pagination, OpenAPI v1 Spec
- JWT-Logout mit Server-seitiger Token-Blocklist
- Saubere Service-Schicht (Task, Employee, Error)
- Task-Delete-Button, Race-Condition-Fix bei Button-Disable
- Fehler-Assistent-Endpunkt mit lokalem Katalog-Lookup und AI-Anreicherung

### Changed
- Blueprints gruppiert, Shims entfernt, Tests umbenannt

---

## [0.6.0] — 2026-03-01

### Added
- Dokumente-Modul: Liste, Download, AI-Review
- Maschinen-Referenzen normalisiert in Modellen
- Frontend-API-Handling zentralisiert (`api()` Wrapper in `app.js`)
- Health-Route bereinigt, OpenAPI-Dokumentation aktualisiert

---

## [0.5.0] — 2026-02-15

### Added
- Dashboard-KPIs mit Task-Cockpit, Priority-Cards und farbcodierten Zonen
- KI-Chat-Widget mit Markdown-Rendering und Feedback-System
- Daily Briefing via `/api/v1/ai/daily-briefing`
- Error-Assistent mit Ähnlichkeitssuche
- Maschinen-Assistent mit Anlagenakte und KI-Fragen
