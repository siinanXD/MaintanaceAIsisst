"""Structured AI answers for inventory and material questions."""

from __future__ import annotations

from app.models import InventoryMaterial
from app.security import has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import normalize_text
from app.services.ai_structured_source_service import (
    inventory_source_cards,
    module_count_source_card,
)
from app.services.visibility_query_service import visible_inventory_materials_query

MAX_ITEMS = 20
MAX_ANSWER_ITEMS = 10


def answer_inventory_structured_question(message, user):
    """Return a structured inventory answer for supported German questions."""
    text = normalize_text(message)
    if not _is_inventory_question(text):
        return None
    if not has_dashboard_permission(user, "inventory", "view"):
        return _permission_denied()
    if _is_count_question(text):
        return _answer_inventory_count(user)
    machine = _requested_machine(message, user)
    if machine:
        return _answer_machine_materials(user, machine)
    if _is_low_stock_question(text):
        return _answer_low_stock(user)
    return None


def _permission_denied():
    """Return a permission-denied inventory answer."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer("Lager", "inventory"),
        "data": [],
        "sources": [],
        "scope": "inventory",
        "structured_context": {"entity_type": "inventory"},
    }


def _answer_inventory_count(user):
    """Return the visible inventory material count."""
    count = visible_inventory_materials_query(user).count()
    source = module_count_source_card("inventory", count, user)
    return {
        "type": "inventory_count",
        "answer": (
            "## Lager\n"
            f"- **Sichtbare Artikel:** {count}\n"
            "- **Quelle:** Strukturierte Lagerdaten"
        ),
        "data": {
            "entity_type": "inventory",
            "query": "count",
            "count": count,
        },
        "sources": [source] if source else [],
        "scope": "inventory",
        "structured_context": {"entity_type": "inventory"},
    }


def _answer_machine_materials(user, machine):
    """Return visible inventory materials linked to one machine."""
    materials = [
        material
        for material in _visible_materials(user)
        if normalize_text(machine) in normalize_text(_machine_name(material))
    ][:MAX_ITEMS]
    return _inventory_result("inventory_machine_materials", f"Teile zu {machine}", materials)


def _answer_low_stock(user):
    """Return visible materials below minimum stock."""
    materials = [
        material
        for material in _visible_materials(user)
        if material.min_quantity > 0 and material.quantity < material.min_quantity
    ][:MAX_ITEMS]
    materials.sort(key=lambda item: (item.quantity - item.min_quantity, item.name))
    return _inventory_result("inventory_low_stock", "Nachzubestellende Materialien", materials)


def _inventory_result(response_type, title, materials):
    """Return a structured inventory result."""
    return {
        "type": response_type,
        "answer": _format_inventory_answer(title, materials),
        "data": {
            "entity_type": "inventory",
            "query": response_type,
            "count": len(materials),
            "items": [_material_payload(material) for material in materials],
        },
        "sources": inventory_source_cards(materials),
        "scope": "inventory",
        "structured_context": {"entity_type": "inventory"},
    }


def _visible_materials(user):
    """Return visible inventory rows ordered for structured answers."""
    return (
        visible_inventory_materials_query(user)
        .order_by(InventoryMaterial.quantity.asc(), InventoryMaterial.name.asc())
        .limit(MAX_ITEMS)
        .all()
    )


def _material_payload(material):
    """Return safe inventory material data for structured answers."""
    return {
        "id": material.id,
        "name": material.name,
        "quantity": material.quantity,
        "min_quantity": material.min_quantity,
        "criticality": material.criticality,
        "lead_time_days": material.lead_time_days,
        "manufacturer": material.manufacturer,
        "machine_id": material.machine_id,
        "machine": _machine_name(material),
        "is_below_minimum": material.min_quantity > 0 and material.quantity < material.min_quantity,
    }


def _format_inventory_answer(title, materials):
    """Return a compact German inventory answer."""
    lines = [
        f"## {title}",
        f"- **Sichtbare Artikel:** {len(materials)}",
        "- **Quelle:** Strukturierte Lagerdaten",
    ]
    if not materials:
        lines.append("")
        lines.append("Keine sichtbaren Lagerartikel fuer diese Anfrage gefunden.")
        return "\n".join(lines)
    lines.append("")
    lines.append("Sichtbare Artikel:")
    for material in materials[:MAX_ANSWER_ITEMS]:
        machine = f", Maschine {_machine_name(material)}" if _machine_name(material) else ""
        lines.append(
            f"- {material.name}: Bestand {material.quantity}, "
            f"Mindestbestand {material.min_quantity}{machine}"
        )
    if len(materials) > MAX_ANSWER_ITEMS:
        lines.append(f"- ... {len(materials) - MAX_ANSWER_ITEMS} weitere Artikel")
    return "\n".join(lines)


def _requested_machine(message, user):
    """Return a visible machine name mentioned in the question."""
    text = normalize_text(message)
    if not any(term in text for term in ("maschine", "anlage")):
        return ""
    for machine_name in _visible_machine_names(user):
        if machine_name and normalize_text(machine_name) in text:
            return machine_name
    return ""


def _visible_machine_names(user):
    """Return machine names linked to visible inventory materials."""
    return sorted({_machine_name(material) for material in _visible_materials(user) if material})


def _machine_name(material):
    """Return the linked machine name for an inventory material."""
    machine = getattr(material, "machine", None)
    return str(getattr(machine, "name", "") or "")


def _is_inventory_question(text):
    """Return whether the text is a supported inventory question."""
    return _is_low_stock_question(text) or any(
        term in text
        for term in ("lager", "material", "materialien", "ersatzteil", "teile", "artikel")
    )


def _is_low_stock_question(text):
    """Return whether the text asks for low-stock or reorder materials."""
    return any(
        term in text
        for term in (
            "bald aus",
            "mindestbestand",
            "nachbestellt",
            "nachbestellen",
            "unter bestand",
            "unterbestand",
        )
    )


def _is_count_question(text):
    """Return whether the text asks for inventory count."""
    return any(term in text for term in ("wie viele", "wieviele", "anzahl")) and any(
        term in text for term in ("artikel", "lager", "material")
    )
