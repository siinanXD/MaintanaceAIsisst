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

## Rollenmodell

| Rolle | Wert | Zugriff |
| --- | --- | --- |
| Master/Admin | `master_admin` | Alle Bereiche und alle Daten |
| IT | `it` | Eigener Bereich |
| Verwaltung | `verwaltung` | Eigener Bereich |
| Instandhaltung | `instandhaltung` | Eigener Bereich |
| Produktion | `produktion` | Eigener Bereich |

Normale Rollen sehen und bearbeiten nur Tasks und Fehlerkatalogeintraege ihres eigenen Bereichs.

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
  "created_at": "2026-04-28T18:30:00"
}
```

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

## Fehlerkatalog

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
  "data": [
    {
      "id": 1,
      "title": "Motor M12 pruefen"
    }
  ]
}
```

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
