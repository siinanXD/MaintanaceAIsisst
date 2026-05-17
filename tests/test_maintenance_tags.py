"""Tests for the maintenance tag knowledge library."""

from app.extensions import db
from app.models import AssistantTrainingEntry, KnowledgeDocument, Role, User
from app.services.maintenance_tag_service import (
    MAINTENANCE_TAG_CATEGORIES,
    seed_maintenance_tag_library,
    suggest_tags_for_error_payload,
    suggest_tags_for_knowledge_payload,
    suggest_tags_for_task_payload,
)


def test_tag_suggestions_detect_error_task_and_knowledge_terms():
    """Verify local tag suggestions cover faults, causes, solutions and risk."""
    error_tags = suggest_tags_for_error_payload(
        {
            "machine": "Montagelinie 05",
            "error_code": "E104",
            "title": "Sensor liefert kein Signal",
            "description": "Sensor an der Linie meldet sporadisch kein Signal.",
            "possible_causes": "Kabelbruch oder Sensor verschmutzt.",
            "solution": "Sensor reinigen, Abstand pruefen und Probelauf dokumentieren.",
            "severity": "high",
        }
    )
    task_tags = suggest_tags_for_task_payload(
        {
            "title": "Hydraulikpresse Druckverlust dringend pruefen",
            "description": "Leckage am Schlauch, Oel nachfuellen und Ventil messen.",
            "priority": "urgent",
        }
    )
    knowledge_tags = suggest_tags_for_knowledge_payload(
        {
            "title": "Nothalt Sicherheitskreis",
            "question": "Was tun bei offenem Not-Halt-Kreis?",
            "answer": "Tuerkontakt pruefen, Sicherheitsrelais messen und Freigabe dokumentieren.",
            "keywords": "Sicherheit, Nothalt, Tuerkontakt",
        }
    )

    error_keys = {item["tag"] for item in error_tags["items"]}
    task_keys = {item["tag"] for item in task_tags["items"]}
    knowledge_keys = {item["tag"] for item in knowledge_tags["items"]}

    assert error_tags["provider"] == "local_keywords"
    assert {"sensor_fault", "electrical", "clean", "inspect_measure", "sensorics"} <= error_keys
    assert {"pressure_loss", "hydraulic", "critical_risk"} <= task_keys
    assert {"safety_fault", "safety", "test_document"} <= knowledge_keys


def test_error_task_and_training_routes_return_tag_suggestions(
    client,
    make_user,
    auth_headers,
):
    """Verify existing APIs expose tag suggestions without new routes."""
    admin = make_user(
        username="tag_route_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    technician = make_user(
        username="tag_route_tech",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    admin_headers = auth_headers(admin["username"])
    tech_headers = auth_headers(technician["username"])

    error_response = client.post(
        "/api/v1/errors",
        headers=tech_headers,
        json={
            "machine": "Hydraulikpresse 03",
            "error_code": "E103",
            "title": "Druck faellt ab",
            "description": "Hydraulikdruck faellt wegen Leckage am Schlauch ab.",
            "possible_causes": "Schlauch undicht oder Ventil klemmt.",
            "solution": "Leckage pruefen, Schlauch tauschen und Oel nachfuellen.",
            "department": "Instandhaltung",
            "severity": "high",
        },
    )
    task_response = client.post(
        "/api/v1/tasks",
        headers=tech_headers,
        json={
            "title": "Foerderband Materialstau beseitigen",
            "description": "Bandlauf pruefen und Sensor nachjustieren.",
            "department": "Instandhaltung",
            "priority": "soon",
        },
    )
    training_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Sensorik Fehler E104",
            "question": "Wie wird ein Sensorfehler E104 behoben?",
            "answer": (
                "Sensor reinigen, Kabel messen, Abstand einstellen und "
                "Probelauf dokumentieren."
            ),
            "keywords": "Sensor, Kabel, Probelauf",
            "category": "stoerung",
            "department": "Instandhaltung",
        },
    )

    assert error_response.status_code == 201
    assert task_response.status_code == 201
    assert training_response.status_code == 201
    assert error_response.get_json()["tag_suggestions"]["status"] == "suggested"
    assert task_response.get_json()["tag_suggestions"]["status"] == "suggested"
    assert training_response.get_json()["data"]["tag_suggestions"]["status"] == "suggested"


def test_seed_maintenance_tag_library_is_idempotent(app, make_user):
    """Verify seed data creates taxonomy training entries without overwriting."""
    admin = make_user(
        username="tag_seed_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    with app.app_context():
        user = User.query.filter_by(username=admin["username"]).one()
        first_summary = seed_maintenance_tag_library(created_by=user.id)
        db.session.commit()
        second_summary = seed_maintenance_tag_library(created_by=user.id)
        db.session.commit()
        entries = AssistantTrainingEntry.query.filter_by(category="maintenance_tags").all()
        documents = KnowledgeDocument.query.filter_by(source_type="manual_training").all()

    assert first_summary["created"] == len(MAINTENANCE_TAG_CATEGORIES)
    assert second_summary["created"] == 0
    assert len(entries) == len(MAINTENANCE_TAG_CATEGORIES)
    assert len(documents) == len(MAINTENANCE_TAG_CATEGORIES)
