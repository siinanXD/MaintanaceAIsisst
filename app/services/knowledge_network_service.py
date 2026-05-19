"""Build read-only maintenance knowledge network data for admin explainability."""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import joinedload

from app.extensions import db
from app.models import (
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeDocument,
    KnowledgeGap,
    Machine,
    MachineManual,
    MaintenancePlan,
    Task,
)
from app.services.knowledge_service import can_user_read_knowledge_document, source_url
from app.services.recurring_issue_service import analyze_recurring_issues
from app.services.technical_entity_service import extract_technical_entities

DEFAULT_DAYS = 30
DEFAULT_LIMIT = 120
DEFAULT_EDGE_LIMIT = 240
MAX_DAYS = 365
MAX_LIMIT = 200
MAX_EDGE_LIMIT = 400
MAX_DOCUMENT_SCAN = 300
MAX_GAP_SCAN = 50
MAX_ENTITY_VALUES = 8
MAX_RECURRING_ISSUES = 12

QUALITY_WEIGHTS = {
    "admin_approved": 4.0,
    "technician_confirmed": 3.0,
    "ai_suggested": 2.0,
    "draft": 1.0,
    "outdated": 0.5,
    "rejected": 0.25,
}

TYPE_ORDER = {
    "machine": 1,
    "error": 2,
    "solution": 3,
    "document": 4,
    "task": 5,
    "inventory_part": 6,
    "recurring_issue": 7,
    "knowledge_gap": 8,
    "component": 9,
    "sensor": 10,
}

FOCUS_TYPES = {
    "machine",
    "error",
    "task",
    "document",
    "inventory_part",
    "knowledge_gap",
    "recurring_issue",
}

DIRECT_EDGE_WEIGHT = 8.0
ENTITY_EDGE_WEIGHT = 2.5
QUALITY_EDGE_FACTOR = 0.4


def knowledge_network(args=None, user=None):
    """Return a bounded read-only knowledge network payload for admins."""
    filters = _network_filters(args or {})
    builder = KnowledgeNetworkBuilder(filters=filters, user=user)
    return builder.build()


class KnowledgeNetworkBuilder:
    """Build an in-memory read model from existing knowledge and source tables."""

    def __init__(self, filters, user=None):
        """Initialize the network builder with filters and permission context."""
        self.filters = filters
        self.user = user
        self.nodes = {}
        self.edges = {}
        self.raw_stats = Counter()
        self.machine_by_id = {}
        self.machine_by_name = {}
        self.material_by_id = {}
        self.material_by_name = {}
        self.error_by_id = {}
        self.error_by_code = {}
        self.task_by_id = {}
        self._load_reference_data()

    def build(self):
        """Build and return the final network payload."""
        self._add_knowledge_documents()
        self._add_recurring_issues()
        self._add_knowledge_gaps()
        return self._payload()

    def _load_reference_data(self):
        """Load bounded lookup tables used for entity de-duplication."""
        machines = Machine.query.order_by(Machine.id.desc()).limit(500).all()
        materials = InventoryMaterial.query.order_by(InventoryMaterial.id.desc()).limit(500).all()
        errors = ErrorEntry.query.order_by(ErrorEntry.created_at.desc()).limit(750).all()
        tasks = Task.query.order_by(Task.updated_at.desc(), Task.id.desc()).limit(500).all()

        self.machine_by_id = {machine.id: machine for machine in machines}
        self.machine_by_name = {_name_key(machine.name): machine for machine in machines}
        self.material_by_id = {material.id: material for material in materials}
        self.material_by_name = {_name_key(material.name): material for material in materials}
        self.error_by_id = {entry.id: entry for entry in errors}
        self.task_by_id = {task.id: task for task in tasks}
        self.error_by_code = {}
        for entry in errors:
            code = _code_key(entry.error_code)
            if code and code not in self.error_by_code:
                self.error_by_code[code] = entry

    def _add_knowledge_documents(self):
        """Add document nodes and relations derived from indexed knowledge."""
        documents = self._document_query().all()
        for document in documents:
            if self.user and not can_user_read_knowledge_document(self.user, document):
                continue
            document_node_id = self._add_document_node(document)
            self._add_direct_source_relation(document_node_id, document)
            self._add_chunk_entity_relations(document_node_id, document)

    def _document_query(self):
        """Return a filtered bounded query for candidate knowledge documents."""
        since = datetime.now(UTC) - timedelta(days=self.filters["days"])
        query = (
            KnowledgeDocument.query.options(joinedload(KnowledgeDocument.chunks))
            .filter(KnowledgeDocument.created_at >= since)
            .order_by(KnowledgeDocument.updated_at.desc(), KnowledgeDocument.id.desc())
        )
        query_text = self.filters["q"]
        if query_text:
            pattern = f"%{query_text}%"
            query = query.filter(
                or_(
                    KnowledgeDocument.title.ilike(pattern),
                    KnowledgeDocument.original_filename.ilike(pattern),
                    KnowledgeDocument.department.ilike(pattern),
                ),
            )
        if self.filters["source_type"]:
            query = query.filter(KnowledgeDocument.source_type == self.filters["source_type"])
        if self.filters["quality_status"]:
            query = query.filter(
                KnowledgeDocument.quality_status == self.filters["quality_status"],
            )
        scan_limit = min(MAX_DOCUMENT_SCAN, max(self.filters["limit"] * 2, 50))
        return query.limit(scan_limit)

    def _add_document_node(self, document):
        """Add or update a knowledge document node."""
        quality_weight = _quality_weight(document.quality_status)
        title = _safe_title(document.title or document.original_filename or "Knowledge document")
        metadata = {
            "source_type": document.source_type,
            "source_id": document.source_id,
            "department": document.department,
            "chunk_count": document.chunk_count,
            "quality_status": document.quality_status,
            "status": document.status,
            "updated_at": _iso_or_none(document.updated_at),
        }
        return self._add_node(
            node_id=f"document:{document.id}",
            node_type="document",
            label=title,
            title=title,
            weight=3.0 + quality_weight + min(document.chunk_count or 0, 8) * 0.3,
            source_type=document.source_type,
            source_id=document.source_id,
            url=source_url(document),
            quality_status=document.quality_status,
            status=document.status,
            metadata=metadata,
            signals=["knowledge_document", "permission_checked"],
        )

    def _add_direct_source_relation(self, document_node_id, document):
        """Add strong edges from a document to its structured source."""
        source_type = document.source_type
        source_id = document.source_id
        target_node_id = None
        if source_type == "error_entry" and source_id:
            target_node_id = self._add_error_source(source_id)
        elif source_type == "task" and source_id:
            target_node_id = self._add_task_source(source_id)
        elif source_type == "machine" and source_id:
            target_node_id = self._add_machine_by_id(source_id)
        elif source_type == "inventory_material" and source_id:
            target_node_id = self._add_inventory_by_id(source_id)
        elif source_type == "generated_document" and source_id:
            target_node_id = self._add_generated_document_source(source_id)
        elif source_type == "maintenance_plan" and source_id:
            target_node_id = self._add_maintenance_plan_source(source_id)
        elif source_type == "machine_manual" and source_id:
            target_node_id = self._add_machine_manual_source(source_id)

        if target_node_id:
            self._add_edge(
                document_node_id,
                target_node_id,
                edge_type="source_relation",
                label="direct source",
                weight=DIRECT_EDGE_WEIGHT + _quality_weight(document.quality_status),
                signals=["source_type_source_id", "structured_relation"],
            )

    def _add_error_source(self, error_id):
        """Add an error node and related structured machine or solution nodes."""
        entry = self.error_by_id.get(error_id) or db.session.get(ErrorEntry, error_id)
        if not entry:
            return None

        error_node_id = self._add_error_node(entry)
        machine_node_id = self._machine_node_for_error(entry)
        if machine_node_id:
            self._add_edge(
                error_node_id,
                machine_node_id,
                edge_type="source_relation",
                label="affected machine",
                weight=DIRECT_EDGE_WEIGHT,
                signals=["error_machine_relation"],
            )
        if str(entry.solution or "").strip():
            solution_node_id = self._add_solution_node(entry)
            self._add_edge(
                error_node_id,
                solution_node_id,
                edge_type="source_relation",
                label="documented solution",
                weight=DIRECT_EDGE_WEIGHT - 1.0,
                signals=["documented_solution"],
            )
        return error_node_id

    def _add_task_source(self, task_id):
        """Add a task node and safe inferred relations from task metadata."""
        task = self.task_by_id.get(task_id) or db.session.get(Task, task_id)
        if not task:
            return None
        task_node_id = self._add_task_node(task)
        for target_node_id, edge_label, signals in self._task_relation_nodes(task):
            self._add_edge(
                task_node_id,
                target_node_id,
                edge_type="task_context",
                label=edge_label,
                weight=DIRECT_EDGE_WEIGHT - 0.5,
                signals=signals,
            )
        return task_node_id

    def _add_task_node(self, task):
        """Add a prompt-safe task node."""
        priority = _enum_value(task.priority)
        status = _enum_value(task.status)
        return self._add_node(
            node_id=f"task:{task.id}",
            node_type="task",
            label=_safe_title(task.title, max_length=120),
            title=_safe_title(task.title, max_length=160),
            weight=4.5,
            url="/tasks",
            status=status,
            metadata={
                "task_id": task.id,
                "priority": priority,
                "status": status,
                "due_date": task.due_date.isoformat() if task.due_date else None,
                "department": task.department.name if task.department else None,
                "blocked": bool(task.blocked_reason),
                "reopened_count": task.reopened_count,
            },
            signals=["task_source"],
        )

    def _task_relation_nodes(self, task):
        """Return inferred machine, error and inventory relations for a task."""
        text = " ".join([task.title or "", task.description or ""])
        entities = extract_technical_entities(
            text,
            metadata={
                "source_type": "task",
                "source_id": task.id,
                "department": task.department.name if task.department else None,
            },
        )
        relations = []
        relation_specs = (
            ("machines", "task machine", "task_machine_entity"),
            ("error_codes", "task error code", "task_error_entity"),
            ("inventory_parts", "task inventory", "task_inventory_entity"),
        )
        for entity_key, edge_label, signal in relation_specs:
            for value in entities.get(entity_key, [])[:MAX_ENTITY_VALUES]:
                target_node_id = self._node_for_entity(entity_key, value)
                if target_node_id:
                    relations.append((target_node_id, edge_label, [signal, entity_key]))
        return _dedupe_relations(relations)

    def _add_generated_document_source(self, document_id):
        """Add source relations for a generated maintenance document."""
        generated = db.session.get(GeneratedDocument, document_id)
        if not generated:
            return None
        if generated.machine_id:
            return self._add_machine_by_id(generated.machine_id)
        if generated.machine:
            return self._add_machine_by_name(generated.machine)
        return None

    def _add_maintenance_plan_source(self, plan_id):
        """Add source relations for a recurring maintenance plan."""
        plan = db.session.get(MaintenancePlan, plan_id)
        if not plan or not plan.machine_id:
            return None
        return self._add_machine_by_id(plan.machine_id)

    def _add_machine_manual_source(self, manual_id):
        """Add source relations for a machine manual."""
        manual = db.session.get(MachineManual, manual_id)
        if not manual or not manual.machine_id:
            return None
        return self._add_machine_by_id(manual.machine_id)

    def _add_chunk_entity_relations(self, document_node_id, document):
        """Add weaker entity-overlap edges from a document's chunk metadata."""
        entity_counts = self._document_entity_counts(document)
        for entity_key, values in entity_counts.items():
            for value, count in values.most_common(MAX_ENTITY_VALUES):
                target_node_id = self._node_for_entity(entity_key, value)
                if not target_node_id:
                    continue
                weight = (
                    ENTITY_EDGE_WEIGHT
                    + min(count, 6) * 0.6
                    + _quality_weight(document.quality_status) * QUALITY_EDGE_FACTOR
                )
                self._add_edge(
                    document_node_id,
                    target_node_id,
                    edge_type="mentions",
                    label="entity mention",
                    weight=weight,
                    evidence_count=count,
                    signals=["chunk_entities", entity_key],
                )

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

    def _add_recurring_issues(self):
        """Add recurring issue nodes from visible local trend analysis."""
        if not self.user:
            return
        trends = analyze_recurring_issues(
            self.user,
            days=self.filters["days"],
            min_occurrences=2,
            limit=MAX_RECURRING_ISSUES,
        )
        for index, item in enumerate(trends.get("items", []), start=1):
            issue_node_id = self._add_recurring_issue_node(index, item)
            machine_node_id = self._recurring_machine_node(item)
            error_node_id = self._recurring_error_node(item)
            if machine_node_id:
                self._add_edge(
                    issue_node_id,
                    machine_node_id,
                    edge_type="recurring_pattern",
                    label="recurring machine",
                    weight=DIRECT_EDGE_WEIGHT,
                    signals=["recurring_issue_machine"],
                )
            if error_node_id:
                self._add_edge(
                    issue_node_id,
                    error_node_id,
                    edge_type="recurring_pattern",
                    label="recurring error",
                    weight=DIRECT_EDGE_WEIGHT - 0.5,
                    signals=["recurring_issue_error"],
                )

    def _add_recurring_issue_node(self, index, item):
        """Add a recurring issue node from trend metadata."""
        machine_key = item.get("machine_id") or _slug(item.get("affected_machine") or "unknown")
        code_key = _slug(item.get("error_code") or f"issue-{index}")
        node_id = f"recurring_issue:{machine_key}:{code_key}"
        label = item.get("error_code") or item.get("affected_machine") or f"Trend {index}"
        return self._add_node(
            node_id=node_id,
            node_type="recurring_issue",
            label=_safe_title(label, max_length=120),
            title=_safe_title(f"Wiederkehrend: {label}", max_length=160),
            weight=6.0 + min(item.get("occurrence_count") or 0, 10) * 0.6,
            url="/errors",
            status=item.get("risk_level"),
            metadata={
                "occurrence_count": item.get("occurrence_count"),
                "entry_count": item.get("entry_count"),
                "affected_machine": item.get("affected_machine"),
                "machine_id": item.get("machine_id"),
                "error_code": item.get("error_code"),
                "risk_level": item.get("risk_level"),
                "confidence": item.get("confidence"),
                "period": item.get("period"),
            },
            signals=["recurring_issue_analysis"],
        )

    def _recurring_machine_node(self, item):
        """Return the machine node for recurring issue metadata."""
        if item.get("machine_id"):
            return self._add_machine_by_id(item["machine_id"])
        if item.get("affected_machine"):
            return self._add_machine_by_name(item["affected_machine"])
        return None

    def _recurring_error_node(self, item):
        """Return the error node for recurring issue metadata."""
        if item.get("error_code"):
            return self._add_error_by_code(item["error_code"])
        return None

    def _add_knowledge_gaps(self):
        """Add prompt-safe knowledge gap nodes and known safe relations."""
        since = datetime.now(UTC) - timedelta(days=self.filters["days"])
        query = (
            KnowledgeGap.query.filter(KnowledgeGap.last_seen_at >= since)
            .order_by(KnowledgeGap.occurrence_count.desc(), KnowledgeGap.last_seen_at.desc())
            .limit(MAX_GAP_SCAN)
        )
        focus = _name_key(self.filters["q"] or self.filters["focus"])
        for gap in query.all():
            if focus and not self._gap_matches_focus(gap, focus):
                continue
            gap_node_id = self._add_gap_node(gap)
            if gap.machine:
                machine_node_id = self._add_machine_by_name(gap.machine)
                if machine_node_id:
                    self._add_edge(
                        gap_node_id,
                        machine_node_id,
                        edge_type="knowledge_gap",
                        label="gap machine",
                        weight=DIRECT_EDGE_WEIGHT - 1.0,
                        signals=["gap_machine_reference"],
                    )
            self._add_gap_audit_edges(gap_node_id, gap)

    def _gap_matches_focus(self, gap, focus):
        """Return whether a prompt-safe gap field matches the current focus."""
        values = [
            gap.question_hash,
            gap.machine,
            gap.department,
            gap.status,
        ]
        return any(focus in _name_key(value) for value in values)

    def _add_gap_node(self, gap):
        """Add a knowledge gap node without exposing raw question or context text."""
        hash_prefix = str(gap.question_hash or "")[:10] or str(gap.id)
        label = f"Gap {hash_prefix}"
        return self._add_node(
            node_id=f"knowledge_gap:{gap.id}",
            node_type="knowledge_gap",
            label=label,
            title=label,
            weight=4.0 + min(gap.occurrence_count or 0, 10) * 0.5,
            url="/admin/ai",
            status=gap.status,
            metadata={
                "question_hash": gap.question_hash,
                "machine": gap.machine,
                "department": gap.department,
                "status": gap.status,
                "occurrence_count": gap.occurrence_count,
                "task_id": gap.task_id,
                "audit_event_id": gap.audit_event_id,
                "last_seen_at": _iso_or_none(gap.last_seen_at),
            },
            signals=["knowledge_gap_metadata"],
        )

    def _add_gap_audit_edges(self, gap_node_id, gap):
        """Connect gaps to safe source ids stored in retrieval explainability."""
        if not gap.audit_event:
            return
        explainability = gap.audit_event.retrieval_explainability()
        sources = explainability.get("sources", [])
        if not isinstance(sources, list):
            return
        for source in sources[:8]:
            if not isinstance(source, dict):
                continue
            document_id = source.get("id")
            source_type = source.get("type")
            if source_type != "knowledge" or not document_id:
                continue
            document = db.session.get(KnowledgeDocument, document_id)
            if not document:
                continue
            document_node_id = self._add_document_node(document)
            self._add_edge(
                gap_node_id,
                document_node_id,
                edge_type="knowledge_gap",
                label="retrieval context",
                weight=ENTITY_EDGE_WEIGHT,
                signals=["gap_retrieval_source"],
            )

    def _add_node(
        self,
        node_id,
        node_type,
        label,
        title,
        weight,
        url,
        source_type=None,
        source_id=None,
        status=None,
        quality_status=None,
        metadata=None,
        signals=None,
    ):
        """Add or merge a node and return its stable id."""
        if not node_id or not node_type:
            raise ValueError("node_id and node_type are required")
        if node_id not in self.nodes:
            self.nodes[node_id] = {
                "id": node_id,
                "type": node_type,
                "label": label,
                "title": title,
                "url": url,
                "weight": 0.0,
                "evidence_count": 0,
                "source_type": source_type,
                "source_id": source_id,
                "status": status,
                "quality_status": quality_status,
                "metadata": metadata or {},
                "explainability": {"signals": []},
            }
            self.raw_stats[f"nodes_{node_type}"] += 1

        node = self.nodes[node_id]
        node["weight"] = round(float(node["weight"]) + float(weight or 0), 3)
        node["evidence_count"] += 1
        if status and not node.get("status"):
            node["status"] = status
        if quality_status and not node.get("quality_status"):
            node["quality_status"] = quality_status
        node["explainability"]["signals"] = _merge_unique(
            node["explainability"].get("signals", []),
            signals or [],
        )
        return node_id

    def _add_edge(
        self,
        source,
        target,
        edge_type,
        label,
        weight,
        signals=None,
        evidence_count=1,
    ):
        """Add or merge an explainable edge between two existing nodes."""
        if not source or not target or source == target:
            return None
        edge_id = f"{source}|{target}|{edge_type}"
        if edge_id not in self.edges:
            self.edges[edge_id] = {
                "id": _edge_id(source, target, edge_type),
                "source": source,
                "target": target,
                "type": edge_type,
                "label": label,
                "weight": 0.0,
                "evidence_count": 0,
                "explainability": {"signals": []},
            }
            self.raw_stats[f"edges_{edge_type}"] += 1
        edge = self.edges[edge_id]
        edge["weight"] = round(float(edge["weight"]) + float(weight or 0), 3)
        edge["evidence_count"] += int(evidence_count or 1)
        edge["explainability"]["signals"] = _merge_unique(
            edge["explainability"].get("signals", []),
            signals or [],
        )
        return edge["id"]

    def _payload(self):
        """Return the bounded final payload with stats and privacy notes."""
        nodes = self._rank_nodes()
        node_ids = {node["id"] for node in nodes}
        edges = [
            edge
            for edge in self.edges.values()
            if edge["source"] in node_ids and edge["target"] in node_ids
        ]
        edges.sort(key=lambda edge: (-edge["weight"], edge["type"], edge["id"]))
        edges = edges[: self.filters["edge_limit"]]
        connected_node_ids = {
            edge_node
            for edge in edges
            for edge_node in (edge["source"], edge["target"])
        }
        nodes = [node for node in nodes if node["id"] in connected_node_ids or not edges]
        return {
            "nodes": nodes,
            "edges": edges,
            "groups": self._groups(nodes, edges),
            "stats": self._stats(nodes, edges),
            "filters": dict(self.filters),
            "explainability": {
                "strategy": "runtime_read_model",
                "ranking": (
                    "Direct source relations, repeated entity mentions, recurring "
                    "patterns, knowledge gaps, quality status, and optional focus "
                    "matches increase weight."
                ),
                "edge_weights": {
                    "source_relation": DIRECT_EDGE_WEIGHT,
                    "mentions": ENTITY_EDGE_WEIGHT,
                    "quality_factor": QUALITY_EDGE_FACTOR,
                },
                "quality_weights": QUALITY_WEIGHTS,
                "permission_model": "Knowledge documents are checked with RAG read permissions.",
            },
            "privacy": {
                "mode": "metadata_only",
                "omitted": [
                    "chunk_text",
                    "prompts",
                    "answers",
                    "knowledge_gap_question",
                    "knowledge_gap_context",
                ],
            },
        }

    def _rank_nodes(self):
        """Return sorted and limited nodes with optional focus narrowing."""
        nodes = list(self.nodes.values())
        focused = self._focused_node_ids(nodes)
        if focused:
            focused_neighbors = set(focused)
            for edge in self.edges.values():
                if edge["source"] in focused:
                    focused_neighbors.add(edge["target"])
                if edge["target"] in focused:
                    focused_neighbors.add(edge["source"])
            nodes = [node for node in nodes if node["id"] in focused_neighbors]
            for node in nodes:
                if node["id"] in focused:
                    node["weight"] = round(float(node["weight"]) + 6.0, 3)

        nodes.sort(
            key=lambda node: (
                -float(node.get("weight") or 0),
                TYPE_ORDER.get(node.get("type"), 99),
                str(node.get("label") or "").lower(),
                node.get("id"),
            ),
        )
        return nodes[: self.filters["limit"]]

    def _focused_node_ids(self, nodes):
        """Return node ids selected by focus text or focus type."""
        focused = set()
        focus = _name_key(self.filters["focus"])
        focus_type = self.filters.get("focus_type")
        for node in nodes:
            if focus_type and node.get("type") == focus_type:
                focused.add(node["id"])
            if not focus:
                continue
            if (
                focus in _name_key(node["id"])
                or focus in _name_key(node.get("label"))
                or focus in _name_key(node.get("title"))
                or focus in _name_key(node.get("source_type"))
            ):
                focused.add(node["id"])
        return focused

    def _groups(self, nodes, edges):
        """Return grouped node summaries for the relationship UI."""
        edges_by_node = Counter()
        for edge in edges:
            edges_by_node[edge["source"]] += 1
            edges_by_node[edge["target"]] += 1
        grouped = defaultdict(list)
        for node in nodes:
            grouped[node["type"]].append(node)
        groups = []
        for node_type, items in sorted(
            grouped.items(),
            key=lambda item: TYPE_ORDER.get(item[0], 99),
        ):
            items.sort(key=lambda node: (-float(node.get("weight") or 0), node["label"]))
            groups.append(
                {
                    "type": node_type,
                    "label": _group_label(node_type),
                    "count": len(items),
                    "edge_count": sum(edges_by_node[node["id"]] for node in items),
                    "top_nodes": [
                        {
                            "id": node["id"],
                            "label": node["label"],
                            "weight": node["weight"],
                            "status": node.get("status") or node.get("quality_status"),
                        }
                        for node in items[:5]
                    ],
                },
            )
        return groups

    def _stats(self, nodes, edges):
        """Return compact network statistics for dashboard rendering."""
        by_type = Counter(node["type"] for node in nodes)
        edge_types = Counter(edge["type"] for edge in edges)
        return {
            "node_count": len(nodes),
            "edge_count": len(edges),
            "nodes_by_type": dict(sorted(by_type.items())),
            "edges_by_type": dict(sorted(edge_types.items())),
            "raw_node_count": len(self.nodes),
            "raw_edge_count": len(self.edges),
            "window_days": self.filters["days"],
            "focus_type": self.filters.get("focus_type") or "all",
        }


def _network_filters(args):
    """Return validated network query filters from request args."""
    return {
        "q": _clean_filter(args.get("q")),
        "source_type": _clean_filter(args.get("source_type")),
        "quality_status": _clean_filter(args.get("quality_status")),
        "focus": _clean_filter(args.get("focus")),
        "focus_type": _focus_type(args.get("focus_type")),
        "days": _parse_bounded_int(args.get("days"), DEFAULT_DAYS, 1, MAX_DAYS, "days"),
        "limit": _parse_bounded_int(args.get("limit"), DEFAULT_LIMIT, 1, MAX_LIMIT, "limit"),
        "edge_limit": _parse_bounded_int(
            args.get("edge_limit"),
            DEFAULT_EDGE_LIMIT,
            1,
            MAX_EDGE_LIMIT,
            "edge_limit",
        ),
    }


def _parse_bounded_int(value, default, minimum, maximum, field_name):
    """Parse and validate a bounded integer query value."""
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an integer") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(f"{field_name} must be between {minimum} and {maximum}")
    return parsed


def _clean_filter(value):
    """Return a trimmed query-filter value."""
    return " ".join(str(value or "").strip().split())


def _focus_type(value):
    """Return a validated optional focus node type."""
    cleaned = _clean_filter(value)
    if not cleaned:
        return ""
    if cleaned not in FOCUS_TYPES:
        raise ValueError("focus_type is not supported")
    return cleaned


def _quality_weight(quality_status):
    """Return the ranking weight for a knowledge quality status."""
    return QUALITY_WEIGHTS.get(str(quality_status or "").strip(), 1.0)


def _safe_title(value, max_length=140):
    """Return a single-line prompt-safe label."""
    cleaned = " ".join(str(value or "").strip().split())
    if len(cleaned) <= max_length:
        return cleaned
    return f"{cleaned[: max_length - 3].rstrip()}..."


def _group_label(node_type):
    """Return a human-readable group label for one network node type."""
    labels = {
        "machine": "Maschinen",
        "error": "Fehler",
        "solution": "Loesungen",
        "document": "Dokumente",
        "task": "Tasks",
        "inventory_part": "Inventarteile",
        "recurring_issue": "Wiederkehrende Probleme",
        "knowledge_gap": "Knowledge-Gaps",
        "component": "Komponenten",
        "sensor": "Sensorik",
    }
    return labels.get(node_type, node_type)


def _enum_value(value):
    """Return a stable string for enum-like values."""
    return getattr(value, "value", value)


def _slug(value):
    """Return a stable lowercase id fragment."""
    slug = re.sub(r"[^a-z0-9]+", "-", str(value or "").lower()).strip("-")
    return slug or "unknown"


def _name_key(value):
    """Return a normalized comparison key for names and labels."""
    return " ".join(str(value or "").strip().lower().split())


def _code_key(value):
    """Return a normalized comparison key for error codes."""
    return "".join(character for character in str(value or "").upper() if character.isalnum())


def _edge_id(source, target, edge_type):
    """Return a compact stable edge id."""
    return _slug(f"{source}-{target}-{edge_type}")


def _merge_unique(existing, additions):
    """Return a stable list with unique values preserving order."""
    values = list(existing or [])
    for item in additions or []:
        if item and item not in values:
            values.append(item)
    return values


def _dedupe_relations(relations):
    """Return unique relation tuples while preserving their first explanation."""
    seen = set()
    unique_relations = []
    for target_node_id, edge_label, signals in relations:
        key = (target_node_id, edge_label)
        if key in seen:
            continue
        seen.add(key)
        unique_relations.append((target_node_id, edge_label, signals))
    return unique_relations


def _iso_or_none(value):
    """Return an ISO timestamp or None."""
    return value.isoformat() if value else None
