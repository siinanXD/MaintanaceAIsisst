"""Knowledge network SourceMixin methods."""

# ruff: noqa: F401, F403, F405

from app.services.knowledge_network_parts import *


class KnowledgeNetworkSourceMixin:
    """Provide KnowledgeNetworkSourceMixin behavior for the knowledge network builder."""

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
