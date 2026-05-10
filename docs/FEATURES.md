# Feature Inventory

This document records the current product features and their isolation boundary.
The frontend source of truth is `app/static/core/feature-registry.js`; backend
permissions remain in `app/permissions.py`.

## Features

| Feature | Route | Permission | Current boundary |
| --- | --- | --- | --- |
| Dashboard | `/` | `dashboard` | Cockpit, KPIs, briefing, calendar preview |
| Tasks | `/tasks` | `tasks` | Task CRUD, suggestions, priority scoring, workflow reports |
| Error catalog | `/errors` | `errors` | Error CRUD, similar-error search, AI analysis |
| Employees | `/employees` | `employees` | Employee records, access tiers, employee documents |
| Machines | `/machines` | `machines` | Machine CRUD, history, machine assistant |
| Inventory | `/inventory` | `inventory` | Materials, summary, spare-parts forecast |
| Shift plans | `/shiftplans` | `shiftplans` | Generation, calendar, drag-and-drop, publish, changelog |
| Shift handover | `/handover` | `shiftplans` | Handover create, edit, complete, filtering |
| Vacations | `/vacations` | `employees` | Requests, approval, rejection, balance |
| Documents | `/documents` | `documents` | Generated reports, filters, download, quality review |
| Admin users | `/admin/users` | `admin_users` | User list and dashboard permission management |

## Isolation Rules

- New navigation entries must be added to `app/static/core/feature-registry.js`
  first, then wired to templates with `data-feature-key`.
- If a feature reuses another permission, set `permissionKey` explicitly instead
  of duplicating permission checks in templates or scripts.
- New frontend code should live behind one feature initializer and avoid adding
  more behavior to the legacy `app/static/app.js` bundle.
- Dynamic API data should be rendered with DOM APIs and `textContent` unless the
  string is a static, trusted empty-state fragment.
