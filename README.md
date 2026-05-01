# Maintenance Assistant

Modulare Flask-Anwendung fuer Wartung, Produktion und Instandhaltung. Die App bietet JWT-Login, rollenbasierte Navigation, Aufgaben, Fehlerkataloge, Mitarbeiterdaten, Maschinen, Lager und optionale KI-Funktionen.

## Features

* Benutzer-Authentifizierung mit JWT
* Rollen- und Dashboard-Rechteverwaltung
* Bereichsbasierte Tasks und Fehlerlisten
* Admin-konfigurierbare Dashboard-Rechte mit getrenntem Lesen und Schreiben
* KI-Service-Layer mit OpenAI- und Mock-Provider
* Smart Task Generator aus Freitext
* KI-gestuetzte Task-Priorisierung mit lokalem Fallback
* KI-gestuetzte Fehleranalyse fuer den Fehlerkatalog
* Automatische HTML-Wartungsberichte fuer abgeschlossene Tasks
* Dokumentenuebersicht mit Filtern und Download
* Wissenssuche ueber Tasks, Fehler und Dokument-Metadaten
* AI-Feedback fuer spaetere Qualitaetsverbesserung
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

## Rollen, Rechte und Navigation

`master_admin` sieht alle Bereiche: Dashboard, Tasks, Fehlerliste, Mitarbeiter, Schichtplan, Maschinen, Lager und Users.

Alle anderen Rollen bekommen Dashboard-Rechte ueber die Admin-Oberflaeche. Pro Dashboard kann der Admin `Anzeigen` und `Bearbeiten` setzen. Die API prueft diese Rechte serverseitig; die Navigation versteckt nur die nicht erlaubten Bereiche.

Mitarbeiterdaten sind zusaetzlich gestuft:

* `none`: keine Mitarbeiterdaten
* `basic`: Personalnummer, Name, Abteilung, Team
* `shift`: zusaetzlich Schicht, Qualifikationen und Favoritenmaschine
* `confidential`: zusaetzlich Geburtsdatum, Adresse, Gehaltsklasse und Dokumente

Tasks und Fehler bleiben fuer Nicht-Admins weiterhin auf den eigenen Bereich gefiltert.

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
* `POST /api/tasks/prioritize`
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

Admin-Rechteverwaltung:

* `GET /api/admin/users/<id>/permissions`
* `PUT /api/admin/users/<id>/permissions`

## KI-Integration

OpenAI ist optional. Ohne API-Key nutzt die App lokale Fallbacks fuer Chat und Schichtplanung. Der KI-Chat baut seinen Kontext aus denselben Dashboard- und Mitarbeiterdatenrechten wie die API. Produktion kann dadurch keine Personaldaten ueber die KI abrufen, waehrend Personalabteilung oder Admins je nach Freigabe mehr Kontext erhalten.

```env
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
AI_PROVIDER=openai
DOCUMENTS_FOLDER=documents
```

Wichtig: `.env.example` ist nur eine Vorlage und wird nicht fuer echte Secrets genutzt. Die App laedt lokale Werte aus `.env`. Lege den echten Key deshalb in `.env` ab; diese Datei ist per `.gitignore` ausgeschlossen.

Die Chat-API gibt sichere Diagnosestati zurueck, ohne Keys offenzulegen:

* `api_key_missing`
* `openai_error`
* `fallback_used`
* `openai_used`

Die Chat-Bubble zeigt pro Antwort, ob OpenAI genutzt wurde, eine lokale Spezialantwort gegriffen hat oder ein Fallback aktiv war. Als Admin kann `/api/ai/status` genutzt werden, um zu pruefen, ob `OPENAI_API_KEY` geladen wurde.

Troubleshooting:

* `api_key_missing`: `.env` fehlt oder `OPENAI_API_KEY` ist leer.
* `openai_error`: Key, Modell oder Netzwerk pruefen.
* `local_answer`: Erwartet fuer schnelle Spezialfaelle wie heutige Tasks.

## KI-Workflows

Smart Task Generator:

* `POST /api/tasks/suggest`
* Erzeugt aus Freitext einen bearbeitbaren Vorschlag.
* Speichert nichts, bis der Nutzer den Vorschlag ins Taskformular uebernimmt.

Task-Priorisierung:

* `POST /api/tasks/prioritize`
* Bewertet sichtbare Tasks nach Dringlichkeit, Faelligkeit, Status und Risikobegriffen.
* Speichert keine Scores und nutzt ohne OpenAI-Key einen lokalen Fallback.

KI-Fehleranalyse:

* `POST /api/errors/analyze`
* Erzeugt Maschine, Fehler, moegliche Ursachen und Loesung als Vorschlag.
* Speichert nichts, bis der Nutzer den Vorschlag uebernimmt und den Fehler speichert.

Wartungsberichte:

* Beim Abschluss eines Tasks kann `generate_report: true` gesendet werden.
* Die App erzeugt einen HTML-Bericht unter `documents/YYYY/MM/task_<id>/`.
* Dokument-Metadaten werden in der Datenbank gespeichert und ueber `/api/documents` gelistet.

Wissenssuche:

* `GET /api/search?q=...`
* Durchsucht zunaechst sichtbare Tasks, Fehler und Dokument-Metadaten.
* Die Struktur ist fuer spaetere Embeddings oder Vector Search vorbereitet.

Die Schichtplanung nutzt Produktionsmitarbeiter, Rhythmus, Praeferenzen, Qualifikationen, Favoritenmaschine und Maschinenbedarf. Der lokale Fallback plant mit max. 8h Schichtdauer und 11h Ruhezeit als Regelhinweis.

## Konfiguration

```env
FLASK_ENV=development
DATABASE_URL=sqlite:///../data/maintenance.db
JWT_SECRET_KEY=change-this-secret-in-production
OPENAI_API_KEY=your_openai_api_key_here
OPENAI_MODEL=gpt-4o-mini
```

`.env` darf nicht committed werden. `.env.example` enthaelt nur Platzhalter. Wenn ein echter Key versehentlich in `.env.example` stand, sollte er beim Anbieter rotiert werden.

## Dokumentation

Das ausfuehrliche API-Protokoll liegt in `docs/API_PROTOCOL.md`.
