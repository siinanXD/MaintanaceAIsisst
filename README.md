# Maintenance Assistant

Modulare Flask-Anwendung fuer Wartung, Produktion und Instandhaltung. Die App bietet JWT-Login, rollenbasierte Navigation, Aufgaben, Fehlerkataloge, Mitarbeiterdaten, Maschinen, Lager und optionale KI-Funktionen.

## Features

* Benutzer-Authentifizierung mit JWT
* Rollen- und Rechteverwaltung
* Bereichsbasierte Tasks und Fehlerlisten
* Admin-only Dashboard, Mitarbeiter, Schichtplan, Maschinen, Lager und Userverwaltung
* Mitarbeiterverwaltung mit Qualifikationen und Favoritenmaschine
* Maschinenverwaltung mit Produktionsinhalt und benoetigter Mitarbeiterzahl
* Lagerverwaltung mit Materialname, Kosten, Anzahl, Maschine, Hersteller und Gesamtwert
* KI-Chat fuer Fehlerhilfe und heutige Tasks
* KI-gestuetzte Schichtplanung fuer Produktionsmitarbeiter mit lokalem Fallback
* Persistente Datenspeicherung via SQLite

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py --host 127.0.0.1 --port 5050
```

Optional mit lokalem HTTPS:

```powershell
python run.py --https
```

Die Standarddatenbank liegt unter `data/maintenance.db`. Beim Start werden die Standardbereiche IT, Verwaltung, Instandhaltung und Produktion angelegt.

## Rollen und Navigation

`master_admin` sieht alle Bereiche: Dashboard, Tasks, Fehlerliste, Mitarbeiter, Schichtplan, Maschinen, Lager und Users.

Alle anderen Rollen sehen nur Tasks und Fehlerliste. Die API filtert Tasks und Fehler fuer normale Rollen auf den eigenen Bereich.

## Wichtige API-Bereiche

Alle geschuetzten Endpunkte verwenden:

```http
Authorization: Bearer <access_token>
```

Auth:

* `POST /api/auth/login`
* `GET /api/auth/me`

Tasks und Fehler:

* `GET/POST /api/tasks`
* `GET/PUT/DELETE /api/tasks/<id>`
* `POST /api/tasks/<id>/start`
* `POST /api/tasks/<id>/complete`
* `GET/POST /api/errors`
* `GET/PUT/DELETE /api/errors/<id>`
* `GET /api/errors/search?query=...`

Admin-only Erweiterungen:

* `GET/POST /api/employees`
* `GET/POST /api/machines`
* `GET/POST /api/inventory`
* `GET /api/inventory/summary`
* `GET /api/shiftplans`
* `POST /api/shiftplans/generate`
* `DELETE /api/shiftplans/<id>`

## KI-Integration

OpenAI ist optional. Ohne API-Key nutzt die App lokale Fallbacks fuer Chat und Schichtplanung.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

Die Chat-API gibt sichere Diagnosestati zurueck, ohne Keys offenzulegen:

* `api_key_missing`
* `openai_error`
* `fallback_used`
* `openai_used`

Die Schichtplanung nutzt Produktionsmitarbeiter, Rhythmus, Praeferenzen, Qualifikationen, Favoritenmaschine und Maschinenbedarf. Der lokale Fallback plant mit max. 8h Schichtdauer und 11h Ruhezeit als Regelhinweis.

## Konfiguration

```env
FLASK_ENV=development
DATABASE_URL=sqlite:///../data/maintenance.db
JWT_SECRET_KEY=change-this-secret-in-production
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

`.env` darf nicht committed werden. `.env.example` enthaelt nur Platzhalter.

## Dokumentation

Das ausfuehrliche API-Protokoll liegt in `docs/API_PROTOCOL.md`.
