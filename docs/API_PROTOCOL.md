# Maintenance Assistant API - HTTPS-Protokoll

Dieses Dokument beschreibt die bestehenden API-Routen fuer den Maintenance Assistant. In Produktion sollte die API ausschliesslich ueber HTTPS betrieben werden.

## Basis

```http
Base URL: https://deine-domain.de
API Prefix: /api
Content-Type: application/json
Authorization: Bearer <access_token>
```

Lokale Entwicklung:

```http
Base URL: http://127.0.0.1:5000
```

## Sicherheit

Alle geschuetzten Endpunkte erwarten einen JWT im `Authorization`-Header:

```http
Authorization: Bearer eyJhbGciOi...
```

Passwoerter werden nicht im Klartext gespeichert, sondern als Hash. Der Token wird ueber `/api/auth/login` ausgestellt.

## Rollen- und Rechtemodell

| Rolle | Wert | Zugriff |
| --- | --- | --- |
| Master/Admin | `master_admin` | Alle Bereiche und alle Daten |
| IT | `it` | Eigener Bereich |
| Verwaltung | `verwaltung` | Eigener Bereich |
| Instandhaltung | `instandhaltung` | Eigener Bereich |
| Produktion | `produktion` | Eigener Bereich |

Zusaetzlich zur Rolle gibt es Dashboard-Rechte pro User. Der Admin kann fuer jedes Dashboard `can_view` und `can_write` setzen. Die API prueft diese Rechte serverseitig.

Dashboard-Keys:

```text
dashboard, tasks, errors, employees, shiftplans, machines, inventory, admin_users
```

`admin_users` bleibt effektiv `master_admin` vorbehalten. Normale Rollen sehen und bearbeiten Tasks und Fehlerkatalogeintraege weiterhin nur im eigenen Bereich.

Mitarbeiterdaten werden gestuft ausgeliefert:

| Stufe | Felder |
| --- | --- |
| `none` | Keine Mitarbeiterdaten |
| `basic` | Personalnummer, Name, Abteilung, Team |
| `shift` | Basic plus Schicht, Qualifikationen, Favoritenmaschine |
| `confidential` | Shift plus Geburtsdatum, Adresse, Gehaltsklasse, Dokumente |

## Standardantworten

Erfolg:

```json
{
  "id": 1,
  "title": "Motor M12 pruefen"
}
```

Fehler:

```json
{
  "error": "Forbidden"
}
```

Typische Statuscodes:

| Code | Bedeutung |
| --- | --- |
| `200` | Erfolgreiche Anfrage |
| `201` | Ressource erstellt |
| `204` | Ressource geloescht, kein Body |
| `400` | Ungueltige Anfrage |
| `401` | Nicht authentifiziert |
| `403` | Keine Berechtigung |
| `404` | Ressource nicht gefunden |
| `409` | Konflikt, z. B. Name existiert bereits |

## Auth

### Benutzer registrieren

```http
POST /api/auth/register
Content-Type: application/json
```

Request:

```json
{
  "username": "admin",
  "email": "admin@example.com",
  "password": "secret",
  "role": "master_admin"
}
```

Normaler Benutzer:

```json
{
  "username": "max",
  "email": "max@example.com",
  "password": "secret",
  "role": "instandhaltung",
  "department": "Instandhaltung"
}
```

Response `201`:

```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "role": "master_admin",
  "department": null,
  "permissions": {
    "tasks": {
      "can_view": true,
      "can_write": true,
      "employee_access_level": "none"
    }
  },
  "created_at": "2026-04-28T18:30:00"
}
```

### Login

```http
POST /api/auth/login
Content-Type: application/json
```

Request:

```json
{
  "login": "admin",
  "password": "secret"
}
```

`login` kann Benutzername oder E-Mail sein.

Response `200`:

```json
{
  "access_token": "<jwt>",
  "user": {
    "id": 1,
    "username": "admin",
    "email": "admin@example.com",
    "role": "master_admin",
    "department": null,
    "created_at": "2026-04-28T18:30:00"
  }
}
```

### Aktuellen Benutzer lesen

```http
GET /api/auth/me
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "id": 1,
  "username": "admin",
  "email": "admin@example.com",
  "role": "master_admin",
  "department": null,
  "permissions": {
    "employees": {
      "can_view": true,
      "can_write": true,
      "employee_access_level": "confidential"
    }
  },
  "created_at": "2026-04-28T18:30:00"
}
```

## Admin-Rechteverwaltung

### Rechte eines Users lesen

Nur `master_admin`.

```http
GET /api/admin/users/2/permissions
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "tasks": {
    "can_view": true,
    "can_write": true,
    "employee_access_level": "none"
  },
  "employees": {
    "can_view": true,
    "can_write": false,
    "employee_access_level": "basic"
  }
}
```

### Rechte eines Users ersetzen

Nur `master_admin`.

```http
PUT /api/admin/users/2/permissions
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "permissions": {
    "tasks": {
      "can_view": true,
      "can_write": true,
      "employee_access_level": "none"
    },
    "employees": {
      "can_view": true,
      "can_write": false,
      "employee_access_level": "basic"
    }
  }
}
```

Ungueltige Dashboard-Keys oder Mitarbeiterdatenstufen liefern `400`.

## Departments

### Departments auflisten

```http
GET /api/departments
Authorization: Bearer <access_token>
```

Response `200`:

```json
[
  {
    "id": 1,
    "name": "Instandhaltung"
  }
]
```

### Department erstellen

Nur `master_admin`.

```http
POST /api/departments
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "name": "Qualitaetssicherung"
}
```

Response `201`:

```json
{
  "id": 5,
  "name": "Qualitaetssicherung"
}
```

## Tasks

### Task-Vorschlag aus Freitext

```http
POST /api/tasks/suggest
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "text": "Maschine 3 macht laute Geraeusche am Lager."
}
```

Response `200` ist ein Vorschlag und wird nicht gespeichert:

```json
{
  "title": "Pruefung: Maschine 3 macht laute Geraeusche am Lager.",
  "description": "Maschine 3 macht laute Geraeusche am Lager.",
  "department": "Instandhaltung",
  "priority": "soon",
  "status": "open",
  "possible_cause": "Lager verschlissen...",
  "recommended_action": "Maschine 3 sicher pruefen..."
}
```

### Tasks auflisten

```http
GET /api/tasks
Authorization: Bearer <access_token>
```

Optionale Filter:

```http
GET /api/tasks?status=open&priority=urgent
```

Response `200`:

```json
[
  {
    "id": 1,
    "title": "Motor M12 pruefen",
    "description": "Motor laeuft unruhig und zieht zu viel Strom.",
    "priority": "urgent",
    "status": "open",
    "due_date": "2026-04-30",
    "department": {
      "id": 3,
      "name": "Instandhaltung"
    },
    "created_by": 1,
    "created_at": "2026-04-28T18:30:00",
    "updated_at": "2026-04-28T18:30:00"
  }
]
```

### Task erstellen

```http
POST /api/tasks
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

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

Erlaubte Prioritaeten:

```text
urgent, soon, normal
```

Erlaubte Status:

```text
open, in_progress, done, cancelled
```

Response `201`: Task-Objekt.

### Einzelnen Task lesen

```http
GET /api/tasks/1
Authorization: Bearer <access_token>
```

Response `200`: Task-Objekt.

### Task aktualisieren

```http
PUT /api/tasks/1
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "status": "in_progress",
  "priority": "urgent"
}
```

Response `200`: Aktualisiertes Task-Objekt.

### Task loeschen

```http
DELETE /api/tasks/1
Authorization: Bearer <access_token>
```

Response:

```http
204 No Content
```

### Heutige Tasks abrufen

```http
GET /api/tasks/today
Authorization: Bearer <access_token>
```

Response `200`: Liste der Tasks mit `due_date` gleich dem aktuellen Datum des Servers.

### Tasks priorisieren

```http
POST /api/tasks/prioritize
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request optional:

```json
{
  "status": "open",
  "limit": 20
}
```

Response `200` ist eine priorisierte, nicht gespeicherte Bewertung sichtbarer Tasks:

```json
[
  {
    "task": {
      "id": 1,
      "title": "Motor M12 pruefen"
    },
    "score": 88,
    "risk_level": "critical",
    "reason": "Prioritaet urgent; Faelligkeit ist heute; mechanische Symptome",
    "recommended_action": "Sofort pruefen, Anlage sichern und Instandhaltung informieren."
  }
]
```

Ohne OpenAI-Key nutzt die API den lokalen Fallback. Die Priorisierung speichert keine Scores in der Datenbank.

## Fehlerkatalog

### Fehlerbeschreibung analysieren

```http
POST /api/errors/analyze
Authorization: Bearer <access_token>
Content-Type: application/json
```

Response `200` ist ein Vorschlag und wird nicht gespeichert:

```json
{
  "machine": "Maschine 3",
  "title": "Stoerung: Sensor meldet sporadisch kein Signal",
  "description": "Sensor meldet sporadisch kein Signal an Maschine 3.",
  "possible_causes": "Sensor verschmutzt...",
  "solution": "Anlage sichern...",
  "department": "Instandhaltung"
}
```

### Fehler auflisten

```http
GET /api/errors
Authorization: Bearer <access_token>
```

Response `200`:

```json
[
  {
    "id": 1,
    "machine": "Verpackungsmaschine 3",
    "error_code": "E104",
    "title": "Sensor erkennt Produkt nicht",
    "description": "Der Lichttaster erkennt das Produkt sporadisch nicht.",
    "possible_causes": "Sensor verschmutzt, falscher Abstand, Kabelbruch",
    "solution": "Sensor reinigen, Abstand pruefen, Kabel messen",
    "department": {
      "id": 3,
      "name": "Instandhaltung"
    },
    "created_at": "2026-04-28T18:30:00"
  }
]
```

### Fehler anlegen

```http
POST /api/errors
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

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

Response `201`: Fehlerkatalog-Objekt.

### Fehler suchen

```http
GET /api/errors/search?query=E104
Authorization: Bearer <access_token>
```

`query` sucht in Fehlercode, Maschine, Titel und Beschreibung.

Response `200`: Liste passender Fehlerkatalogeintraege.

### Einzelnen Fehler lesen

```http
GET /api/errors/1
Authorization: Bearer <access_token>
```

Response `200`: Fehlerkatalog-Objekt.

### Fehler aktualisieren

```http
PUT /api/errors/1
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request:

```json
{
  "solution": "Sensor reinigen, Abstand auf 40 mm einstellen, Kabel auf Bruch pruefen."
}
```

Response `200`: Aktualisiertes Fehlerkatalog-Objekt.

### Fehler loeschen

```http
DELETE /api/errors/1
Authorization: Bearer <access_token>
```

Response:

```http
204 No Content
```

## KI-Assistent

### Chat-Anfrage senden

```http
POST /api/ai/chat
Authorization: Bearer <access_token>
Content-Type: application/json
```

Request Fehlerhilfe:

```json
{
  "message": "Maschine 3 zeigt Fehler E104. Was soll ich pruefen?"
}
```

Response `200`:

```json
{
  "type": "error_help",
  "answer": "Der Fehler E104 an Verpackungsmaschine 3 passt zu: Sensor erkennt Produkt nicht...",
  "diagnostics": {
    "status": "openai_used",
    "fallback_used": false
  },
  "data": [
    {
      "id": 1,
      "machine": "Verpackungsmaschine 3",
      "error_code": "E104",
      "title": "Sensor erkennt Produkt nicht"
    }
  ]
}
```

Request Task-Abfrage:

```json
{
  "message": "Welche Tasks stehen heute an?"
}
```

Response `200`:

```json
{
  "type": "tasks_today",
  "answer": "Heute stehen diese Tasks an:\n- Motor M12 pruefen (urgent, open, Bereich: Instandhaltung)",
  "diagnostics": {
    "status": "local_answer",
    "fallback_used": false
  },
  "data": [
    {
      "id": 1,
      "title": "Motor M12 pruefen"
    }
  ]
}
```

Moegliche Diagnosewerte:

| Status | Bedeutung |
| --- | --- |
| `local_answer` | Lokale Antwort ohne OpenAI, z. B. heutige Tasks |
| `api_key_missing` | Kein OpenAI-Key konfiguriert, lokaler Fallback genutzt |
| `openai_error` | OpenAI-Anfrage fehlgeschlagen, lokaler Fallback genutzt |
| `fallback_used` | Fallback wurde ohne genauere Kategorie genutzt |
| `openai_used` | OpenAI-Antwort wurde verwendet |

`diagnostics` enthaelt zusaetzlich `provider` und `model`, aber niemals den API-Key. Die Chat-Bubble zeigt diese Werte als kleine Statuszeile pro Antwort.

### KI-Konfiguration pruefen

Nur `master_admin`.

```http
GET /api/ai/status
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "api_key_configured": true,
  "provider": "OpenAI",
  "model": "gpt-4o-mini",
  "ready": true,
  "last_error": null
}
```

Der API-Key wird nie im Response-Body ausgegeben.

Wenn `api_key_configured` false ist, fehlt die lokale `.env` oder `OPENAI_API_KEY` ist leer. `.env.example` ist nur eine Vorlage und darf keine echten Secrets enthalten.

### AI-Feedback speichern

```http
POST /api/ai/feedback
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{
  "prompt": "Was bedeutet E104?",
  "response": "Der Fehler deutet auf...",
  "rating": "helpful",
  "comment": "optional"
}
```

## Dokumente

```http
GET /api/documents
GET /api/documents?task_id=1&department=Instandhaltung&machine=Maschine
GET /api/documents/1
POST /api/documents/1/review
GET /api/documents/1/download
```

Dokumente benoetigen `documents.view`. Berichte werden lokal als HTML unter `documents/YYYY/MM/task_<id>/maintenance_report.html` gespeichert.

### Dokument pruefen

```http
POST /api/documents/1/review
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "document": {
    "id": 1,
    "title": "Wartungsbericht Task 1"
  },
  "quality_score": 80,
  "status": "needs_review",
  "findings": [
    {
      "field": "Ursache",
      "severity": "critical",
      "message": "Ursache fehlt im Wartungsbericht."
    }
  ],
  "recommendations": [
    "Ursache oder wahrscheinliche Fehlerquelle dokumentieren."
  ],
  "diagnostics": {
    "status": "local_answer",
    "provider": "mock"
  }
}
```

Die Pruefung speichert keine Ergebnisse. Ohne OpenAI-Key nutzt die API einen lokalen Fallback.

## Wissenssuche

```http
GET /api/search?q=Sensorfehler
Authorization: Bearer <access_token>
```

Response:

```json
{
  "query": "Sensorfehler",
  "results": [
    {
      "type": "task",
      "title": "Sensor pruefen",
      "summary": "Beschreibung",
      "url": "/api/tasks/1"
    }
  ]
}
```

## Mitarbeiter

Mitarbeiter-Endpunkte benoetigen `employees.view`. Schreibzugriffe, Uploads und Downloads vertraulicher Dokumente benoetigen `employees.write` und `employee_access_level=confidential`.

```http
GET /api/employees
POST /api/employees
PUT /api/employees/1
DELETE /api/employees/1
```

Mitarbeiter enthalten fuer die Schichtplanung:

```json
{
  "qualifications": "CNC, Staplerschein",
  "favorite_machine": "Anlage 4"
}
```

## Maschinen

Maschinen-Endpunkte benoetigen `machines.view` oder `machines.write`.

```http
GET /api/machines
POST /api/machines
GET /api/machines/1/history
PUT /api/machines/1
DELETE /api/machines/1
```

Request:

```json
{
  "name": "Anlage 4",
  "produced_item": "Gehaeuse",
  "required_employees": 2
}
```

### Maschinen-Historie

```http
GET /api/machines/1/history
Authorization: Bearer <access_token>
```

Benoetigt `machines.view`. Tasks, Fehler und Dokumente werden nur einbezogen, wenn der Benutzer fuer das jeweilige Dashboard Leserechte hat.

Response `200`:

```json
{
  "machine": {
    "id": 1,
    "name": "Anlage 4"
  },
  "summary": {
    "text": "Anlage 4 hat 2 Tasks, 1 Fehler und 3 Dokumente in der Historie.",
    "diagnostics": {
      "status": "local_answer"
    }
  },
  "source_counts": {
    "tasks": 2,
    "errors": 1,
    "documents": 3,
    "total": 6
  },
  "timeline": [
    {
      "type": "task",
      "date": "2026-05-01T12:00:00",
      "title": "Stillstand Anlage 4",
      "status": "open",
      "summary": "Sensorfehler pruefen",
      "url": "/api/tasks/1"
    }
  ]
}
```

Die Historie ist read-only und speichert keine KI-Zusammenfassungen.

## Lager

Lager-Endpunkte benoetigen `inventory.view` oder `inventory.write`.

```http
GET /api/inventory
GET /api/inventory/summary
POST /api/inventory
PUT /api/inventory/1
DELETE /api/inventory/1
```

Request:

```json
{
  "name": "Schraube M6",
  "unit_cost": 0.12,
  "quantity": 500,
  "machine_id": 1,
  "manufacturer": "ACME"
}
```

Summary:

```json
{
  "material_count": 1,
  "total_quantity": 500,
  "total_value": 60.0
}
```

### Ersatzteil-Prognose

```http
POST /api/inventory/forecast
Authorization: Bearer <access_token>
Content-Type: application/json
```

Benoetigt `inventory.view` und `tasks.view`.

Request optional:

```json
{
  "status": "open",
  "limit": 20,
  "low_stock_threshold": 5
}
```

Response `200`:

```json
{
  "items": [
    {
      "machine": {"id": 1, "name": "Anlage 4"},
      "material": {"id": 2, "name": "Sensor S1"},
      "quantity": 1,
      "task": {"id": 7, "title": "Stillstand Anlage 4"},
      "score": 92,
      "risk_level": "high",
      "reason": "Sensor S1 liegt bei 1 Stueck und damit unter oder auf dem Mindestbestand 5; Task-Risiko critical.",
      "recommended_action": "Nachbestellung vorbereiten und Task vor Arbeitsbeginn pruefen."
    }
  ],
  "unmatched_tasks": [],
  "summary": {
    "critical": 0,
    "high": 1,
    "medium": 0,
    "total": 1
  }
}
```

Die Prognose speichert keine Ergebnisse. Maschinen werden in Version 1 ueber Namensvorkommen in Task-Titel oder Beschreibung erkannt.

## Schichtplanung

Schichtplan-Endpunkte benoetigen `shiftplans.view` oder `shiftplans.write`. Die Generierung benoetigt zusaetzlich mindestens Mitarbeiterdatenstufe `shift`, weil dabei Produktionsmitarbeiter geplant werden.

```http
GET /api/shiftplans
POST /api/shiftplans/generate
DELETE /api/shiftplans/1
```

Request:

```json
{
  "title": "KW 18 Produktion",
  "start_date": "2026-05-01",
  "days": 7,
  "rhythm": "2-Schicht",
  "preferences": "Max bevorzugt Fruehschicht, Lisa bevorzugt Anlage 4"
}
```

Die Generierung beruecksichtigt Produktionsmitarbeiter, Rhythmus, Praeferenzen, Qualifikationen, Favoritenmaschine und Maschinenbedarf. Ohne OpenAI-Key oder bei OpenAI-Fehlern wird ein lokaler Fallback genutzt.

## cURL-Beispiele

Login:

```bash
curl -X POST https://deine-domain.de/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"login\":\"admin\",\"password\":\"secret\"}"
```

Fehler suchen:

```bash
curl "https://deine-domain.de/api/errors/search?query=E104" \
  -H "Authorization: Bearer <access_token>"
```

Chat:

```bash
curl -X POST https://deine-domain.de/api/ai/chat \
  -H "Authorization: Bearer <access_token>" \
  -H "Content-Type: application/json" \
  -d "{\"message\":\"Maschine 3 zeigt Fehler E104. Was soll ich pruefen?\"}"
```

## Produktionshinweise

- HTTPS ueber Reverse Proxy wie Nginx, Caddy oder Traefik terminieren.
- `JWT_SECRET_KEY` in Produktion stark und geheim halten.
- `.env` niemals committen.
- CORS nur fuer bekannte Frontend-Domains erlauben.
- Rate-Limits fuer Login und KI-Chat einplanen.
- Datenbank-Backups fuer den Fehlerkatalog automatisieren.
