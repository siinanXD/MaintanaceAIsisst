"""Rule-based technical entity extraction for knowledge chunks."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from flask import has_app_context
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

TECHNICAL_ENTITY_KEYS = (
    "machines",
    "error_codes",
    "sensors",
    "components",
    "inventory_parts",
    "areas",
    "maintenance_terms",
    "technical_keywords",
)
MAX_ENTITY_VALUES = 24

ERROR_CODE_CONTEXT_PATTERN = re.compile(
    r"\b(?:fehler(?:code)?|error|code|stoerung|st\u00f6rung)\s*[:#-]?\s*"
    r"([A-Z]{1,8}[-_]?\d{1,6}(?:[-_][A-Z0-9]{1,8})?)\b",
    re.IGNORECASE,
)
GENERIC_ERROR_CODE_PATTERN = re.compile(
    r"\b[A-Z]{1,4}[-_]?\d{2,5}(?:[-_][A-Z0-9]{1,8})?\b",
)
MACHINE_REFERENCE_PATTERN = re.compile(
    r"\b(?:maschine|anlage|presse|linie|station|roboter|ofen)\s+"
    r"[A-Z0-9][A-Za-z0-9_-]{0,40}\b",
    re.IGNORECASE,
)
SENSOR_REFERENCE_PATTERN = re.compile(
    r"\b(?:sensor|geber|fuehler|f\u00fchler)\s+[A-Z]?\d{1,4}\b",
    re.IGNORECASE,
)
SENSOR_WORD_PATTERN = re.compile(
    r"\b[A-Za-z0-9_-]*(?:sensor|geber|schranke|initiator)[A-Za-z0-9_-]*\b",
    re.IGNORECASE,
)
INVENTORY_PART_PATTERN = re.compile(
    r"\b(?:[A-Za-z0-9-]+\s+){0,2}"
    r"(?:filter|dichtung|lager|ventil|pumpe|riemen|motor|zylinder|kupplung)"
    r"[A-Za-z0-9-]*(?:\s+[A-Z0-9-]{2,})?\b",
    re.IGNORECASE,
)
TECHNICAL_KEYWORD_PATTERN = re.compile(
    r"\b(?=[A-Z0-9_-]*[A-Z])(?=[A-Z0-9_-]*\d)[A-Z0-9][A-Z0-9_-]{2,}\b",
)

STATIC_ENTITY_TERMS = {
    "sensors": (
        "sensor",
        "drucksensor",
        "temperatursensor",
        "lichtschranke",
        "naeherungsschalter",
        "n\u00e4herungsschalter",
        "encoder",
        "initiator",
        "geber",
        "fuehler",
        "f\u00fchler",
        "endlagenschalter",
        "durchflusssensor",
        "fuellstandsensor",
        "f\u00fcllstandsensor",
    ),
    "components": (
        "hydraulik",
        "pneumatik",
        "pumpe",
        "ventil",
        "filter",
        "lager",
        "motor",
        "getriebe",
        "riemen",
        "dichtung",
        "zylinder",
        "schalter",
        "aktor",
        "servo",
        "steuerung",
        "plc",
        "sps",
        "kupplung",
        "bremse",
        "antrieb",
        "foerderband",
        "f\u00f6rderband",
    ),
    "inventory_parts": (
        "ersatzteil",
        "lagerteil",
        "verschleissteil",
        "verschlei\u00dfteil",
        "verbrauchsmaterial",
        "hydraulikfilter",
        "dichtungssatz",
        "keilriemen",
        "sensor",
        "ventil",
        "pumpe",
    ),
    "areas": (
        "produktion",
        "instandhaltung",
        "wartung",
        "montage",
        "fertigung",
        "verpackung",
        "logistik",
        "versand",
        "linie",
        "bereich",
        "halle",
    ),
    "maintenance_terms": (
        "wartung",
        "inspektion",
        "pruefung",
        "pr\u00fcfung",
        "pruefen",
        "pr\u00fcfen",
        "reinigen",
        "schmieren",
        "kalibrieren",
        "tauschen",
        "wechseln",
        "reparieren",
        "fehleranalyse",
        "stoerung",
        "st\u00f6rung",
        "stillstand",
        "abschmieren",
        "justieren",
    ),
}


@dataclass(frozen=True)
class TechnicalEntityCatalog:
    """Known technical values loaded from existing application tables."""

    machines: tuple[str, ...] = ()
    error_codes: tuple[str, ...] = ()
    inventory_parts: tuple[str, ...] = ()
    areas: tuple[str, ...] = ()
    manufacturers: tuple[str, ...] = ()
    produced_items: tuple[str, ...] = ()


def extract_technical_entities(text, metadata=None, catalog=None):
    """Return technical entities detected in text and optional source metadata."""
    catalog = catalog or load_technical_entity_catalog()
    combined_text = _combined_entity_text(text, metadata)
    entities = _empty_entity_sets()

    _add_catalog_entities(entities, combined_text, catalog)
    _add_metadata_entities(entities, metadata)
    _add_error_codes(entities, combined_text, catalog)
    _add_regex_entities(entities, combined_text)
    _add_static_terms(entities, combined_text)
    _add_technical_keywords(entities, combined_text, catalog)
    return _sorted_entity_payload(entities)


def load_technical_entity_catalog(limit=500):
    """Load known machine, material, area, and error values from the database."""
    if not has_app_context():
        return TechnicalEntityCatalog()

    try:
        from app.models import Department, ErrorEntry, InventoryMaterial, Machine

        machines = Machine.query.with_entities(Machine.name, Machine.produced_item).limit(
            limit,
        )
        materials = InventoryMaterial.query.with_entities(
            InventoryMaterial.name,
            InventoryMaterial.manufacturer,
        ).limit(limit)
        areas = Department.query.with_entities(Department.name).limit(limit)
        errors = ErrorEntry.query.with_entities(
            ErrorEntry.error_code,
            ErrorEntry.machine,
        ).limit(limit)
        machine_rows = list(machines)
        material_rows = list(materials)
        error_rows = list(errors)
        return TechnicalEntityCatalog(
            machines=_unique_tuple(
                [row[0] for row in machine_rows] + [row[1] for row in error_rows],
            ),
            produced_items=_unique_tuple(row[1] for row in machine_rows),
            inventory_parts=_unique_tuple(row[0] for row in material_rows),
            manufacturers=_unique_tuple(row[1] for row in material_rows),
            areas=_unique_tuple(row[0] for row in areas),
            error_codes=_unique_tuple(row[0] for row in error_rows),
        )
    except SQLAlchemyError as exc:
        logger.warning("technical_entity_catalog_load_failed error=%s", exc)
        return TechnicalEntityCatalog()


def normalize_entity_payload(payload):
    """Return a stable entity dictionary with all supported entity keys."""
    entities = {key: [] for key in TECHNICAL_ENTITY_KEYS}
    if not isinstance(payload, dict):
        return entities

    for key in TECHNICAL_ENTITY_KEYS:
        values = payload.get(key, [])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list | tuple | set):
            continue
        entities[key] = _sorted_values(values)
    return entities


def entities_to_json(entities):
    """Serialize a technical entity payload for KnowledgeChunk storage."""
    return json.dumps(
        normalize_entity_payload(entities),
        ensure_ascii=True,
        sort_keys=True,
    )


def entities_from_json(raw_value):
    """Deserialize a technical entity payload from stored JSON."""
    try:
        payload = json.loads(raw_value or "{}")
    except (TypeError, json.JSONDecodeError):
        payload = {}
    return normalize_entity_payload(payload)


def entity_token_text(entities):
    """Return normalized entity values as a compact token string."""
    payload = normalize_entity_payload(entities)
    values = []
    for key in TECHNICAL_ENTITY_KEYS:
        values.extend(payload[key])
    return " ".join(_sorted_values(values))


def _combined_entity_text(text, metadata):
    """Return text plus metadata values as one searchable extraction input."""
    parts = [str(text or "")]
    for value in _metadata_values(metadata):
        parts.append(str(value))
    return "\n".join(part for part in parts if part.strip())


def _metadata_values(metadata):
    """Yield scalar strings from a metadata mapping."""
    if not isinstance(metadata, dict):
        return
    for value in metadata.values():
        if value in (None, ""):
            continue
        if isinstance(value, list | tuple | set):
            for item in value:
                if item not in (None, ""):
                    yield item
            continue
        yield value


def _empty_entity_sets():
    """Return mutable entity sets for internal extraction steps."""
    return {key: set() for key in TECHNICAL_ENTITY_KEYS}


def _add_catalog_entities(entities, text, catalog):
    """Add known database entities that appear in the extraction text."""
    for machine in catalog.machines:
        if _contains_phrase(text, machine):
            entities["machines"].add(machine)
            entities["technical_keywords"].add(machine)
    for code in catalog.error_codes:
        if _contains_phrase(text, code):
            entities["error_codes"].add(_normalize_error_code(code))
            entities["technical_keywords"].add(_normalize_error_code(code))
    for part in catalog.inventory_parts:
        if _contains_phrase(text, part):
            entities["inventory_parts"].add(part)
            entities["technical_keywords"].add(part)
    for area in catalog.areas:
        if _contains_phrase(text, area):
            entities["areas"].add(area)
    for manufacturer in catalog.manufacturers:
        if _contains_phrase(text, manufacturer):
            entities["technical_keywords"].add(manufacturer)
    for produced_item in catalog.produced_items:
        if _contains_phrase(text, produced_item):
            entities["components"].add(produced_item)


def _add_metadata_entities(entities, metadata):
    """Add explicitly supplied source metadata values to matching categories."""
    if not isinstance(metadata, dict):
        return
    aliases = {
        "machines": ("machine", "machine_name", "machines"),
        "error_codes": ("error_code", "error_codes"),
        "inventory_parts": ("inventory_part", "inventory_parts", "material"),
        "areas": ("area", "areas", "department"),
    }
    for target_key, metadata_keys in aliases.items():
        for metadata_key in metadata_keys:
            _add_values(entities[target_key], metadata.get(metadata_key))


def _add_error_codes(entities, text, catalog):
    """Add context-aware and known generic error-code matches."""
    for match in ERROR_CODE_CONTEXT_PATTERN.finditer(text):
        entities["error_codes"].add(_normalize_error_code(match.group(1)))
    known_codes = {_normalize_error_code(code) for code in catalog.error_codes}
    for match in GENERIC_ERROR_CODE_PATTERN.finditer(text):
        code = _normalize_error_code(match.group(0))
        if code in known_codes or _near_error_label(text, match.start()):
            entities["error_codes"].add(code)


def _add_regex_entities(entities, text):
    """Add technical entities detected through lightweight regex rules."""
    for pattern, target_key in (
        (MACHINE_REFERENCE_PATTERN, "machines"),
        (SENSOR_REFERENCE_PATTERN, "sensors"),
        (SENSOR_WORD_PATTERN, "sensors"),
        (INVENTORY_PART_PATTERN, "inventory_parts"),
    ):
        for match in pattern.finditer(text):
            entities[target_key].add(_clean_phrase(match.group(0)))


def _add_static_terms(entities, text):
    """Add known maintenance vocabulary and technical component terms."""
    for target_key, terms in STATIC_ENTITY_TERMS.items():
        for term in terms:
            if _contains_phrase(text, term):
                entities[target_key].add(term)
                if target_key in {"components", "maintenance_terms"}:
                    entities["technical_keywords"].add(term)


def _add_technical_keywords(entities, text, catalog):
    """Add compact technical identifiers and catalog signals as keywords."""
    for match in TECHNICAL_KEYWORD_PATTERN.finditer(text):
        entities["technical_keywords"].add(_clean_phrase(match.group(0)))
    for key in ("machines", "error_codes", "sensors", "components", "inventory_parts"):
        entities["technical_keywords"].update(entities[key])
    for manufacturer in catalog.manufacturers:
        if _contains_phrase(text, manufacturer):
            entities["technical_keywords"].add(manufacturer)


def _near_error_label(text, start_index):
    """Return whether a generic code appears close to an error label."""
    prefix = text[max(0, start_index - 32) : start_index].lower()
    labels = ("fehler", "fehlercode", "error", "code", "stoerung", "st\u00f6rung")
    sensor_labels = ("sensor", "geber", "fuehler", "f\u00fchler")
    last_error_label = max(prefix.rfind(label) for label in labels)
    last_sensor_label = max(prefix.rfind(label) for label in sensor_labels)
    return last_error_label >= 0 and last_error_label > last_sensor_label


def _contains_phrase(text, phrase):
    """Return whether phrase appears as a word-bounded value in text."""
    clean_phrase = _clean_phrase(phrase)
    if not clean_phrase:
        return False
    pattern = r"(?<!\w)" + re.escape(clean_phrase) + r"(?!\w)"
    return re.search(pattern, str(text or ""), re.IGNORECASE) is not None


def _add_values(target, values):
    """Add one or many values to a target set."""
    if values in (None, ""):
        return
    if isinstance(values, list | tuple | set):
        for value in values:
            _add_values(target, value)
        return
    value = _clean_phrase(values)
    if value:
        target.add(value)


def _normalize_error_code(value):
    """Return a normalized uppercase error code."""
    return _clean_phrase(value).upper().replace("_", "-")


def _clean_phrase(value):
    """Return a compact display phrase for one entity value."""
    return re.sub(r"\s+", " ", str(value or "").strip())[:160]


def _sorted_entity_payload(entities):
    """Return sorted and capped entity lists for public storage."""
    return {
        key: _sorted_values(entities.get(key, ()))
        for key in TECHNICAL_ENTITY_KEYS
    }


def _sorted_values(values):
    """Return unique entity values sorted by display-normalized value."""
    clean_values = [_clean_phrase(value) for value in values]
    unique_values = {value for value in clean_values if value}
    return sorted(unique_values, key=lambda item: item.lower())[:MAX_ENTITY_VALUES]


def _unique_tuple(values):
    """Return a stable tuple with empty values removed."""
    return tuple(_sorted_values(values))
