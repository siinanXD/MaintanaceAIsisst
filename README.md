# Maintenance Assistant API

Eine modulare Flask-API zur Unterstützung von Wartungs- und Instandhaltungsprozessen.
Die Anwendung bietet Benutzerverwaltung, Aufgabenmanagement, Fehlerkataloge sowie eine optionale KI-gestützte Assistenz.

---

## Features

* Benutzer-Authentifizierung (JWT)
* Rollen- und Rechteverwaltung
* Department-basierte Zugriffskontrolle
* Task-Management (CRUD + Tagesübersicht)
* Fehlerkatalog mit Suchfunktion
* KI-gestützter Chat-Assistent (optional mit OpenAI)
* Persistente Datenspeicherung via SQLite

---

## Projektstruktur

```text
app/
├── auth/           # Login & Registrierung
├── employees/      # Mitarbeiterverwaltung
├── departments/    # Bereiche (IT, Produktion, etc.)
├── tasks/          # Aufgabenverwaltung
├── errors/         # Fehlerkatalog
├── ai/             # KI-Integration
├── health/         # System-Checks
├── static/         # CSS / Assets
└── templates/      # HTML Templates

data/               # Datenbank & Uploads
docs/               # API-Dokumentation
```

---

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

Optional mit HTTPS:

```powershell
python run.py --https
```

Danach erreichbar unter:

```
https://127.0.0.1:5000
```

Hinweis: Das Zertifikat ist selbstsigniert und führt zu einer Browserwarnung (nur Entwicklungsumgebung).

---

## Datenbank

Die SQLite-Datenbank wird automatisch erstellt:

```
data/maintenance.db
```

Initial werden folgende Departments angelegt:

* IT
* Verwaltung
* Instandhaltung
* Produktion

---

## Authentifizierung

### Registrierung

```http
POST /api/auth/register
```

Beispiel:

```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "secret",
  "role": "master_admin"
}
```

---

### Login

```http
POST /api/auth/login
```

```json
{
  "login": "admin",
  "password": "secret"
}
```

Danach:

```
Authorization: Bearer <access_token>
```

---

## Rollen

| Rolle          | Beschreibung |
| -------------- | ------------ |
| master_admin   | Vollzugriff  |
| it             | Bereich IT   |
| verwaltung     | Verwaltung   |
| instandhaltung | Wartung      |
| produktion     | Produktion   |

---

## API Endpoints

### Departments

* `GET /api/departments`
* `POST /api/departments`

---

### Tasks

* `GET /api/tasks`
* `POST /api/tasks`
* `GET /api/tasks/<id>`
* `PUT /api/tasks/<id>`
* `DELETE /api/tasks/<id>`
* `GET /api/tasks/today`

---

### Fehlerkatalog

* `GET /api/errors`
* `POST /api/errors`
* `GET /api/errors/<id>`
* `PUT /api/errors/<id>`
* `DELETE /api/errors/<id>`
* `GET /api/errors/search`

---

### KI-Chat

```http
POST /api/ai/chat
```

```json
{
  "message": "Maschine zeigt Fehler E104"
}
```

---

## KI-Integration

Wenn ein API-Key gesetzt ist, wird OpenAI genutzt:

```env
OPENAI_API_KEY=your_key_here
OPENAI_MODEL=gpt-4o-mini
```

Ohne API-Key wird ein lokaler Fallback verwendet.

---

## Konfiguration

```env
DATABASE_URL=sqlite:///../data/maintenance.db
JWT_SECRET_KEY=your-secret-key
OPENAI_API_KEY=
OPENAI_MODEL=gpt-4o-mini
```

---

## Dokumentation

Detaillierte API-Beschreibung:

```
docs/API_PROTOCOL.md
```

---

## Ziel des Projekts

Ziel ist die Entwicklung eines praxisnahen Tools für technische Bereiche (z. B. Instandhaltung), um:

* Fehler schneller zu analysieren
* Wissen zentral zu speichern
* Aufgaben effizient zu verwalten
* KI sinnvoll im Arbeitsalltag einzusetzen

```
```
