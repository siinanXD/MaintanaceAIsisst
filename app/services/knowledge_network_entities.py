"""Knowledge network EntityMixin methods."""

# ruff: noqa: F401, F403, F405

from app.services.knowledge_network_parts import *


class KnowledgeNetworkEntityMixin:
    """Provide KnowledgeNetworkEntityMixin behavior for the knowledge network builder."""

    def _document_entity_counts(self, document):
        """Return per-entity counters from chunk metadata without reading text."""
        counters = defaultdict(Counter)
        for chunk in document.chunks:
            entities = chunk.entities()
            for entity_key, values in entities.items():
                if entity_key not in {
                    "machines",
                    "error_codes",
                    "components",
                    "sensors",
                    "inventory_parts",
                }:
                    continue
                for value in values[:MAX_ENTITY_VALUES]:
                    cleaned = _safe_title(value, max_length=120)
                    if cleaned:
                        counters[entity_key][cleaned] += 1
        return counters

    def _node_for_entity(self, entity_key, value):
        """Return a node id for a technical entity value."""
        if entity_key == "machines":
            return self._add_machine_by_name(value)
        if entity_key == "error_codes":
            return self._add_error_by_code(value)
        if entity_key == "inventory_parts":
            return self._add_inventory_by_name(value)
        if entity_key == "components":
            return self._add_literal_entity("component", value)
        if entity_key == "sensors":
            return self._add_literal_entity("sensor", value)
        return None

    def _add_machine_by_id(self, machine_id):
        """Add a machine node by database id."""
        machine = self.machine_by_id.get(machine_id) or db.session.get(Machine, machine_id)
        if not machine:
            return None
        return self._add_machine_node(machine)

    def _add_machine_by_name(self, machine_name):
        """Add a machine node by name, falling back to a stable virtual id."""
        machine = self.machine_by_name.get(_name_key(machine_name))
        if machine:
            return self._add_machine_node(machine)
        label = _safe_title(machine_name, max_length=120)
        if not label:
            return None
        return self._add_node(
            node_id=f"machine-name:{_slug(label)}",
            node_type="machine",
            label=label,
            title=label,
            weight=2.0,
            url="/machines",
            metadata={"matched_by": "entity_name"},
            signals=["entity_machine"],
        )

    def _add_machine_node(self, machine):
        """Add a canonical machine node."""
        return self._add_node(
            node_id=f"machine:{machine.id}",
            node_type="machine",
            label=_safe_title(machine.name, max_length=120),
            title=_safe_title(machine.name, max_length=160),
            weight=5.0,
            url="/machines",
            status=machine.status,
            metadata={
                "machine_id": machine.id,
                "produced_item": machine.produced_item,
                "criticality": machine.criticality,
                "status": machine.status,
                "site_id": machine.site_id,
            },
            signals=["machine_source"],
        )

    def _add_inventory_by_id(self, material_id):
        """Add an inventory part node by database id."""
        material = self.material_by_id.get(material_id) or db.session.get(
            InventoryMaterial,
            material_id,
        )
        if not material:
            return None
        return self._add_inventory_node(material)

    def _add_inventory_by_name(self, material_name):
        """Add an inventory part by name, falling back to a stable virtual id."""
        material = self.material_by_name.get(_name_key(material_name))
        if material:
            return self._add_inventory_node(material)
        label = _safe_title(material_name, max_length=120)
        if not label:
            return None
        return self._add_node(
            node_id=f"inventory-part:{_slug(label)}",
            node_type="inventory_part",
            label=label,
            title=label,
            weight=2.0,
            url="/inventory",
            metadata={"matched_by": "entity_name"},
            signals=["entity_inventory_part"],
        )

    def _add_inventory_node(self, material):
        """Add a canonical inventory part node and optional machine edge."""
        material_node_id = self._add_node(
            node_id=f"inventory_part:{material.id}",
            node_type="inventory_part",
            label=_safe_title(material.name, max_length=120),
            title=_safe_title(material.name, max_length=160),
            weight=4.0,
            url="/inventory",
            status=material.criticality,
            metadata={
                "inventory_id": material.id,
                "quantity": material.quantity,
                "min_quantity": material.min_quantity,
                "criticality": material.criticality,
                "machine_id": material.machine_id,
            },
            signals=["inventory_source"],
        )
        if material.machine_id:
            machine_node_id = self._add_machine_by_id(material.machine_id)
            if machine_node_id:
                self._add_edge(
                    material_node_id,
                    machine_node_id,
                    edge_type="source_relation",
                    label="assigned machine",
                    weight=DIRECT_EDGE_WEIGHT - 1.0,
                    signals=["inventory_machine_relation"],
                )
        return material_node_id

    def _add_error_by_code(self, error_code):
        """Add an error node by code, falling back to a stable virtual id."""
        entry = self.error_by_code.get(_code_key(error_code))
        if entry:
            return self._add_error_node(entry)
        label = _safe_title(error_code, max_length=80)
        if not label:
            return None
        return self._add_node(
            node_id=f"error-code:{_slug(label)}",
            node_type="error",
            label=label,
            title=label,
            weight=2.5,
            url="/errors",
            metadata={"matched_by": "error_code_entity"},
            signals=["entity_error_code"],
        )

    def _add_error_node(self, entry):
        """Add a canonical error node."""
        label = entry.error_code or entry.title or f"Fehler {entry.id}"
        return self._add_node(
            node_id=f"error:{entry.id}",
            node_type="error",
            label=_safe_title(label, max_length=100),
            title=_safe_title(entry.title or label, max_length=160),
            weight=5.0 + min(entry.repeat_count or 0, 6) * 0.5,
            url="/errors",
            status=entry.severity,
            metadata={
                "error_id": entry.id,
                "error_code": entry.error_code,
                "machine": entry.machine,
                "machine_id": entry.machine_id,
                "severity": entry.severity,
                "cause_category": entry.cause_category,
                "repeat_count": entry.repeat_count,
                "last_seen_at": _iso_or_none(entry.last_seen_at),
            },
            signals=["error_source"],
        )

    def _machine_node_for_error(self, entry):
        """Return the best machine node for an error entry."""
        if entry.machine_id:
            return self._add_machine_by_id(entry.machine_id)
        if entry.machine:
            return self._add_machine_by_name(entry.machine)
        return None

    def _add_solution_node(self, entry):
        """Add a prompt-safe solution node for a documented error solution."""
        label = f"Loesung: {entry.error_code or entry.title or entry.id}"
        return self._add_node(
            node_id=f"solution:error:{entry.id}",
            node_type="solution",
            label=_safe_title(label, max_length=120),
            title=_safe_title(label, max_length=160),
            weight=4.0,
            url="/errors",
            metadata={
                "source_error_id": entry.id,
                "error_code": entry.error_code,
                "has_solution": True,
            },
            signals=["documented_solution"],
        )

    def _add_literal_entity(self, node_type, value):
        """Add a non-persisted technical entity node."""
        label = _safe_title(value, max_length=100)
        if not label:
            return None
        return self._add_node(
            node_id=f"{node_type}:{_slug(label)}",
            node_type=node_type,
            label=label,
            title=label,
            weight=1.75,
            url="/admin/ai",
            metadata={"matched_by": "chunk_entity"},
            signals=[f"entity_{node_type}"],
        )
