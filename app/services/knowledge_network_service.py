"""Build read-only maintenance knowledge network data for admin explainability."""

from __future__ import annotations

from collections import Counter

from app.services.knowledge_network_entities import KnowledgeNetworkEntityMixin
from app.services.knowledge_network_insights import KnowledgeNetworkInsightMixin
from app.services.knowledge_network_parts import _network_filters
from app.services.knowledge_network_payload import KnowledgeNetworkPayloadMixin
from app.services.knowledge_network_sources import KnowledgeNetworkSourceMixin


def knowledge_network(args=None, user=None):
    """Return a bounded read-only knowledge network payload for admins."""
    filters = _network_filters(args or {})
    builder = KnowledgeNetworkBuilder(filters=filters, user=user)
    return builder.build()


class KnowledgeNetworkBuilder(
    KnowledgeNetworkSourceMixin,
    KnowledgeNetworkEntityMixin,
    KnowledgeNetworkInsightMixin,
    KnowledgeNetworkPayloadMixin,
):
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
