"""Permission-aware chat template helpers."""

from app.security import has_dashboard_permission


def chat_templates_for_user(user):
    """Return chat suggestions available for the given user."""
    templates = []
    if has_dashboard_permission(user, "tasks", "view"):
        add_template(templates, "tasks", "Welche Tasks sind heute wichtig?")
    if has_dashboard_permission(user, "tasks", "view") and has_dashboard_permission(
        user, "tasks", "write"
    ):
        add_template(templates, "tasks", "Task erstellen: Maschine 3 macht Geräusche")
    if has_dashboard_permission(user, "errors", "view"):
        add_template(templates, "errors", "Was bedeutet Fehler E104?")
    if has_dashboard_permission(user, "errors", "view") and has_dashboard_permission(
        user, "errors", "write"
    ):
        add_template(templates, "errors", "Fehleranalyse: Sensor meldet kein Signal")
    if has_dashboard_permission(user, "machines", "view"):
        add_template(templates, "machines", "Welche Maschinen brauchen Aufmerksamkeit?")
    if has_dashboard_permission(user, "inventory", "view"):
        add_template(templates, "inventory", "Welche Lagerteile sind kritisch?")
    if has_dashboard_permission(user, "documents", "view"):
        add_template(templates, "documents", "Welche Dokumente sollte ich prüfen?")
    if has_dashboard_permission(user, "shiftplans", "view"):
        add_template(templates, "shiftplans", "Welche Schichten sind heute relevant?")
    return {"items": templates[:8], "count": len(templates[:8])}


def add_template(templates, scope, message):
    """Append a chat template when the user can view its scope."""
    templates.append(
        {
            "scope": scope,
            "message": message,
            "label": message,
            "category": scope,
        }
    )


def fallback_chat_templates_for_user(user):
    """Return templates filtered by dashboard permissions without API state."""
    templates = []
    if has_dashboard_permission(user, "tasks", "view"):
        add_template(templates, "tasks", "Welche Tasks sind heute wichtig?")
    if has_dashboard_permission(user, "errors", "view"):
        add_template(templates, "errors", "Was bedeutet Fehler E104?")
    if has_dashboard_permission(user, "machines", "view"):
        add_template(templates, "machines", "Welche Maschinen brauchen Aufmerksamkeit?")
    if has_dashboard_permission(user, "inventory", "view"):
        add_template(templates, "inventory", "Welche Lagerteile sind kritisch?")
    if has_dashboard_permission(user, "documents", "view"):
        add_template(templates, "documents", "Welche Dokumente sollte ich prüfen?")
    return {"items": templates[:6], "count": len(templates[:6])}
