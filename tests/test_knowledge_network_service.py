"""Tests for the admin maintenance knowledge network read model."""

from __future__ import annotations

import json
from datetime import UTC, datetime

from app.extensions import db
from app.models import ErrorEntry, KnowledgeChunk, KnowledgeDocument, KnowledgeGap, Role, User
from app.services.knowledge_network_service import knowledge_network
from app.services.technical_entity_service import entities_to_json


def _user_by_id(user_id):
    """Return a user by id inside the active app context."""
    return db.session.get(User, user_id)


def _link_error_to_machine(error_id, machine_id):
    """Attach an error entry to a machine for structured-source tests."""
    entry = db.session.get(ErrorEntry, error_id)
    entry.machine_id = machine_id
    db.session.commit()


def _create_knowledge_document(
    creator_id,
    title,
    source_type="upload",
    source_id=None,
    quality_status="draft",
    entities=None,
    text="Sensitive full chunk text that must stay private.",
):
    """Create an indexed knowledge document with one metadata-rich chunk."""
    document = KnowledgeDocument(
        source_type=source_type,
        source_id=source_id,
        title=title,
        original_filename=f"{title}.txt",
        department="Produktion",
        status="indexed",
        quality_status=quality_status,
        chunk_count=1,
        is_public=True,
        created_by=creator_id,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db.session.add(document)
    db.session.flush()
    chunk = KnowledgeChunk(
        document_id=document.id,
        chunk_index=0,
        text=text,
        token_text="machine error inventory component sensor",
        entities_json=entities_to_json(entities or {}),
    )
    db.session.add(chunk)
    db.session.commit()
    return document.id


def test_knowledge_network_builds_prompt_safe_nodes_and_edges(
    app,
    make_user,
    make_machine,
    make_material,
    make_error_entry,
):
    """Verify documents, structured sources and chunk entities produce safe graph data."""
    admin = make_user(username="network_admin", role=Role.MASTER_ADMIN)
    machine_id = make_machine(name="Presse 7")
    make_material("Hydraulikfilter X900", 42, 8, machine_id=machine_id)
    error_id = make_error_entry(
        "Presse 7",
        "F-900",
        "Hydraulikdruck faellt ab",
        solution="Filter tauschen und Druck pruefen.",
    )

    with app.app_context():
        _link_error_to_machine(error_id, machine_id)
        _create_knowledge_document(
            admin["id"],
            "Hydraulik Fehlerhandbuch",
            source_type="error_entry",
            source_id=error_id,
            quality_status="admin_approved",
            entities={
                "machines": ["Presse 7"],
                "error_codes": ["F-900"],
                "inventory_parts": ["Hydraulikfilter X900"],
                "components": ["Hydraulik"],
                "sensors": ["Drucksensor S12"],
            },
        )

        payload = knowledge_network({}, _user_by_id(admin["id"]))

    node_types = {node["type"] for node in payload["nodes"]}
    edge_types = {edge["type"] for edge in payload["edges"]}
    serialized = json.dumps(payload, sort_keys=True)

    assert {"document", "machine", "error", "solution", "inventory_part"} <= node_types
    assert {"component", "sensor"} <= node_types
    assert {"source_relation", "mentions"} <= edge_types
    assert "Sensitive full chunk text" not in serialized
    assert "chunk_text" in payload["privacy"]["omitted"]


def test_knowledge_network_adds_task_sources_and_focus_groups(
    app,
    make_user,
    make_machine,
    make_material,
    make_error_entry,
    make_task,
):
    """Verify task-backed knowledge participates in focused relationship views."""
    admin = make_user(username="network_task_admin", role=Role.MASTER_ADMIN)
    machine_id = make_machine(name="Anlage T1")
    make_material("Sensor T42", 10, 2, machine_id=machine_id)
    error_id = make_error_entry("Anlage T1", "T-42", "Sensor T42 meldet Drift")
    task_id = make_task(
        "Anlage T1 Fehler T-42 Sensor T42 pruefen",
        creator_username=admin["username"],
        description="Bitte Sensor T42 an Anlage T1 pruefen und Fehler T-42 bewerten.",
    )

    with app.app_context():
        _link_error_to_machine(error_id, machine_id)
        _create_knowledge_document(
            admin["id"],
            "Taskbasierte Sensorpruefung",
            source_type="task",
            source_id=task_id,
            quality_status="technician_confirmed",
            entities={"machines": ["Anlage T1"], "error_codes": ["T-42"]},
        )

        payload = knowledge_network(
            {"focus_type": "task", "limit": "20", "edge_limit": "40"},
            _user_by_id(admin["id"]),
        )

    node_types = {node["type"] for node in payload["nodes"]}
    edge_types = {edge["type"] for edge in payload["edges"]}
    group_types = {group["type"] for group in payload["groups"]}

    assert {"document", "task", "machine", "error"} <= node_types
    assert {"source_relation", "task_context"} <= edge_types
    assert "task" in group_types
    assert payload["stats"]["focus_type"] == "task"


def test_knowledge_network_deduplicates_nodes_and_weights_direct_relations(
    app,
    make_user,
    make_machine,
):
    """Verify canonical nodes are de-duplicated and direct edges rank higher."""
    admin = make_user(username="network_weight_admin", role=Role.MASTER_ADMIN, department_name=None)
    machine_id = make_machine(name="Fraese 2")

    with app.app_context():
        _create_knowledge_document(
            admin["id"],
            "Maschinenkarte Fraese 2",
            source_type="machine",
            source_id=machine_id,
            quality_status="admin_approved",
            entities={"machines": ["Fraese 2"]},
        )
        _create_knowledge_document(
            admin["id"],
            "Lose Entitaet Fraese 2",
            source_type="upload",
            source_id=None,
            quality_status="draft",
            entities={"machines": ["Fraese 2"]},
        )
        payload = knowledge_network({}, _user_by_id(admin["id"]))

    machine_nodes = [node for node in payload["nodes"] if node["id"] == f"machine:{machine_id}"]
    direct_edges = [
        edge
        for edge in payload["edges"]
        if edge["target"] == f"machine:{machine_id}" and edge["type"] == "source_relation"
    ]
    mention_edges = [
        edge
        for edge in payload["edges"]
        if edge["target"] == f"machine:{machine_id}" and edge["type"] == "mentions"
    ]

    assert len(machine_nodes) == 1
    assert direct_edges
    assert mention_edges
    assert max(edge["weight"] for edge in direct_edges) > max(
        edge["weight"] for edge in mention_edges
    )


def test_knowledge_network_limits_nodes_and_includes_gaps_and_recurring_issues(
    app,
    make_user,
    make_machine,
    make_error_entry,
):
    """Verify bounded output still surfaces recurring issues and knowledge gaps."""
    admin = make_user(username="network_gap_admin", role=Role.MASTER_ADMIN)
    machine_id = make_machine(name="Linie 3")
    first_error_id = make_error_entry("Linie 3", "V-300", "Vibration hoch")
    second_error_id = make_error_entry("Linie 3", "V-300", "Vibration erneut")

    with app.app_context():
        _link_error_to_machine(first_error_id, machine_id)
        _link_error_to_machine(second_error_id, machine_id)
        gap = KnowledgeGap(
            question="Sensitive raw user question must not be exposed.",
            question_hash="abc123gapnetwork",
            context_text="Sensitive retrieval context must not be exposed.",
            machine="Linie 3",
            department="Produktion",
            status="open",
            occurrence_count=4,
            user_id=admin["id"],
            last_seen_at=datetime.now(UTC),
        )
        db.session.add(gap)
        db.session.commit()

        payload = knowledge_network(
            {"limit": "4", "edge_limit": "6"},
            _user_by_id(admin["id"]),
        )

    node_types = {node["type"] for node in payload["nodes"]}
    node_ids = {node["id"] for node in payload["nodes"]}
    serialized = json.dumps(payload, sort_keys=True)

    assert len(payload["nodes"]) <= 4
    assert all(
        edge["source"] in node_ids and edge["target"] in node_ids for edge in payload["edges"]
    )
    assert "recurring_issue" in node_types
    assert "knowledge_gap" in node_types
    assert "Sensitive raw user question" not in serialized
    assert "Sensitive retrieval context" not in serialized


def test_admin_knowledge_network_endpoint_is_master_admin_only_and_prompt_safe(
    app,
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify the API endpoint is admin-only and omits full chunk text."""
    admin = make_user(username="network_api_admin", role=Role.MASTER_ADMIN, department_name=None)
    user = make_user(username="network_api_user", role=Role.PRODUKTION)
    machine_id = make_machine(name="Roboter 4")

    with app.app_context():
        _create_knowledge_document(
            admin["id"],
            "Roboter Handbuch",
            source_type="machine",
            source_id=machine_id,
            quality_status="technician_confirmed",
            entities={"machines": ["Roboter 4"]},
            text="Private chunk text for network API.",
        )

    forbidden_response = client.get(
        "/api/v1/admin/ai/knowledge-network",
        headers=auth_headers(user["username"]),
    )
    response = client.get(
        "/api/v1/admin/ai/knowledge-network?limit=20",
        headers=auth_headers(admin["username"]),
    )
    payload = response.get_json()["data"]
    serialized = json.dumps(payload, sort_keys=True)

    assert forbidden_response.status_code == 403
    assert response.status_code == 200
    assert payload["nodes"]
    assert payload["privacy"]["mode"] == "metadata_only"
    assert "Private chunk text" not in serialized
