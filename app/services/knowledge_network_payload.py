"""Knowledge network PayloadMixin methods."""

# ruff: noqa: F401, F403, F405

from app.services.knowledge_network_parts import *


class KnowledgeNetworkPayloadMixin:
    """Provide KnowledgeNetworkPayloadMixin behavior for the knowledge network builder."""

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
            edge_node for edge in edges for edge_node in (edge["source"], edge["target"])
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
