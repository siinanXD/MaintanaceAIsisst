"""Knowledge network InsightMixin methods."""

# ruff: noqa: F401, F403, F405

from app.services.knowledge_network_parts import *


class KnowledgeNetworkInsightMixin:
    """Provide KnowledgeNetworkInsightMixin behavior for the knowledge network builder."""

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
