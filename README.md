# Maintenance Assistant API

Flask-API fuer Login, Rollen, Departments, Tasks, Fehlerkatalog und einen einfachen KI-Chat-Assistenten.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Lokaler HTTPS-Start:

```powershell
python run.py --https
```

Danach im Browser oeffnen:

```text
https://127.0.0.1:5000
```

Der Browser kann beim lokalen Zertifikat eine Warnung anzeigen. Fuer die Entwicklung ist das normal, weil Flask ein selbstsigniertes Zertifikat erzeugt.

Die SQLite-Datenbank wird automatisch unter `data/maintenance.db` angelegt. Die Standardbereiche `IT`, `Verwaltung`, `Instandhaltung` und `Produktion` werden beim Start erstellt.

## SQL-Persistenz pruefen

Tasks, Fehlerliste, Mitarbeiter und Mitarbeiter-Dokumente werden dauerhaft in SQLite gespeichert:

- `task`
- `error_entry`
- `employee`
- `employee_document`

Nach dem Login kann der Datenbankstatus geprueft werden:

```http
GET /api/health/database
Authorization: Bearer <access_token>
```

Die Antwort enthaelt Datenbankdatei, Tabellen und aktuelle Datensatz-Anzahlen.

## Rollen

- `master_admin`: darf alles sehen und verwalten
- `it`: sieht und bearbeitet Tasks/Fehler des eigenen Bereichs
- `verwaltung`: sieht und bearbeitet Tasks/Fehler des eigenen Bereichs
- `instandhaltung`: sieht und bearbeitet Tasks/Fehler des eigenen Bereichs
- `produktion`: sieht und bearbeitet Tasks/Fehler des eigenen Bereichs

## Auth

### Registrieren

```http
POST /api/auth/register
Content-Type: application/json

{
  "username": "admin",
  "email": "admin@example.com",
  "password": "secret",
  "role": "master_admin"
}
```

Normale User brauchen einen Bereich:

```json
{
  "username": "max",
  "email": "max@example.com",
  "password": "secret",
  "role": "instandhaltung",
  "department": "Instandhaltung"
}
```

### Login

```http
POST /api/auth/login
Content-Type: application/json

{
  "login": "admin",
  "password": "secret"
}
```

Alle geschuetzten Routen erwarten danach:

```http
Authorization: Bearer <access_token>
```

## Routen

Ein ausfuehrliches HTTPS-Protokoll mit Requests, Responses, Statuscodes und cURL-Beispielen liegt unter `docs/API_PROTOCOL.md`.

Ein modernes CSS-Theme fuer eine spaetere Web-Oberflaeche liegt unter `app/static/styles.css`.

### Departments

- `GET /api/departments`
- `POST /api/departments` nur `master_admin`

### Tasks

- `GET /api/tasks`
- `POST /api/tasks`
- `GET /api/tasks/<id>`
- `PUT /api/tasks/<id>`
- `DELETE /api/tasks/<id>`
- `GET /api/tasks/today`

Beispiel:

```json
{
  "title": "Motor M12 pruefen",
  "description": "Motor laeuft unruhig und zieht zu viel Strom.",
  "department": "Instandhaltung",
  "due_date": "2026-04-30",
  "priority": "urgent",
  "status": "open"
}
```

### Fehlerkatalog

- `GET /api/errors`
- `POST /api/errors`
- `GET /api/errors/<id>`
- `PUT /api/errors/<id>`
- `DELETE /api/errors/<id>`
- `GET /api/errors/search?query=E104`

Beispiel:

```json
{
  "machine": "Verpackungsmaschine 3",
  "error_code": "E104",
  "title": "Sensor erkennt Produkt nicht",
  "description": "Der Lichttaster erkennt das Produkt sporadisch nicht.",
  "possible_causes": "Sensor verschmutzt, falscher Abstand, Kabelbruch",
  "solution": "Sensor reinigen, Abstand pruefen, Kabel messen",
  "department": "Instandhaltung"
}
```

### KI-Chat

- `POST /api/ai/chat`

```json
{
  "message": "Maschine 3 zeigt Fehler E104. Was soll ich pruefen?"
}
```

Wenn `OPENAI_API_KEY` in `.env` gesetzt ist, nutzt die API OpenAI mit dem Fehlerkatalog als Kontext. Ohne Key antwortet sie mit einem lokalen Fallback aus dem gefundenen Katalogeintrag.

## Konfiguration

`.env`:

```env
DATABASE_URL=sqlite:///../data/maintenance.db
JWT_SECRET_KEY=change-this-secret-in-production
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```
