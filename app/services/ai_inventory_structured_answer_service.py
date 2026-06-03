"""Structured AI answers for inventory and material questions."""

from __future__ import annotations

from app.models import InventoryMaterial
from app.security import has_dashboard_permission
from app.services.ai_prompting import permission_denied_answer
from app.services.ai_question_normalizer import normalize_text
from app.services.ai_structured_context_helpers import (
    build_structured_context,
    inherited_structured_scope,
    is_list_follow_up,
)
from app.services.ai_structured_source_service import (
    inventory_source_cards,
    module_count_source_card,
)
from app.services.visibility_query_service import visible_inventory_materials_query

MAX_ITEMS = 20
MAX_ANSWER_ITEMS = 10


def answer_inventory_structured_question(message, user, conversation_context=None):
    """Return a structured inventory answer for supported German questions."""
    text = normalize_text(message)
    if not _is_inventory_question(text) and not _is_inventory_follow_up(text, conversation_context):
        return None
    if not has_dashboard_permission(user, "inventory", "view"):
        return _permission_denied()
    follow_up_result = _answer_inventory_follow_up(message, user, conversation_context)
    if follow_up_result:
        return follow_up_result
    if _is_count_question(text):
        return _answer_inventory_count(user)
    machine = _requested_machine(message, user)
    if machine:
        return _answer_machine_materials(user, machine)
    if _is_low_stock_question(text):
        return _answer_low_stock(user)
    if _is_critical_inventory_question(text):
        return _answer_critical_inventory(user)
    return None


def _answer_inventory_follow_up(message, user, conversation_context):
    """Return a filtered inventory answer for structured follow-up questions."""
    text = normalize_text(message)
    if not _is_inventory_follow_up(text, conversation_context):
        return None

    inherited = inherited_structured_scope(conversation_context)
    query = str(inherited.get("query") or "").strip()
    materials = _materials_for_query(query, user)
    if not materials:
        return None

    machine = _requested_machine(message, user, allow_name_only=True) or str(
        inherited.get("machine") or ""
    ).strip()
    if machine:
        materials = [
            material
            for material in materials
            if normalize_text(machine) in normalize_text(_machine_name(material))
        ]
        title = f"Materialien zu {machine}"
        response_type = "inventory_machine_materials"
        context = build_structured_context(
            "inventory",
            query=query or response_type,
            machine=machine,
        )
    else:
        title = _follow_up_title_for_query(query)
        response_type = query or "inventory_follow_up"
        context = build_structured_context("inventory", query=query or response_type)

    return _inventory_result(response_type, title, materials, context)


def _materials_for_query(query, user):
    """Return visible inventory rows for one structured inventory query."""
    if query == "inventory_low_stock":
        return [
            material
            for material in _visible_materials(user)
            if material.min_quantity > 0 and material.quantity < material.min_quantity
        ]
    if query == "inventory_critical":
        return [
            material
            for material in _visible_materials(user)
            if str(getattr(material, "criticality", "") or "").strip().lower()
            in {"critical", "kritisch", "high", "hoch"}
        ]
    if query == "inventory_machine_materials":
        return _visible_materials(user)
    if query == "inventory_count":
        return _visible_materials(user)
    return []


def _follow_up_title_for_query(query):
    """Return a German title for an inventory follow-up answer."""
    mapping = {
        "inventory_low_stock": "Nachzubestellende Materialien",
        "inventory_critical": "Kritische Materialien",
        "inventory_machine_materials": "Lagerartikel",
        "inventory_count": "Lagerartikel",
    }
    return mapping.get(query, "Lagerartikel")


def _permission_denied():
    """Return a permission-denied inventory answer."""
    return {
        "type": "permission_denied",
        "answer": permission_denied_answer("Lager", "inventory"),
        "data": [],
        "sources": [],
        "scope": "inventory",
        "structured_context": build_structured_context("inventory"),
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
            "query": "inventory_count",
            "count": count,
        },
        "sources": [source] if source else [],
        "scope": "inventory",
        "structured_context": build_structured_context("inventory", query="inventory_count"),
    }


def _answer_machine_materials(user, machine):
    """Return visible inventory materials linked to one machine."""
    materials = [
        material
        for material in _visible_materials(user)
        if normalize_text(machine) in normalize_text(_machine_name(material))
    ][:MAX_ITEMS]
    return _inventory_result(
        "inventory_machine_materials",
        f"Teile zu {machine}",
        materials,
        build_structured_context(
            "inventory",
            query="inventory_machine_materials",
            machine=machine,
        ),
    )


def _answer_low_stock(user):
    """Return visible materials below minimum stock."""
    materials = [
        material
        for material in _visible_materials(user)
        if material.min_quantity > 0 and material.quantity < material.min_quantity
    ][:MAX_ITEMS]
    materials.sort(key=lambda item: (item.quantity - item.min_quantity, item.name))
    return _inventory_result(
        "inventory_low_stock",
        "Nachzubestellende Materialien",
        materials,
        build_structured_context("inventory", query="inventory_low_stock"),
    )


def _answer_critical_inventory(user):
    """Return visible inventory materials flagged as critical or high priority."""
    materials = [
        material
        for material in _visible_materials(user)
        if str(getattr(material, "criticality", "") or "").strip().lower()
        in {"critical", "kritisch", "high", "hoch"}
    ][:MAX_ITEMS]
    materials.sort(
        key=lambda item: (
            0 if str(item.criticality or "").lower() in {"critical", "kritisch"} else 1,
            item.name,
        )
    )
    return _inventory_result(
        "inventory_critical",
        "Kritische Materialien",
        materials,
        build_structured_context("inventory", query="inventory_critical"),
    )


def _inventory_result(response_type, title, materials, structured_context):
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
        "structured_context": structured_context,
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


def _requested_machine(message, user, allow_name_only=False):
    """Return a visible machine name mentioned in the question."""
    text = normalize_text(message)
    if not allow_name_only and not any(term in text for term in ("maschine", "anlage")):
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


def _is_inventory_follow_up(text, conversation_context):
    """Return whether a follow-up should stay on structured inventory data."""
    if not is_list_follow_up(text):
        return False
    inherited = inherited_structured_scope(conversation_context)
    return inherited.get("entity_type") == "inventory"


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


def _is_critical_inventory_question(text):
    """Return whether the text asks for critical inventory materials."""
    inventory_terms = (
        "material",
        "materialien",
        "lager",
        "ersatzteil",
        "teile",
        "artikel",
    )
    return any(term in text for term in ("kritisch", "kritische", "critical")) and any(
        term in text for term in inventory_terms
    )


def _is_count_question(text):
    """Return whether the text asks for inventory count."""
    return any(term in text for term in ("wie viele", "wieviele", "anzahl")) and any(
        term in text for term in ("artikel", "lager", "material")
    )
