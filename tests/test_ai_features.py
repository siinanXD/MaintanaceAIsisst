"""Tests for AI feature endpoints and services."""

import json
from datetime import date, datetime, time, timedelta
from io import BytesIO
from pathlib import Path

import pytest

from app.extensions import db
from app.models import (
    AIAuditEvent,
    AIFeedback,
    AssistantTrainingEntry,
    ChatMessage,
    Department,
    EmployeeMachineQualification,
    ErrorEntry,
    GeneratedDocument,
    InventoryMaterial,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeGap,
    Machine,
    MachineManual,
    MaintenancePlan,
    Priority,
    RetrievalEvaluationRun,
    Role,
    ShiftPlan,
    ShiftPlanCoverageSlot,
    ShiftPlanEntry,
    Task,
    TaskStatus,
    User,
    VacationRequest,
)
from app.services.ai_audit_service import (
    ai_analytics_summary,
    ai_user_usage_metrics,
    create_ai_audit_event,
)
from app.services.ai_confidence_service import calculate_ai_confidence
from app.services.ai_observability_service import (
    _evaluation_quality_actions,
    _observability_recommended_actions,
    ai_observability_dashboard,
)
from app.services.ai_routing import estimate_cost_usd, workflow_profile
from app.services.ai_service import AIServiceError, get_ai_provider
from app.services.conversation_context_service import conversation_context_for_chat
from app.services.document_service import document_path
from app.services.empty_retrieval_response_service import build_empty_retrieval_answer
from app.services.knowledge_service import register_source_document
from app.services.retrieval_telemetry_service import retrieval_quality_analytics
from app.services.vector_sync_status_service import (
    clear_vector_sync_observability,
    record_vector_sync_failure,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_TASK_SOURCE_FIELDS = {
    "blocked_reason",
    "completed_by_user",
    "creator",
    "current_worker",
    "description",
}
FORBIDDEN_INCIDENT_SOURCE_FIELDS = {
    "description",
    "downtime_minutes",
    "impact",
    "possible_causes",
    "production_loss_minutes",
    "solution",
    "symptoms",
}
AGGREGATE_SOURCE_FIELDS = {
    "count",
    "created_at",
    "id",
    "module",
    "role_visibility",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "title",
    "type",
    "url",
}
MACHINE_SOURCE_FIELDS = {
    "created_at",
    "criticality",
    "id",
    "last_downtime_at",
    "machine",
    "machine_id",
    "module",
    "produced_item",
    "role_visibility",
    "site_id",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "status",
    "title",
    "type",
    "url",
}
VACATION_SOURCE_FIELDS = {
    "created_at",
    "days_used",
    "department",
    "employee_id",
    "employee_name",
    "end_date",
    "id",
    "module",
    "role_visibility",
    "shift_type",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "start_date",
    "status",
    "title",
    "type",
    "url",
}
EMPLOYEE_SOURCE_FIELDS = {
    "created_at",
    "department",
    "employee_access_level",
    "id",
    "module",
    "role_visibility",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "title",
    "type",
    "url",
}
DOCUMENT_SOURCE_FIELDS = {
    "created_at",
    "department",
    "document_type",
    "id",
    "machine",
    "machine_id",
    "module",
    "quality_status",
    "role_visibility",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "status",
    "title",
    "type",
    "updated_at",
    "url",
}
MANUAL_SOURCE_FIELDS = {
    "created_at",
    "department",
    "document_type",
    "id",
    "machine",
    "machine_id",
    "module",
    "role_visibility",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "title",
    "type",
    "updated_at",
    "url",
}
SHIFTPLAN_ENTRY_SOURCE_FIELDS = {
    "created_at",
    "department",
    "employee_id",
    "employee_name",
    "end_time",
    "id",
    "machine",
    "machine_id",
    "module",
    "plan_id",
    "role_visibility",
    "shift",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "start_time",
    "title",
    "type",
    "url",
    "work_date",
}
SHIFTPLAN_COVERAGE_SOURCE_FIELDS = {
    "assigned",
    "created_at",
    "department",
    "id",
    "machine",
    "machine_id",
    "missing",
    "module",
    "plan_id",
    "required",
    "role_visibility",
    "shift",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "title",
    "type",
    "url",
    "work_date",
}
INVENTORY_SOURCE_FIELDS = {
    "created_at",
    "criticality",
    "id",
    "lead_time_days",
    "machine",
    "machine_id",
    "manufacturer",
    "min_quantity",
    "module",
    "name",
    "quantity",
    "role_visibility",
    "source_id",
    "source_kind",
    "source_record_id",
    "source_type",
    "title",
    "type",
    "url",
}
FORBIDDEN_INVENTORY_SOURCE_FIELDS = {
    "site",
    "total_value",
    "unit_cost",
}
FORBIDDEN_SHIFTPLAN_SOURCE_FIELDS = {
    "notes",
    "preferences",
    "reason",
    "suggestion",
}
FORBIDDEN_DOCUMENT_SOURCE_FIELDS = {
    "analysis",
    "approval_comment",
    "approved_by",
    "extracted_text",
    "original_filename",
    "relative_path",
    "rejected_by",
    "rejection_comment",
    "summary",
}
FORBIDDEN_EMPLOYEE_SOURCE_FIELDS = {
    "birth_date",
    "city",
    "current_shift",
    "documents",
    "favorite_machine",
    "last_shift",
    "machine_qualifications",
    "next_shift",
    "postal_code",
    "qualifications",
    "salary_group",
    "shift_model",
    "street",
}
FORBIDDEN_VACATION_SOURCE_FIELDS = {
    "approved_by",
    "cancelled_by",
    "impact_summary",
    "notes",
    "reason",
    "representative",
    "representative_employee_id",
    "requested_by",
}


def _assert_no_forbidden_source_fields(source, forbidden_fields):
    """Verify a source card does not expose fields reserved for data payloads."""
    for field in forbidden_fields:
        assert field not in source


def _assert_aggregate_count_source(
    source,
    module,
    url,
    count,
    extra_fields=frozenset(),
):
    """Verify one compact aggregate source card for a module count answer."""
    assert set(source) == AGGREGATE_SOURCE_FIELDS | set(extra_fields)
    assert source["type"] == "aggregate"
    assert source["id"] is None
    assert source["module"] == module
    assert source["url"] == url
    assert source["source_type"] == "module_count"
    assert source["source_id"] is None
    assert source["source_record_id"] is None
    assert source["source_kind"] == "structured_aggregate"
    assert source["created_at"]
    assert source["count"] == count


def _assert_machine_source(source, machine_id, machine_name):
    """Verify one compact safe machine source card."""
    assert set(source) == MACHINE_SOURCE_FIELDS
    assert source["type"] == "machine"
    assert source["id"] == machine_id
    assert source["title"] == machine_name
    assert source["module"] == "machines"
    assert source["url"] == "/machines"
    assert source["source_type"] == "machine"
    assert source["source_id"] == machine_id
    assert source["source_record_id"] == machine_id
    assert source["source_kind"] == "structured"
    assert source["machine_id"] == machine_id
    assert source["machine"] == machine_name
    assert source["role_visibility"] == "public"
    assert source["created_at"]


def _assert_vacation_source(source, employee_id, employee_name):
    """Verify one compact safe vacation source card."""
    assert set(source) == VACATION_SOURCE_FIELDS
    assert source["type"] == "vacation_request"
    assert source["module"] == "vacations"
    assert source["url"] == "/vacations"
    assert source["source_type"] == "vacation_request"
    assert source["source_id"] == source["id"]
    assert source["source_record_id"] == source["id"]
    assert source["source_kind"] == "structured"
    assert source["employee_id"] == employee_id
    assert source["employee_name"] == employee_name
    assert source["created_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_VACATION_SOURCE_FIELDS)


def _assert_employee_source(source, employee_id, employee_name):
    """Verify one compact safe employee source card."""
    assert set(source) == EMPLOYEE_SOURCE_FIELDS
    assert source["type"] == "employee"
    assert source["module"] == "employees"
    assert source["url"] == "/employees"
    assert source["source_type"] == "employee"
    assert source["source_id"] == employee_id
    assert source["source_record_id"] == employee_id
    assert source["source_kind"] == "structured"
    assert source["title"] == employee_name
    assert source["created_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_EMPLOYEE_SOURCE_FIELDS)


def _assert_document_source(source, document_id, title):
    """Verify one compact safe generated-document source card."""
    assert set(source) == DOCUMENT_SOURCE_FIELDS
    assert source["type"] == "document"
    assert source["id"] == document_id
    assert source["title"] == title
    assert source["module"] == "documents"
    assert source["url"] == "/documents"
    assert source["source_type"] == "generated_document"
    assert source["source_id"] == document_id
    assert source["source_record_id"] == document_id
    assert source["source_kind"] == "structured"
    assert source["created_at"]
    assert source["updated_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_DOCUMENT_SOURCE_FIELDS)


def _assert_manual_source(source, manual_id, title):
    """Verify one compact safe machine-manual source card."""
    assert set(source) == MANUAL_SOURCE_FIELDS
    assert source["type"] == "machine_manual"
    assert source["id"] == manual_id
    assert source["title"] == title
    assert source["module"] == "documents"
    assert source["url"] == "/documents"
    assert source["source_type"] == "machine_manual"
    assert source["source_id"] == manual_id
    assert source["source_record_id"] == manual_id
    assert source["source_kind"] == "structured"
    assert source["created_at"]
    assert source["updated_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_DOCUMENT_SOURCE_FIELDS)


def _assert_shiftplan_entry_source(source, entry_id, employee_name):
    """Verify one compact safe shift-plan entry source card."""
    assert set(source) == SHIFTPLAN_ENTRY_SOURCE_FIELDS
    assert source["type"] == "shiftplan_entry"
    assert source["id"] == entry_id
    assert source["module"] == "shiftplans"
    assert source["url"] == "/shiftplans"
    assert source["source_type"] == "shiftplan_entry"
    assert source["source_id"] == entry_id
    assert source["source_record_id"] == entry_id
    assert source["source_kind"] == "structured"
    assert source["employee_name"] == employee_name
    assert source["created_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_SHIFTPLAN_SOURCE_FIELDS)


def _assert_shiftplan_coverage_source(source, slot_id):
    """Verify one compact safe shift-plan coverage source card."""
    assert set(source) == SHIFTPLAN_COVERAGE_SOURCE_FIELDS
    assert source["type"] == "shiftplan_coverage"
    assert source["id"] == slot_id
    assert source["module"] == "shiftplans"
    assert source["url"] == "/shiftplans"
    assert source["source_type"] == "shiftplan_coverage"
    assert source["source_id"] == slot_id
    assert source["source_record_id"] == slot_id
    assert source["source_kind"] == "structured"
    assert source["created_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_SHIFTPLAN_SOURCE_FIELDS)


def _assert_inventory_source(source, material_id, name):
    """Verify one compact safe inventory source card."""
    assert set(source) == INVENTORY_SOURCE_FIELDS
    assert source["type"] == "inventory"
    assert source["id"] == material_id
    assert source["title"] == name
    assert source["name"] == name
    assert source["module"] == "inventory"
    assert source["url"] == "/inventory"
    assert source["source_type"] == "inventory"
    assert source["source_id"] == material_id
    assert source["source_record_id"] == material_id
    assert source["source_kind"] == "structured"
    assert source["created_at"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_INVENTORY_SOURCE_FIELDS)


def _create_vacation_request(
    app,
    employee_id,
    start_date,
    end_date,
    status="pending",
    shift_type="",
):
    """Create one vacation request directly for AI feature tests."""
    with app.app_context():
        vacation = VacationRequest(
            employee_id=employee_id,
            start_date=start_date,
            end_date=end_date,
            days_used=max(1, (end_date - start_date).days + 1),
            status=status,
            shift_type=shift_type,
            reason="Interner Grund darf nicht in AI Sources stehen",
            impact_summary="Interne Auswirkungsnotiz darf nicht leaken",
            notes="Interne Notiz darf nicht leaken",
        )
        db.session.add(vacation)
        db.session.commit()
        vacation_id = vacation.id
    return vacation_id


def _create_machine_manual(app, created_by, machine_id, title, department="Produktion"):
    """Create one machine manual directly for AI feature tests."""
    with app.app_context():
        manual = MachineManual(
            machine_id=machine_id,
            department=department,
            title=title,
            original_filename=f"{title}.pdf",
            relative_path=f"manual_{title}.pdf",
            content_type="application/pdf",
            file_size=128,
            analysis="Interne Analyse darf nicht in AI Sources stehen",
            summary="Interne Zusammenfassung darf nicht in AI Sources stehen",
            created_by=created_by,
            created_at=datetime.now(),
            updated_at=datetime.now(),
        )
        db.session.add(manual)
        db.session.commit()
        return manual.id


def _update_generated_document(app, document_id, **values):
    """Update generated document metadata directly for AI feature tests."""
    with app.app_context():
        document = db.session.get(GeneratedDocument, document_id)
        for key, value in values.items():
            setattr(document, key, value)
        db.session.commit()


def _create_shift_plan(app, created_by, department, start_date, status="published"):
    """Create one shift plan directly for AI feature tests."""
    with app.app_context():
        plan = ShiftPlan(
            title=f"Plan {department} {start_date.isoformat()}",
            start_date=start_date,
            days=7,
            rhythm="Test",
            preferences="Interne Praeferenz darf nicht in Sources stehen",
            notes="Interne Notiz darf nicht in Sources stehen",
            department=department,
            status=status,
            created_by=created_by,
        )
        db.session.add(plan)
        db.session.commit()
        return plan.id


def _create_shift_entry(
    app,
    plan_id,
    employee_id,
    work_date,
    shift="Frueh",
    machine_id=None,
):
    """Create one shift plan entry directly for AI feature tests."""
    with app.app_context():
        entry = ShiftPlanEntry(
            plan_id=plan_id,
            employee_id=employee_id,
            machine_id=machine_id,
            work_date=work_date,
            shift=shift,
            start_time="06:00" if shift == "Frueh" else "14:00",
            end_time="14:00" if shift == "Frueh" else "22:00",
            notes="Interne Entry-Notiz darf nicht in Sources stehen",
        )
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id
    return entry_id


def _create_shift_coverage_slot(
    app,
    plan_id,
    work_date,
    shift,
    missing,
    machine_id=None,
):
    """Create one shift plan coverage slot directly for AI feature tests."""
    with app.app_context():
        slot = ShiftPlanCoverageSlot(
            plan_id=plan_id,
            machine_id=machine_id,
            work_date=work_date,
            shift=shift,
            required=3,
            assigned=3 - missing,
            missing=missing,
            reason="Interner Grund darf nicht in Sources stehen",
            suggestion="Interner Vorschlag darf nicht in Sources stehen",
        )
        db.session.add(slot)
        db.session.commit()
        slot_id = slot.id
    return slot_id


def _update_inventory_material(app, material_id, **values):
    """Update inventory material metadata directly for AI feature tests."""
    with app.app_context():
        material = db.session.get(InventoryMaterial, material_id)
        for key, value in values.items():
            setattr(material, key, value)
        db.session.commit()


def _link_user_employee(app, user_data, employee_id):
    """Attach a test user to an employee record."""
    with app.app_context():
        user = db.session.get(User, user_data["id"])
        user.employee_id = employee_id
        db.session.commit()


def _next_week_test_bounds():
    """Return the next calendar week used by vacation AI tests."""
    today = date.today()
    next_monday = today + timedelta(days=7 - today.weekday())
    return next_monday, next_monday + timedelta(days=6)


def test_ai_chat_returns_today_tasks_without_openai(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify the chat endpoint answers today's task questions locally."""
    user = make_user(username="ai_today_user")
    make_task("Task fuer heute", creator_username=user["username"])

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Tasks stehen heute an?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "tasks_today"
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["data"][0]["title"] == "Task fuer heute"


def test_ai_chat_answers_yesterday_closed_tasks_from_structured_data(
    app,
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify yesterday's closed task questions use visible structured tasks."""
    user = make_user(username="ai_yesterday_done_user")
    yesterday = date.today() - timedelta(days=1)
    yesterday_task_id = make_task(
        "Gestern geschlossen sichtbar",
        creator_username=user["username"],
        status=TaskStatus.DONE,
    )
    today_task_id = make_task(
        "Heute geschlossen nicht gestern",
        creator_username=user["username"],
        status=TaskStatus.DONE,
    )
    foreign_task_id = make_task(
        "Gestern geschlossen fremd",
        creator_username=user["username"],
        department_name="IT",
        status=TaskStatus.DONE,
    )
    with app.app_context():
        db.session.get(Task, yesterday_task_id).completed_at = datetime.combine(
            yesterday,
            time(hour=10),
        )
        db.session.get(Task, today_task_id).completed_at = datetime.combine(
            date.today(),
            time(hour=10),
        )
        db.session.get(Task, foreign_task_id).completed_at = datetime.combine(
            yesterday,
            time(hour=11),
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Tasks wurden gestern geschlossen?"},
    )

    payload = response.get_json()
    titles = [item["title"] for item in payload["data"]["items"]]
    assert response.status_code == 200
    assert payload["type"] == "tasks_status"
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["data"]["status"] == TaskStatus.DONE.value
    assert payload["data"]["count"] == 1
    assert titles == ["Gestern geschlossen sichtbar"]
    assert "Heute geschlossen nicht gestern" not in payload["answer"]
    assert "Gestern geschlossen fremd" not in payload["answer"]


def test_ai_chat_task_status_answers_return_safe_source_cards(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify task-status answers expose source cards for visible task rows."""
    user = make_user(username="ai_task_status_source_cards_user")
    visible_id = make_task(
        "Offener sichtbarer Status Task",
        creator_username=user["username"],
        status=TaskStatus.OPEN,
        description="Interne Statusbeschreibung darf nicht in Source Cards stehen",
    )
    make_task(
        "Offener fremder Status Task",
        creator_username=user["username"],
        department_name="IT",
        status=TaskStatus.OPEN,
    )
    make_task(
        "Erledigter sichtbarer Status Task",
        creator_username=user["username"],
        status=TaskStatus.DONE,
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Tasks sind offen?"},
    )

    payload = response.get_json()
    sources = payload["sources"]
    assert response.status_code == 200
    assert payload["type"] == "tasks_status"
    assert payload["data"]["status"] == TaskStatus.OPEN.value
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["id"] == visible_id
    assert len(sources) == 1
    source = sources[0]
    assert source["type"] == "task"
    assert source["id"] == visible_id
    assert source["title"] == "Offener sichtbarer Status Task"
    assert source["module"] == "tasks"
    assert source["url"] == "/tasks"
    assert source["source_type"] == "task"
    assert source["source_id"] == visible_id
    assert source["source_record_id"] == visible_id
    assert source["source_kind"] == "structured"
    assert source["department"] == "Produktion"
    assert source["role_visibility"] == "department:Produktion"
    assert source["created_at"]
    assert source["status"] == TaskStatus.OPEN.value
    assert source["priority"]
    assert source["due_date"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_TASK_SOURCE_FIELDS)
    assert "Offener fremder Status Task" not in json.dumps(payload["data"], ensure_ascii=True)
    assert "Offener fremder Status Task" not in json.dumps(sources, ensure_ascii=True)
    assert payload["diagnostics"]["source_count"] == len(sources)
    assert payload["diagnostics"]["source_count"] > 0
    assert payload["answer_quality"]["source_count"] == len(sources)


def test_ai_chat_counts_done_tasks_from_structured_data(
    app,
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify done-task count questions do not use generic module counts."""
    user = make_user(username="ai_done_count_user")
    done_task_ids = [
        make_task("Done Task A", creator_username=user["username"], status=TaskStatus.DONE),
        make_task("Done Task B", creator_username=user["username"], status=TaskStatus.DONE),
    ]
    make_task("Open Task C", creator_username=user["username"], status=TaskStatus.OPEN)
    with app.app_context():
        for offset, task_id in enumerate(done_task_ids):
            db.session.get(Task, task_id).completed_at = datetime.combine(
                date.today() - timedelta(days=offset),
                time(hour=9),
            )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Tasks wurden beendet?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "tasks_status"
    assert payload["data"]["status"] == TaskStatus.DONE.value
    assert payload["data"]["count"] == 2
    assert "Anzahl:** 2" in payload["answer"]


def test_ai_chat_counts_open_tasks_only_as_task_followup(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify open-count follow-ups require prior task conversation context."""
    user = make_user(username="ai_open_followup_user")
    make_task("Offener Follow-up Task", creator_username=user["username"], status=TaskStatus.OPEN)
    make_task(
        "Erledigter Follow-up Task",
        creator_username=user["username"],
        status=TaskStatus.DONE,
    )
    headers = auth_headers(user["username"])

    first_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Welche Tasks stehen heute an?",
            "session_id": "task-status-followup",
        },
    )
    followup_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Wie viele sind noch offen?",
            "session_id": "task-status-followup",
        },
    )
    fresh_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Wie viele sind noch offen?",
            "session_id": "unrelated-task-status-followup",
        },
    )

    followup_payload = followup_response.get_json()
    assert first_response.status_code == 200
    assert first_response.get_json()["type"] == "tasks_today"
    assert followup_response.status_code == 200
    assert followup_payload["type"] == "structured_scope"
    assert followup_payload["data"]["entity_type"] == "tasks"
    assert followup_payload["data"]["filters"]["status"] == TaskStatus.OPEN.value
    assert followup_payload["data"]["count"] == 1
    assert fresh_response.status_code == 200
    assert fresh_response.get_json()["type"] != "structured_scope"


def test_ai_chat_short_open_followup_after_yesterday_done_uses_task_domain(
    app,
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify a short open-count follow-up keeps task context without stale time filters."""
    user = make_user(username="ai_yesterday_open_followup_user")
    yesterday = date.today() - timedelta(days=1)
    done_task_id = make_task(
        "Gestern abgeschlossen fuer Follow-up",
        creator_username=user["username"],
        status=TaskStatus.DONE,
    )
    open_task_id = make_task(
        "Aktuell offener Follow-up Task",
        creator_username=user["username"],
        status=TaskStatus.OPEN,
    )
    with app.app_context():
        db.session.get(Task, done_task_id).completed_at = datetime.combine(
            yesterday,
            time(hour=9),
        )
        db.session.get(Task, open_task_id).created_at = datetime.combine(
            date.today(),
            time(hour=9),
        )
        db.session.commit()
    headers = auth_headers(user["username"])

    first_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Welche Tasks wurden gestern abgeschlossen?",
            "session_id": "task-yesterday-open-followup",
        },
    )
    followup_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Wie viele sind noch offen?",
            "session_id": "task-yesterday-open-followup",
        },
    )
    fresh_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Wie viele sind noch offen?",
            "session_id": "task-yesterday-open-fresh",
        },
    )

    first_payload = first_response.get_json()
    followup_payload = followup_response.get_json()
    fresh_payload = fresh_response.get_json()
    assert first_response.status_code == 200
    assert first_payload["type"] == "tasks_status"
    assert first_payload["data"]["status"] == TaskStatus.DONE.value
    assert first_payload["data"]["count"] == 1
    assert followup_response.status_code == 200
    assert followup_payload["type"] == "structured_scope"
    assert followup_payload["data"]["entity_type"] == "tasks"
    assert followup_payload["data"]["filters"] == {"status": TaskStatus.OPEN.value}
    assert followup_payload["data"]["count"] == 1
    assert followup_payload["data"]["items"][0]["title"] == "Aktuell offener Follow-up Task"
    assert fresh_response.status_code == 200
    assert fresh_payload["type"] not in {"structured_scope", "tasks_status"}
    assert "Anzahl:**" not in fresh_payload["answer"]


def test_ai_chat_structured_task_answers_return_safe_source_cards(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify structured task answers expose compact safe source cards."""
    user = make_user(username="ai_task_source_cards_user")
    visible_id = make_task(
        "Dringender sichtbarer Task",
        creator_username=user["username"],
        priority=Priority.URGENT,
        description="Interner Task-Text darf nicht in Source Cards stehen",
    )
    make_task(
        "Dringender fremder Task",
        creator_username=user["username"],
        department_name="IT",
        priority=Priority.URGENT,
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche dringenden Tasks gibt es?"},
    )

    payload = response.get_json()
    sources = payload["sources"]
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["id"] == visible_id
    assert len(sources) == 1
    source = sources[0]
    assert source["type"] == "task"
    assert source["id"] == visible_id
    assert source["title"] == "Dringender sichtbarer Task"
    assert source["module"] == "tasks"
    assert source["url"] == "/tasks"
    assert source["source_type"] == "task"
    assert source["source_id"] == visible_id
    assert source["source_record_id"] == visible_id
    assert source["source_kind"] == "structured"
    assert source["department"] == "Produktion"
    assert source["role_visibility"] == "department:Produktion"
    assert source["created_at"]
    assert source["status"] == TaskStatus.OPEN.value
    assert source["priority"] == Priority.URGENT.value
    assert source["due_date"]
    _assert_no_forbidden_source_fields(source, FORBIDDEN_TASK_SOURCE_FIELDS)
    assert "Dringender fremder Task" not in json.dumps(payload["data"], ensure_ascii=True)
    assert "Dringender fremder Task" not in json.dumps(sources, ensure_ascii=True)
    assert payload["diagnostics"]["source_count"] == len(sources)
    assert payload["answer_quality"]["source_count"] == len(sources)
    assert payload["answer_quality"]["has_sources"] is True


def test_ai_chat_structured_followup_inherits_incident_scope(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify incident follow-ups inherit status scope from the prior answer."""
    user = make_user(username="ai_incident_followup_user")
    open_critical_id = make_error_entry(
        "Presse 7",
        "IF-CRIT",
        "Kritische Stoerung",
        department_name="Produktion",
    )
    open_medium_id = make_error_entry(
        "Presse 8",
        "IF-MED",
        "Normale Stoerung",
        department_name="Produktion",
    )
    closed_id = make_error_entry(
        "Presse 9",
        "IF-CLOSED",
        "Geschlossene Stoerung",
        department_name="Produktion",
    )
    foreign_id = make_error_entry(
        "Presse 10",
        "IF-FOREIGN",
        "Fremde Stoerung",
        department_name="IT",
    )
    with app.app_context():
        db.session.get(ErrorEntry, open_critical_id).status = "open"
        db.session.get(ErrorEntry, open_critical_id).severity = "critical"
        db.session.get(ErrorEntry, open_medium_id).status = "open"
        db.session.get(ErrorEntry, open_medium_id).severity = "medium"
        db.session.get(ErrorEntry, closed_id).status = "closed"
        db.session.get(ErrorEntry, closed_id).severity = "critical"
        db.session.get(ErrorEntry, foreign_id).status = "open"
        db.session.get(ErrorEntry, foreign_id).severity = "critical"
        db.session.commit()

    headers = auth_headers(user["username"])
    first_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Welche Störungen sind offen?",
            "session_id": "incident-followup",
        },
    )
    followup_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Und welche sind kritisch?",
            "session_id": "incident-followup",
        },
    )

    first_payload = first_response.get_json()
    followup_payload = followup_response.get_json()
    assert first_response.status_code == 200
    assert first_payload["type"] == "structured_scope"
    assert first_payload["data"]["entity_type"] == "incidents"
    assert first_payload["data"]["count"] == 2
    assert first_payload["data"]["filters"]["status"] == "open"
    assert followup_response.status_code == 200
    assert followup_payload["type"] == "structured_scope"
    assert followup_payload["data"]["entity_type"] == "incidents"
    assert followup_payload["data"]["count"] == 1
    assert followup_payload["data"]["filters"]["status"] == "open"
    assert followup_payload["data"]["filters"]["severity"] == "critical"
    assert followup_payload["data"]["items"][0]["error_code"] == "IF-CRIT"


def test_ai_chat_counts_visible_open_incidents_from_structured_data(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify open incident counts use only visible structured errors."""
    user = make_user(username="ai_open_incident_count_user")
    visible_open_id = make_error_entry(
        "Presse Open",
        "OPEN-1",
        "Offene sichtbare Stoerung",
        department_name="Produktion",
    )
    visible_closed_id = make_error_entry(
        "Presse Closed",
        "OPEN-2",
        "Geschlossene sichtbare Stoerung",
        department_name="Produktion",
    )
    foreign_open_id = make_error_entry(
        "Presse Foreign",
        "OPEN-3",
        "Fremde offene Stoerung",
        department_name="IT",
    )
    with app.app_context():
        db.session.get(ErrorEntry, visible_open_id).status = "open"
        db.session.get(ErrorEntry, visible_closed_id).status = "closed"
        db.session.get(ErrorEntry, foreign_open_id).status = "open"
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Stoerungen sind offen?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["data"]["entity_type"] == "incidents"
    assert payload["data"]["count"] == 1
    assert payload["data"]["filters"]["status"] == "open"
    assert "OPEN-3" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_lists_visible_critical_incidents_from_structured_data(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify critical incident lists use only visible structured errors."""
    user = make_user(username="ai_critical_incident_user")
    critical_id = make_error_entry(
        "Presse Critical",
        "CRIT-1",
        "Kritische sichtbare Stoerung",
        department_name="Produktion",
    )
    medium_id = make_error_entry(
        "Presse Medium",
        "CRIT-2",
        "Normale sichtbare Stoerung",
        department_name="Produktion",
    )
    foreign_id = make_error_entry(
        "Presse Foreign Critical",
        "CRIT-3",
        "Fremde kritische Stoerung",
        department_name="IT",
    )
    with app.app_context():
        db.session.get(ErrorEntry, critical_id).severity = "critical"
        db.session.get(ErrorEntry, medium_id).severity = "medium"
        db.session.get(ErrorEntry, foreign_id).severity = "critical"
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Stoerungen sind kritisch?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["data"]["count"] == 1
    assert payload["data"]["filters"]["severity"] == "critical"
    assert payload["data"]["items"][0]["error_code"] == "CRIT-1"
    assert len(payload["sources"]) == 1
    source = payload["sources"][0]
    assert source["type"] == "error"
    assert source["id"] == critical_id
    assert source["title"] == "CRIT-1 - Kritische sichtbare Stoerung"
    assert source["module"] == "errors"
    assert source["url"] == "/errors"
    assert source["source_type"] == "error"
    assert source["source_id"] == critical_id
    assert source["source_record_id"] == critical_id
    assert source["source_kind"] == "structured"
    assert source["department"] == "Produktion"
    assert source["machine"] == "Presse Critical"
    assert source["machine_id"] is None
    assert source["role_visibility"] == "department:Produktion"
    assert source["created_at"]
    assert source["status"] == "open"
    assert source["severity"] == "critical"
    assert source["error_code"] == "CRIT-1"
    _assert_no_forbidden_source_fields(source, FORBIDDEN_INCIDENT_SOURCE_FIELDS)
    assert "CRIT-3" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_filters_incidents_reported_today_from_structured_data(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify incident questions about today filter created_at from structured data."""
    user = make_user(username="ai_today_incident_user")
    today_id = make_error_entry(
        "Presse Today",
        "TODAY-1",
        "Heute gemeldete Stoerung",
        department_name="Produktion",
    )
    yesterday_id = make_error_entry(
        "Presse Yesterday",
        "TODAY-2",
        "Gestern gemeldete Stoerung",
        department_name="Produktion",
    )
    with app.app_context():
        db.session.get(ErrorEntry, today_id).created_at = datetime.combine(
            date.today(),
            time(hour=8),
        )
        db.session.get(ErrorEntry, yesterday_id).created_at = datetime.combine(
            date.today() - timedelta(days=1),
            time(hour=8),
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Stoerungen wurden heute gemeldet?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["data"]["count"] == 1
    assert payload["data"]["filters"]["time_range"] == "today"
    assert payload["data"]["items"][0]["error_code"] == "TODAY-1"


def test_ai_chat_aggregates_incidents_by_visible_machine(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify incident machine aggregation uses only visible structured errors."""
    user = make_user(username="ai_incident_machine_aggregation_user")
    make_error_entry("Presse Top", "TOP-1", "Top Stoerung A", department_name="Produktion")
    make_error_entry("Presse Top", "TOP-2", "Top Stoerung B", department_name="Produktion")
    make_error_entry("Presse Other", "TOP-3", "Andere Stoerung", department_name="Produktion")
    make_error_entry("Presse Foreign", "TOP-4", "Fremde Stoerung", department_name="IT")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschine hat die meisten Stoerungen?"},
    )

    payload = response.get_json()
    top = payload["data"]["aggregation"]["top"]
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["data"]["entity_type"] == "incidents"
    assert payload["data"]["count"] == 3
    assert top["machine"] == "Presse Top"
    assert top["count"] == 2
    assert {item["error_code"] for item in top["examples"]} == {"TOP-1", "TOP-2"}
    assert {source["error_code"] for source in payload["sources"]} == {"TOP-1", "TOP-2"}
    assert all(source["machine"] == "Presse Top" for source in payload["sources"])
    assert "TOP-3" not in json.dumps(payload["sources"], ensure_ascii=True)
    assert "TOP-4" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_machine_downtime_uses_only_visible_incidents(
    app,
    client,
    make_user,
    make_machine,
    make_error_entry,
    set_dashboard_permission,
    auth_headers,
):
    """Verify machine downtime aggregation sums only visible error downtime."""
    user = make_user(username="ai_machine_downtime_user")
    top_machine_id = make_machine(name="Presse Downtime Top", produced_item="Deckel")
    other_machine_id = make_machine(name="Presse Downtime Other", produced_item="Rahmen")
    top_error_a = make_error_entry(
        "Presse Downtime Top",
        "DOWN-1",
        "Sichtbare Ausfallzeit A",
        department_name="Produktion",
    )
    top_error_b = make_error_entry(
        "Presse Downtime Top",
        "DOWN-2",
        "Sichtbare Ausfallzeit B",
        department_name="Produktion",
    )
    other_error = make_error_entry(
        "Presse Downtime Other",
        "DOWN-3",
        "Andere Ausfallzeit",
        department_name="Produktion",
    )
    foreign_error = make_error_entry(
        "Presse Downtime Other",
        "DOWN-4",
        "Fremde Ausfallzeit",
        department_name="IT",
    )
    set_dashboard_permission(user["username"], "machines", can_view=True)
    set_dashboard_permission(user["username"], "errors", can_view=True)
    with app.app_context():
        db.session.get(ErrorEntry, top_error_a).machine_id = top_machine_id
        db.session.get(ErrorEntry, top_error_a).downtime_minutes = 30
        db.session.get(ErrorEntry, top_error_b).machine_id = top_machine_id
        db.session.get(ErrorEntry, top_error_b).downtime_minutes = 25
        db.session.get(ErrorEntry, other_error).machine_id = other_machine_id
        db.session.get(ErrorEntry, other_error).downtime_minutes = 50
        db.session.get(ErrorEntry, foreign_error).machine_id = other_machine_id
        db.session.get(ErrorEntry, foreign_error).downtime_minutes = 999
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschine verursacht die meiste Ausfallzeit?"},
    )

    payload = response.get_json()
    top = payload["data"]["aggregation"]["top"]
    machine_source = next(source for source in payload["sources"] if source["type"] == "machine")
    incident_sources = [source for source in payload["sources"] if source["type"] == "error"]
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "machine_downtime"
    assert top["machine_id"] == top_machine_id
    assert top["machine"] == "Presse Downtime Top"
    assert top["total_downtime_minutes"] == 55
    assert top["incident_count"] == 2
    _assert_machine_source(machine_source, top_machine_id, "Presse Downtime Top")
    assert {source["error_code"] for source in incident_sources} == {"DOWN-1", "DOWN-2"}
    assert all(source["machine_id"] == top_machine_id for source in incident_sources)
    assert "DOWN-4" not in serialized_payload
    assert payload["diagnostics"]["source_count"] == len(payload["sources"])
    assert payload["answer_quality"]["source_count"] == len(payload["sources"])


def test_ai_chat_lists_visible_machine_incidents_with_safe_sources(
    app,
    client,
    make_user,
    make_machine,
    make_error_entry,
    set_dashboard_permission,
    auth_headers,
):
    """Verify machine incident questions return visible rows and safe sources."""
    user = make_user(username="ai_machine_incident_list_user")
    machine_id = make_machine(name="Presse Liste", produced_item="Deckel")
    other_machine_id = make_machine(name="Presse Andere", produced_item="Rahmen")
    linked_error = make_error_entry(
        "Presse Liste",
        "MLIST-1",
        "Verknuepfte Stoerung",
        department_name="Produktion",
    )
    make_error_entry(
        "Presse Liste",
        "MLIST-2",
        "Text Stoerung",
        department_name="Produktion",
    )
    other_error = make_error_entry(
        "Presse Andere",
        "MLIST-3",
        "Andere Stoerung",
        department_name="Produktion",
    )
    foreign_error = make_error_entry(
        "Presse Liste",
        "MLIST-4",
        "Fremde Stoerung",
        department_name="IT",
    )
    set_dashboard_permission(user["username"], "machines", can_view=True)
    set_dashboard_permission(user["username"], "errors", can_view=True)
    with app.app_context():
        db.session.get(ErrorEntry, linked_error).machine_id = machine_id
        db.session.get(ErrorEntry, other_error).machine_id = other_machine_id
        db.session.get(ErrorEntry, foreign_error).machine_id = machine_id
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Stoerungen gibt es an Maschine Presse Liste?"},
    )

    payload = response.get_json()
    machine_source = next(source for source in payload["sources"] if source["type"] == "machine")
    incident_sources = [source for source in payload["sources"] if source["type"] == "error"]
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "machine_incidents"
    assert payload["data"]["machine"]["id"] == machine_id
    assert payload["data"]["count"] == 2
    assert {item["error_code"] for item in payload["data"]["items"]} == {"MLIST-1", "MLIST-2"}
    _assert_machine_source(machine_source, machine_id, "Presse Liste")
    assert {source["error_code"] for source in incident_sources} == {"MLIST-1", "MLIST-2"}
    for source in incident_sources:
        _assert_no_forbidden_source_fields(source, FORBIDDEN_INCIDENT_SOURCE_FIELDS)
    assert "MLIST-3" not in serialized_payload
    assert "MLIST-4" not in serialized_payload


def test_ai_chat_machine_structured_answer_requires_machine_and_error_permissions(
    client,
    make_user,
    make_machine,
    set_dashboard_permission,
    auth_headers,
):
    """Verify machine incident answers require both machines:view and errors:view."""
    user = make_user(username="ai_machine_permission_denied_user")
    make_machine(name="Presse Permission", produced_item="Deckel")
    set_dashboard_permission(user["username"], "machines", can_view=True)
    set_dashboard_permission(user["username"], "errors", can_view=False)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschine hat die meiste Downtime?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "permission_denied"
    assert payload["sources"] == []


def test_ai_chat_machine_structured_answer_only_redacts_evidence(
    app,
    client,
    make_user,
    make_machine,
    make_error_entry,
    set_dashboard_permission,
    auth_headers,
):
    """Verify answer-only mode redacts structured machine evidence for normal users."""
    user = make_user(username="ai_machine_answer_only_user")
    machine_id = make_machine(name="Presse Redacted", produced_item="Deckel")
    error_id = make_error_entry(
        "Presse Redacted",
        "MRED-1",
        "Redacted Stoerung",
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "machines", can_view=True)
    set_dashboard_permission(user["username"], "errors", can_view=True)
    with app.app_context():
        db.session.get(ErrorEntry, error_id).machine_id = machine_id
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Welche Fehler gibt es an Maschine Presse Redacted?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "machine_incidents"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_vacation_own_pending_only_returns_own_request(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify own pending vacation answers never include other employees."""
    user = make_user(username="ai_vacation_own_pending_user")
    own_employee_id = make_employee(
        personnel_number="P-AI-VAC-OWN-1",
        name="Anna Urlaub Eigen",
        department="Produktion",
    )
    other_employee_id = make_employee(
        personnel_number="P-AI-VAC-OWN-2",
        name="Bernd Urlaub Fremd",
        department="Produktion",
    )
    _link_user_employee(app, user, own_employee_id)
    _create_vacation_request(
        app,
        own_employee_id,
        date.today() + timedelta(days=10),
        date.today() + timedelta(days=12),
        status="pending",
    )
    _create_vacation_request(
        app,
        other_employee_id,
        date.today() + timedelta(days=11),
        date.today() + timedelta(days=11),
        status="pending",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Habe ich Urlaub offen?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "vacation_own_pending"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["employee_id"] == own_employee_id
    assert len(payload["sources"]) == 1
    _assert_vacation_source(payload["sources"][0], own_employee_id, "Anna Urlaub Eigen")
    assert payload["sources"][0]["role_visibility"] == f"employee:{own_employee_id}"
    assert "Bernd Urlaub Fremd" not in serialized_payload
    assert payload["diagnostics"]["source_count"] == 1
    assert payload["answer_quality"]["source_count"] == 1


def test_ai_chat_vacation_own_latest_status_excludes_other_employees(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify own vacation status answers use only the current user's requests."""
    user = make_user(username="ai_vacation_own_status_user")
    own_employee_id = make_employee(
        personnel_number="P-AI-VAC-STATUS-1",
        name="Clara Urlaub Status",
        department="Produktion",
    )
    other_employee_id = make_employee(
        personnel_number="P-AI-VAC-STATUS-2",
        name="Dirk Urlaub Status Fremd",
        department="Produktion",
    )
    _link_user_employee(app, user, own_employee_id)
    _create_vacation_request(
        app,
        own_employee_id,
        date.today() + timedelta(days=20),
        date.today() + timedelta(days=21),
        status="approved",
    )
    _create_vacation_request(
        app,
        other_employee_id,
        date.today() + timedelta(days=22),
        date.today() + timedelta(days=23),
        status="rejected",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welchen Status hat mein Urlaubsantrag?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "vacation_own_status"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["status"] == "approved"
    assert payload["data"]["items"][0]["employee_id"] == own_employee_id
    assert len(payload["sources"]) == 1
    _assert_vacation_source(payload["sources"][0], own_employee_id, "Clara Urlaub Status")
    assert "Dirk Urlaub Status Fremd" not in serialized_payload
    for source in payload["sources"]:
        _assert_no_forbidden_source_fields(source, FORBIDDEN_VACATION_SOURCE_FIELDS)
    for item in payload["data"]["items"]:
        _assert_no_forbidden_source_fields(item, FORBIDDEN_VACATION_SOURCE_FIELDS)


def test_ai_chat_vacation_department_manager_sees_own_department_absences(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify department vacation visibility for tomorrow and next week."""
    manager = make_user(username="ai_vacation_department_manager")
    set_dashboard_permission(
        manager["username"],
        "employees",
        can_view=True,
        can_write=True,
        employee_access_level="basic",
    )
    prod_employee_id = make_employee(
        personnel_number="P-AI-VAC-DEPT-1",
        name="Eva Urlaub Produktion",
        department="Produktion",
    )
    prod_pending_id = make_employee(
        personnel_number="P-AI-VAC-DEPT-2",
        name="Frank Urlaub Pending",
        department="Produktion",
    )
    it_employee_id = make_employee(
        personnel_number="P-AI-VAC-DEPT-3",
        name="Gina Urlaub IT",
        department="IT",
    )
    tomorrow = date.today() + timedelta(days=1)
    next_week_start, _next_week_end = _next_week_test_bounds()
    next_week_day = next_week_start + timedelta(days=2)
    _create_vacation_request(app, prod_employee_id, tomorrow, tomorrow, status="approved")
    _create_vacation_request(app, prod_pending_id, tomorrow, tomorrow, status="pending")
    _create_vacation_request(app, it_employee_id, tomorrow, tomorrow, status="approved")
    _create_vacation_request(app, prod_employee_id, next_week_day, next_week_day, status="approved")
    _create_vacation_request(app, it_employee_id, next_week_day, next_week_day, status="approved")

    tomorrow_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(manager["username"]),
        json={"message": "Wer hat morgen Urlaub?"},
    )
    next_week_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(manager["username"]),
        json={"message": "Wer hat naechste Woche Urlaub?"},
    )

    tomorrow_payload = tomorrow_response.get_json()
    next_week_payload = next_week_response.get_json()
    tomorrow_serialized = json.dumps(tomorrow_payload, ensure_ascii=True)
    next_week_serialized = json.dumps(next_week_payload, ensure_ascii=True)
    assert tomorrow_response.status_code == 200
    assert tomorrow_payload["type"] == "vacation_absences"
    assert "Eva Urlaub Produktion" in tomorrow_serialized
    assert "Frank Urlaub Pending" not in tomorrow_serialized
    assert "Gina Urlaub IT" not in tomorrow_serialized
    assert next_week_response.status_code == 200
    assert next_week_payload["type"] == "vacation_absences"
    assert "Eva Urlaub Produktion" in next_week_serialized
    assert "Gina Urlaub IT" not in next_week_serialized
    assert all(item["status"] == "approved" for item in tomorrow_payload["data"]["items"])
    for source in tomorrow_payload["sources"]:
        _assert_no_forbidden_source_fields(source, FORBIDDEN_VACATION_SOURCE_FIELDS)


def test_ai_chat_vacation_master_admin_sees_all_department_absences(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify master admins can see approved vacation absences across departments."""
    admin = make_user(
        username="ai_vacation_master_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    prod_employee_id = make_employee(
        personnel_number="P-AI-VAC-ADMIN-1",
        name="Hanna Urlaub Produktion",
        department="Produktion",
    )
    it_employee_id = make_employee(
        personnel_number="P-AI-VAC-ADMIN-2",
        name="Ivan Urlaub IT",
        department="IT",
    )
    tomorrow = date.today() + timedelta(days=1)
    _create_vacation_request(app, prod_employee_id, tomorrow, tomorrow, status="approved")
    _create_vacation_request(app, it_employee_id, tomorrow, tomorrow, status="approved")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Wer fehlt morgen?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "vacation_absences"
    assert payload["data"]["count"] == 2
    assert "Hanna Urlaub Produktion" in serialized_payload
    assert "Ivan Urlaub IT" in serialized_payload


def test_ai_chat_vacation_user_without_employee_gets_safe_no_result(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify users without own employee mapping do not see vacation data."""
    user = make_user(username="ai_vacation_no_employee_user")
    employee_id = make_employee(
        personnel_number="P-AI-VAC-NOEMP-1",
        name="Julia Urlaub Unsichtbar",
        department="Produktion",
    )
    _create_vacation_request(
        app,
        employee_id,
        date.today() + timedelta(days=5),
        date.today() + timedelta(days=5),
        status="pending",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Habe ich Urlaub offen?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "vacation_own_pending"
    assert payload["data"]["count"] == 0
    assert payload["sources"] == []
    assert "Julia Urlaub Unsichtbar" not in serialized_payload


def test_ai_chat_vacation_pending_count_uses_only_visible_requests(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify pending vacation counts are scoped by visible_vacation_query."""
    manager = make_user(username="ai_vacation_pending_count_manager")
    set_dashboard_permission(
        manager["username"],
        "employees",
        can_view=True,
        can_write=True,
        employee_access_level="basic",
    )
    prod_employee_id = make_employee(
        personnel_number="P-AI-VAC-COUNT-1",
        name="Kai Urlaub Count",
        department="Produktion",
    )
    it_employee_id = make_employee(
        personnel_number="P-AI-VAC-COUNT-2",
        name="Lena Urlaub Count IT",
        department="IT",
    )
    _create_vacation_request(
        app,
        prod_employee_id,
        date.today() + timedelta(days=8),
        date.today() + timedelta(days=8),
        status="pending",
    )
    _create_vacation_request(
        app,
        it_employee_id,
        date.today() + timedelta(days=8),
        date.today() + timedelta(days=8),
        status="pending",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(manager["username"]),
        json={"message": "Wie viele Urlaubsantraege sind offen?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "vacation_pending_count"
    assert payload["data"]["count"] == 1
    assert "Kai Urlaub Count" in serialized_payload
    assert "Lena Urlaub Count IT" not in serialized_payload
    assert len(payload["sources"]) == 1
    _assert_vacation_source(payload["sources"][0], prod_employee_id, "Kai Urlaub Count")


def test_ai_chat_vacation_answer_only_redacts_sources_and_data(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify answer-only mode redacts structured vacation evidence."""
    user = make_user(username="ai_vacation_answer_only_user")
    employee_id = make_employee(
        personnel_number="P-AI-VAC-ANSWER-1",
        name="Mia Urlaub Answer Only",
        department="Produktion",
    )
    _link_user_employee(app, user, employee_id)
    _create_vacation_request(
        app,
        employee_id,
        date.today() + timedelta(days=9),
        date.today() + timedelta(days=9),
        status="pending",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Habe ich Urlaub offen?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "vacation_own_pending"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_lists_incidents_in_my_area_without_foreign_department(
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify my-area incident questions rely on visible error scope."""
    user = make_user(username="ai_my_area_incident_user")
    make_error_entry("Presse Bereich", "AREA-1", "Bereich Stoerung", department_name="Produktion")
    make_error_entry("Presse Fremd", "AREA-2", "Fremde Stoerung", department_name="IT")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Stoerungen gibt es in meinem Bereich?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["error_code"] == "AREA-1"
    assert "AREA-2" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_incident_structured_answer_respects_errors_permission(
    client,
    make_user,
    make_error_entry,
    set_dashboard_permission,
    auth_headers,
):
    """Verify incident structured answers deny users without errors:view."""
    user = make_user(username="ai_incident_permission_denied_user")
    make_error_entry("Presse Denied", "DENY-1", "Verborgene Stoerung")
    set_dashboard_permission(user["username"], "errors", can_view=False)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Stoerungen sind offen?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "permission_denied"
    assert payload["sources"] == []


def test_ai_chat_answer_only_redacts_structured_sources_for_normal_users(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify answer-only mode still hides structured source evidence and data."""
    user = make_user(username="ai_structured_answer_only_user")
    make_task(
        "Answer-only sichtbarer Task",
        creator_username=user["username"],
        priority=Priority.URGENT,
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Welche dringenden Tasks gibt es?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "structured_scope"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False


def test_ai_chat_structured_followup_preserves_department_filter(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify follow-up refinements keep the previous department filter."""
    admin = make_user(
        username="ai_department_followup_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_task(
        "Instandhaltung dringend",
        creator_username=admin["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
    )
    make_task(
        "Instandhaltung normal",
        creator_username=admin["username"],
        department_name="Instandhaltung",
        priority=Priority.NORMAL,
    )
    make_task(
        "Produktion dringend",
        creator_username=admin["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
    )
    headers = auth_headers(admin["username"])

    first_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Zeig mir die Aufgaben der Instandhaltung.",
            "session_id": "department-followup",
        },
    )
    followup_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={
            "message": "Welche davon sind dringend?",
            "session_id": "department-followup",
        },
    )

    first_payload = first_response.get_json()
    followup_payload = followup_response.get_json()
    assert first_response.status_code == 200
    assert first_payload["type"] == "structured_scope"
    assert first_payload["data"]["count"] == 2
    assert first_payload["data"]["filters"]["department"] == "Instandhaltung"
    assert followup_response.status_code == 200
    assert followup_payload["type"] == "structured_scope"
    assert followup_payload["data"]["entity_type"] == "tasks"
    assert followup_payload["data"]["count"] == 1
    assert followup_payload["data"]["filters"]["department"] == "Instandhaltung"
    assert followup_payload["data"]["filters"]["priority"] == "urgent"
    assert followup_payload["data"]["items"][0]["title"] == "Instandhaltung dringend"


def test_ai_chat_rejects_empty_messages(client, make_user, auth_headers):
    """Verify chat input validation rejects blank messages."""
    user = make_user(username="ai_empty_user")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "   "},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "message_is_required"
    assert response.get_json()["message"] == "message is required"


def test_ai_chat_denies_requested_scope_with_admin_hint(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify the global assistant explains missing requested permissions."""
    user = make_user(username="ai_denied_employee_user")
    set_dashboard_permission(user["username"], "employees", can_view=False)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Mitarbeiter sind heute verfuegbar?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "permission_denied"
    assert payload["diagnostics"]["status"] == "permission_denied"
    assert "Mitarbeiter" in payload["answer"]
    assert "Admin" in payload["answer"]
    assert payload["sources"] == []
    assert payload["diagnostics"]["evidence_visible"] is False
    assert "confidence" not in payload


def test_ai_chat_answers_machine_scope_without_error_fallback(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify broad machine questions are handled as assistant requests."""
    user = make_user(username="ai_machine_scope_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Chat", produced_item="Deckel")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschinen sind sichtbar?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "assistant"
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["data"]["machines"][0]["name"] == "Anlage Chat"


def test_ai_chat_employee_context_respects_basic_access(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify assistant employee context follows configured access levels."""
    user = make_user(username="ai_employee_basic_user")
    make_employee(name="Anna Chat", salary_group="E9")
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        can_write=False,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Mitarbeiterdaten darf ich sehen?"},
    )

    employee_payload = response.get_json()["data"]["employees"][0]
    source = response.get_json()["sources"][0]
    assert response.status_code == 200
    assert employee_payload["name"] == "Anna Chat"
    assert "salary_group" not in employee_payload
    assert "city" not in employee_payload
    assert source["type"] == "employee"
    assert source["source_kind"] == "structured"
    assert source["source_record_id"] == employee_payload["id"]
    assert source["role_visibility"] == "department:Produktion"
    assert source["employee_access_level"] == "basic"
    assert source["created_at"]


def test_ai_chat_employee_context_is_department_scoped(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify non-admin employee AI context stays scoped to the user's department."""
    user = make_user(username="ai_employee_department_scope_user")
    make_employee(
        personnel_number="P-AI-SCOPE-1",
        name="Anna Scope Produktion",
        department="Produktion",
    )
    make_employee(
        personnel_number="P-AI-SCOPE-2",
        name="Bernd Scope IT",
        department="IT",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Mitarbeiterdaten darf ich sehen?"},
    )

    payload = response.get_json()
    names = {item["name"] for item in payload["data"]["employees"]}
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert "Anna Scope Produktion" in names
    assert "Bernd Scope IT" not in serialized_payload


def test_ai_chat_employee_structured_denies_missing_employee_permission(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify structured employee answers require employee view permission."""
    user = make_user(username="ai_employee_no_view_user")
    make_employee(
        personnel_number="P-AI-EMPL-NOVIEW-1",
        name="Nora Keine Sicht",
        department="Produktion",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=False,
        employee_access_level="none",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wer arbeitet in der Produktion?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "permission_denied"
    assert payload["sources"] == []
    assert "Nora Keine Sicht" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_employee_structured_denies_none_employee_access_level(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify employee_access_level none does not expose employee data."""
    user = make_user(username="ai_employee_access_none_user")
    make_employee(
        personnel_number="P-AI-EMPL-NONE-1",
        name="Noah Access None",
        department="Produktion",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="none",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Mitarbeiter hat die Produktion?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "permission_denied"
    assert payload["sources"] == []
    assert "Noah Access None" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_employee_department_list_uses_visible_department_scope(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify structured employee lists only include visible department employees."""
    user = make_user(username="ai_employee_list_scope_user")
    prod_id = make_employee(
        personnel_number="P-AI-EMPL-LIST-1",
        name="Anna Liste Produktion",
        department="Produktion",
    )
    make_employee(
        personnel_number="P-AI-EMPL-LIST-2",
        name="Bernd Liste IT",
        department="IT",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wer arbeitet in der Produktion?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "employee_department_list"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["name"] == "Anna Liste Produktion"
    assert "Bernd Liste IT" not in serialized_payload
    assert len(payload["sources"]) == 1
    _assert_employee_source(payload["sources"][0], prod_id, "Anna Liste Produktion")
    assert payload["sources"][0]["employee_access_level"] == "basic"
    assert payload["sources"][0]["role_visibility"] == "department:Produktion"


def test_ai_chat_employee_department_list_uses_shift_safe_payload(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify shift employee access exposes shift-safe fields only."""
    user = make_user(username="ai_employee_shift_payload_user")
    make_employee(
        personnel_number="P-AI-EMPL-SHIFT-1",
        name="Berta Schichtdaten",
        department="Produktion",
        salary_group="E12",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="shift",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wer arbeitet in der Produktion?"},
    )

    payload = response.get_json()
    employee_payload = payload["data"]["items"][0]
    assert response.status_code == 200
    assert payload["type"] == "employee_department_list"
    assert employee_payload["name"] == "Berta Schichtdaten"
    assert employee_payload["shift_model"] == "2-Schicht"
    assert employee_payload["current_shift"] == "Frueh"
    assert employee_payload["qualifications"] == "CNC"
    assert "salary_group" not in employee_payload
    assert "birth_date" not in employee_payload
    assert set(payload["sources"][0]) == EMPLOYEE_SOURCE_FIELDS


def test_ai_chat_employee_available_today_excludes_approved_absences(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify today's availability subtracts approved visible vacation only."""
    manager = make_user(username="ai_employee_available_manager")
    present_id = make_employee(
        personnel_number="P-AI-EMPL-AVAIL-1",
        name="Paula Heute Da",
        department="Produktion",
    )
    approved_id = make_employee(
        personnel_number="P-AI-EMPL-AVAIL-2",
        name="Quentin Heute Urlaub",
        department="Produktion",
    )
    pending_id = make_employee(
        personnel_number="P-AI-EMPL-AVAIL-3",
        name="Rita Heute Pending",
        department="Produktion",
    )
    today = date.today()
    _create_vacation_request(app, approved_id, today, today, status="approved")
    _create_vacation_request(app, pending_id, today, today, status="pending")
    set_dashboard_permission(
        manager["username"],
        "employees",
        can_view=True,
        can_write=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(manager["username"]),
        json={"message": "Welche Mitarbeiter sind heute verfuegbar?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "employee_available"
    assert {item["id"] for item in payload["data"]["items"]} == {present_id, pending_id}
    assert "Paula Heute Da" in serialized_payload
    assert "Rita Heute Pending" in serialized_payload
    assert "Quentin Heute Urlaub" not in serialized_payload


def test_ai_chat_employee_master_admin_sees_all_available_employees(
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify master admins can see available employees across departments."""
    admin = make_user(
        username="ai_employee_available_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_employee(
        personnel_number="P-AI-EMPL-ADMIN-1",
        name="Carla Verfuegbar Produktion",
        department="Produktion",
    )
    make_employee(
        personnel_number="P-AI-EMPL-ADMIN-2",
        name="Dirk Verfuegbar IT",
        department="IT",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Welche Mitarbeiter sind heute verfuegbar?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "employee_available"
    assert payload["data"]["count"] == 2
    assert "Carla Verfuegbar Produktion" in serialized_payload
    assert "Dirk Verfuegbar IT" in serialized_payload


def test_ai_chat_employee_department_count_respects_visibility(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify structured employee department counts use visible employees only."""
    user = make_user(username="ai_employee_count_department_user")
    make_employee(
        personnel_number="P-AI-EMPL-COUNT-1",
        name="Eva Count Produktion",
        department="Produktion",
    )
    make_employee(
        personnel_number="P-AI-EMPL-COUNT-2",
        name="Frank Count Instandhaltung",
        department="Instandhaltung",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Mitarbeiter hat die Produktion?"},
    )
    hidden_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Mitarbeiter hat die Instandhaltung?"},
    )

    payload = response.get_json()
    hidden_payload = hidden_response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "employee_department_count"
    assert payload["data"]["department"] == "Produktion"
    assert payload["data"]["count"] == 1
    assert hidden_response.status_code == 200
    assert hidden_payload["type"] == "employee_department_count"
    assert hidden_payload["data"]["department"] == "Instandhaltung"
    assert hidden_payload["data"]["count"] == 0


def test_ai_chat_employee_absences_use_approved_visible_vacations_only(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify employee absence answers use approved visible vacation rows only."""
    manager = make_user(username="ai_employee_absence_manager")
    set_dashboard_permission(
        manager["username"],
        "employees",
        can_view=True,
        can_write=True,
        employee_access_level="basic",
    )
    approved_id = make_employee(
        personnel_number="P-AI-EMPL-ABS-1",
        name="Gina Fehlt Produktion",
        department="Produktion",
    )
    pending_id = make_employee(
        personnel_number="P-AI-EMPL-ABS-2",
        name="Hugo Pending Produktion",
        department="Produktion",
    )
    hidden_id = make_employee(
        personnel_number="P-AI-EMPL-ABS-3",
        name="Ida Fehlt IT",
        department="IT",
    )
    tomorrow = date.today() + timedelta(days=1)
    _create_vacation_request(app, approved_id, tomorrow, tomorrow, status="approved")
    _create_vacation_request(app, pending_id, tomorrow, tomorrow, status="pending")
    _create_vacation_request(app, hidden_id, tomorrow, tomorrow, status="approved")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(manager["username"]),
        json={"message": "Welche Mitarbeiter fehlen morgen?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "employee_absences"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["name"] == "Gina Fehlt Produktion"
    assert payload["data"]["items"][0]["absence_source"] == "approved_vacation"
    assert "Hugo Pending Produktion" not in serialized_payload
    assert "Ida Fehlt IT" not in serialized_payload
    assert len(payload["sources"]) == 1
    _assert_employee_source(payload["sources"][0], approved_id, "Gina Fehlt Produktion")


def test_ai_chat_employee_team_lead_question_does_not_guess(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify team lead questions return a grounded no-data answer."""
    user = make_user(username="ai_employee_teamlead_user")
    make_employee(
        personnel_number="P-AI-EMPL-LEAD-1",
        name="Julia Produktion",
        department="Produktion",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wer ist Teamleiter der Produktion?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "employee_team_lead_unavailable"
    assert payload["data"]["reason"] == "team_lead_field_missing"
    assert payload["data"]["items"] == []
    assert payload["sources"] == []
    assert "Julia Produktion" not in json.dumps(payload, ensure_ascii=True)


def test_ai_chat_employee_answer_only_redacts_sources_and_data(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify answer-only mode redacts structured employee evidence."""
    user = make_user(username="ai_employee_answer_only_user")
    make_employee(
        personnel_number="P-AI-EMPL-ANSWER-1",
        name="Klara Answer Produktion",
        department="Produktion",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Wer arbeitet in der Produktion?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "employee_department_list"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_document_department_list_returns_visible_metadata_only(
    app,
    client,
    make_user,
    make_task,
    make_document,
    set_dashboard_permission,
    auth_headers,
):
    """Verify structured document answers only include visible department metadata."""
    user = make_user(username="ai_document_department_user")
    visible_task_id = make_task("Doku Produktion", creator_username=user["username"])
    hidden_task_id = make_task(
        "Doku IT",
        creator_username=user["username"],
        department_name="IT",
    )
    visible_document_id = make_document(
        visible_task_id,
        created_by=user["id"],
        relative_path="2026/05/document-visible.html",
        department="Produktion",
        machine="Anlage Doku A",
    )
    hidden_document_id = make_document(
        hidden_task_id,
        created_by=user["id"],
        relative_path="2026/05/document-hidden.html",
        department="IT",
        machine="Anlage Doku B",
    )
    _update_generated_document(app, visible_document_id, title="Bericht Produktion Safe")
    _update_generated_document(app, hidden_document_id, title="Bericht IT Hidden")
    set_dashboard_permission(user["username"], "documents", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Dokumente gehoeren zur Produktion?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "document_department_list"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["title"] == "Bericht Produktion Safe"
    assert "Bericht IT Hidden" not in serialized_payload
    assert hidden_document_id not in {source["id"] for source in payload["sources"]}
    _assert_document_source(
        payload["sources"][0],
        visible_document_id,
        "Bericht Produktion Safe",
    )


def test_ai_chat_document_machine_filter_includes_reports_and_manuals(
    app,
    client,
    make_user,
    make_task,
    make_document,
    make_machine,
    set_dashboard_permission,
    auth_headers,
):
    """Verify machine-filtered document answers include safe report and manual cards."""
    user = make_user(username="ai_document_machine_user")
    machine_id = make_machine(name="Anlage Doku C")
    task_id = make_task("Doku Maschine", creator_username=user["username"])
    document_id = make_document(
        task_id,
        created_by=user["id"],
        relative_path="2026/05/document-machine.html",
        department="Produktion",
        machine="Anlage Doku C",
    )
    _update_generated_document(
        app,
        document_id,
        title="Bericht Anlage Doku C",
        machine_id=machine_id,
        summary="Interne Summary darf nicht in Sources stehen",
        approval_comment="Interner Kommentar darf nicht in Sources stehen",
    )
    manual_id = _create_machine_manual(
        app,
        created_by=user["id"],
        machine_id=machine_id,
        title="Manual Anlage Doku C",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Dokumente betreffen Maschine Anlage Doku C?"},
    )

    payload = response.get_json()
    source_by_type = {source["type"]: source for source in payload["sources"]}
    serialized_sources = json.dumps(payload["sources"], ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "document_machine_list"
    assert payload["data"]["count"] == 2
    _assert_document_source(
        source_by_type["document"],
        document_id,
        "Bericht Anlage Doku C",
    )
    _assert_manual_source(source_by_type["machine_manual"], manual_id, "Manual Anlage Doku C")
    assert "Interne Summary" not in serialized_sources
    assert "Interne Analyse" not in serialized_sources
    assert "Interner Kommentar" not in serialized_sources
    assert "relative_path" not in serialized_sources


def test_ai_chat_document_outdated_uses_structured_metadata(
    app,
    client,
    make_user,
    make_task,
    make_document,
    set_dashboard_permission,
    auth_headers,
):
    """Verify outdated document answers use explicit structured document metadata."""
    user = make_user(username="ai_document_outdated_user")
    stale_task_id = make_task("Doku Veraltet", creator_username=user["username"])
    fresh_task_id = make_task("Doku Frisch", creator_username=user["username"])
    stale_document_id = make_document(
        stale_task_id,
        created_by=user["id"],
        relative_path="2026/05/document-stale.html",
        department="Produktion",
        machine="Anlage Stale",
    )
    fresh_document_id = make_document(
        fresh_task_id,
        created_by=user["id"],
        relative_path="2026/05/document-fresh.html",
        department="Produktion",
        machine="Anlage Fresh",
    )
    _update_generated_document(
        app,
        stale_document_id,
        title="Bericht Veraltet",
        quality_status="outdated",
    )
    _update_generated_document(app, fresh_document_id, title="Bericht Frisch")
    set_dashboard_permission(user["username"], "documents", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Dokumente sind veraltet?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "document_outdated"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["quality_status"] == "outdated"
    assert "Bericht Veraltet" in serialized_payload
    assert "Bericht Frisch" not in serialized_payload


def test_ai_chat_document_this_week_uses_visible_created_metadata(
    app,
    client,
    make_user,
    make_task,
    make_document,
    set_dashboard_permission,
    auth_headers,
):
    """Verify this-week document answers use visible created/upload metadata."""
    user = make_user(username="ai_document_this_week_user")
    current_task_id = make_task("Doku Diese Woche", creator_username=user["username"])
    old_task_id = make_task("Doku Alt", creator_username=user["username"])
    current_document_id = make_document(
        current_task_id,
        created_by=user["id"],
        relative_path="2026/05/document-week.html",
        department="Produktion",
        machine="Anlage Woche",
    )
    old_document_id = make_document(
        old_task_id,
        created_by=user["id"],
        relative_path="2026/05/document-old.html",
        department="Produktion",
        machine="Anlage Alt",
    )
    _update_generated_document(app, current_document_id, title="Bericht Diese Woche")
    _update_generated_document(
        app,
        old_document_id,
        title="Bericht Alt",
        created_at=datetime(2020, 1, 1),
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Dokumente wurden diese Woche hochgeladen?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "document_this_week"
    assert "Bericht Diese Woche" in serialized_payload
    assert "Bericht Alt" not in serialized_payload


def test_ai_chat_document_answer_only_redacts_sources_and_data(
    client,
    make_user,
    make_task,
    make_document,
    set_dashboard_permission,
    auth_headers,
):
    """Verify answer-only mode redacts structured document evidence."""
    user = make_user(username="ai_document_answer_only_user")
    task_id = make_task("Doku Answer Only", creator_username=user["username"])
    make_document(
        task_id,
        created_by=user["id"],
        relative_path="2026/05/document-answer-only.html",
        department="Produktion",
        machine="Anlage Answer",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Welche Dokumente gehoeren zur Produktion?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "document_department_list"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_shiftplan_entries_use_visible_published_department_plans(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify non-admin shiftplan answers use published own-department plans only."""
    user = make_user(username="ai_shiftplan_visible_user")
    tomorrow = date.today() + timedelta(days=1)
    prod_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-VIS-1",
        name="Anna Schicht Produktion",
        department="Produktion",
    )
    draft_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-VIS-2",
        name="Bernd Schicht Draft",
        department="Produktion",
    )
    it_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-VIS-3",
        name="Clara Schicht IT",
        department="IT",
    )
    visible_plan_id = _create_shift_plan(app, user["id"], "Produktion", tomorrow)
    draft_plan_id = _create_shift_plan(app, user["id"], "Produktion", tomorrow, status="draft")
    hidden_plan_id = _create_shift_plan(app, user["id"], "IT", tomorrow)
    entry_id = _create_shift_entry(app, visible_plan_id, prod_employee_id, tomorrow)
    _create_shift_entry(app, draft_plan_id, draft_employee_id, tomorrow)
    _create_shift_entry(app, hidden_plan_id, it_employee_id, tomorrow)
    set_dashboard_permission(user["username"], "shiftplans", can_view=True)
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wer ist morgen eingeplant?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "shiftplan_entries"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["employee"]["name"] == "Anna Schicht Produktion"
    assert "Bernd Schicht Draft" not in serialized_payload
    assert "Clara Schicht IT" not in serialized_payload
    assert len(payload["sources"]) == 1
    _assert_shiftplan_entry_source(payload["sources"][0], entry_id, "Anna Schicht Produktion")


def test_ai_chat_shiftplan_master_admin_sees_all_departments(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Verify master admins can see planned employees across departments."""
    admin = make_user(
        username="ai_shiftplan_admin_user",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    tomorrow = date.today() + timedelta(days=1)
    prod_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-ADMIN-1",
        name="David Schicht Produktion",
        department="Produktion",
    )
    it_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-ADMIN-2",
        name="Eva Schicht IT",
        department="IT",
    )
    prod_plan_id = _create_shift_plan(app, admin["id"], "Produktion", tomorrow)
    it_plan_id = _create_shift_plan(app, admin["id"], "IT", tomorrow)
    _create_shift_entry(app, prod_plan_id, prod_employee_id, tomorrow)
    _create_shift_entry(app, it_plan_id, it_employee_id, tomorrow)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Wer ist morgen eingeplant?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "shiftplan_entries"
    assert payload["data"]["count"] == 2
    assert "David Schicht Produktion" in serialized_payload
    assert "Eva Schicht IT" in serialized_payload


def test_ai_chat_shiftplan_understaffed_next_week_uses_coverage_slots(
    app,
    client,
    make_user,
    make_machine,
    set_dashboard_permission,
    auth_headers,
):
    """Verify undercoverage answers use visible coverage slots with missing staff."""
    user = make_user(username="ai_shiftplan_understaffed_user")
    machine_id = make_machine(name="Anlage Unterdeckung")
    next_monday, _next_sunday = _next_week_test_bounds()
    plan_id = _create_shift_plan(app, user["id"], "Produktion", next_monday)
    missing_slot_id = _create_shift_coverage_slot(
        app,
        plan_id,
        next_monday,
        "Spaet",
        missing=2,
        machine_id=machine_id,
    )
    _create_shift_coverage_slot(app, plan_id, next_monday, "Frueh", missing=0)
    set_dashboard_permission(user["username"], "shiftplans", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Schicht ist naechste Woche unterbesetzt?"},
    )

    payload = response.get_json()
    serialized_sources = json.dumps(payload["sources"], ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "shiftplan_understaffed"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["missing"] == 2
    assert len(payload["sources"]) == 1
    _assert_shiftplan_coverage_source(payload["sources"][0], missing_slot_id)
    assert "Interner Grund" not in serialized_sources
    assert "Interner Vorschlag" not in serialized_sources


def test_ai_chat_shiftplan_shift_count_counts_visible_entries(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify shift count answers count visible employees in the requested shift."""
    user = make_user(username="ai_shiftplan_count_user")
    tomorrow = date.today() + timedelta(days=1)
    first_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-COUNT-1",
        name="Frank Spaet Eins",
        department="Produktion",
    )
    second_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-COUNT-2",
        name="Gina Spaet Zwei",
        department="Produktion",
    )
    night_employee_id = make_employee(
        personnel_number="P-AI-SHIFT-COUNT-3",
        name="Hugo Nacht",
        department="Produktion",
    )
    plan_id = _create_shift_plan(app, user["id"], "Produktion", tomorrow)
    _create_shift_entry(app, plan_id, first_employee_id, tomorrow, shift="Spaet")
    _create_shift_entry(
        app,
        plan_id,
        second_employee_id,
        tomorrow + timedelta(days=1),
        shift="Spaet",
    )
    _create_shift_entry(app, plan_id, night_employee_id, tomorrow, shift="Nacht")
    set_dashboard_permission(user["username"], "shiftplans", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Mitarbeiter sind in der Spaetschicht?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "shiftplan_shift_count"
    assert payload["data"]["shift"] == "Spaet"
    assert payload["data"]["count"] == 2


def test_ai_chat_shiftplan_redacts_employee_names_without_employee_access(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify shiftplan answer text follows employee_access_level restrictions."""
    user = make_user(username="ai_shiftplan_no_employee_access_user")
    tomorrow = date.today() + timedelta(days=1)
    employee_id = make_employee(
        personnel_number="P-AI-SHIFT-NONE-1",
        name="Jana Schicht Geheim",
        department="Produktion",
    )
    plan_id = _create_shift_plan(app, user["id"], "Produktion", tomorrow)
    entry_id = _create_shift_entry(app, plan_id, employee_id, tomorrow)
    set_dashboard_permission(user["username"], "shiftplans", can_view=True)
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=False,
        employee_access_level="none",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wer ist morgen eingeplant?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "shiftplan_entries"
    assert payload["data"]["items"][0]["employee"] is None
    assert payload["sources"][0]["employee_name"] == ""
    assert payload["sources"][0]["title"].startswith("Schichtplaneintrag")
    assert "Mitarbeiter nicht sichtbar" in payload["answer"]
    assert "Jana Schicht Geheim" not in serialized_payload
    _assert_shiftplan_entry_source(payload["sources"][0], entry_id, "")


def test_ai_chat_shiftplan_answer_only_redacts_sources_and_data(
    app,
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify answer-only mode redacts structured shiftplan evidence."""
    user = make_user(username="ai_shiftplan_answer_only_user")
    tomorrow = date.today() + timedelta(days=1)
    employee_id = make_employee(
        personnel_number="P-AI-SHIFT-ANSWER-1",
        name="Ida Schicht Answer",
        department="Produktion",
    )
    plan_id = _create_shift_plan(app, user["id"], "Produktion", tomorrow)
    _create_shift_entry(app, plan_id, employee_id, tomorrow)
    set_dashboard_permission(user["username"], "shiftplans", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Wer ist morgen eingeplant?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "shiftplan_entries"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_inventory_low_stock_returns_safe_visible_sources(
    app,
    client,
    make_user,
    make_material,
    set_dashboard_permission,
    auth_headers,
):
    """Verify low-stock inventory answers use below-minimum rows and safe sources."""
    user = make_user(username="ai_inventory_low_stock_user")
    low_id = make_material("Filter Low Stock", 99.9, 1)
    ok_id = make_material("Filter OK Stock", 199.9, 10)
    _update_inventory_material(
        app,
        low_id,
        min_quantity=5,
        criticality="high",
        lead_time_days=12,
        manufacturer="SafeParts",
    )
    _update_inventory_material(app, ok_id, min_quantity=5)
    set_dashboard_permission(user["username"], "inventory", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Materialien sind unter Mindestbestand?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "inventory_low_stock"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["name"] == "Filter Low Stock"
    assert payload["data"]["items"][0]["is_below_minimum"] is True
    assert "Filter OK Stock" not in serialized_payload
    assert "99.9" not in serialized_payload
    assert len(payload["sources"]) == 1
    _assert_inventory_source(payload["sources"][0], low_id, "Filter Low Stock")


def test_ai_chat_inventory_count_respects_permission(
    client,
    make_user,
    make_material,
    set_dashboard_permission,
    auth_headers,
):
    """Verify inventory count answers require inventory visibility."""
    user = make_user(username="ai_inventory_count_user")
    denied = make_user(username="ai_inventory_count_denied_user")
    make_material("Zaehler Lagerteil", 12.5, 3)
    set_dashboard_permission(user["username"], "inventory", can_view=True)
    set_dashboard_permission(denied["username"], "inventory", can_view=False)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Artikel sind im Lager?"},
    )
    denied_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(denied["username"]),
        json={"message": "Wie viele Artikel sind im Lager?"},
    )

    payload = response.get_json()
    denied_payload = denied_response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "inventory_count"
    assert payload["data"]["count"] == 1
    assert denied_response.status_code == 200
    assert denied_payload["type"] == "permission_denied"
    assert denied_payload["sources"] == []


def test_ai_chat_inventory_machine_filter_returns_linked_parts(
    client,
    make_user,
    make_machine,
    make_material,
    set_dashboard_permission,
    auth_headers,
):
    """Verify machine-filtered inventory answers return linked visible parts."""
    user = make_user(username="ai_inventory_machine_user")
    machine_id = make_machine(name="Anlage Lager X")
    other_machine_id = make_machine(name="Anlage Lager Y")
    linked_id = make_material("Sensor Lager X", 30.0, 4, machine_id=machine_id)
    make_material("Sensor Lager Y", 40.0, 4, machine_id=other_machine_id)
    set_dashboard_permission(user["username"], "inventory", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Teile gehoeren zu Maschine Anlage Lager X?"},
    )

    payload = response.get_json()
    serialized_payload = json.dumps(payload, ensure_ascii=True)
    assert response.status_code == 200
    assert payload["type"] == "inventory_machine_materials"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["machine"] == "Anlage Lager X"
    assert "Sensor Lager X" in serialized_payload
    assert "Sensor Lager Y" not in serialized_payload
    _assert_inventory_source(payload["sources"][0], linked_id, "Sensor Lager X")


def test_ai_chat_inventory_reorder_question_uses_low_stock_logic(
    app,
    client,
    make_user,
    make_material,
    set_dashboard_permission,
    auth_headers,
):
    """Verify reorder questions use the same below-minimum stock logic."""
    user = make_user(username="ai_inventory_reorder_user")
    material_id = make_material("Dichtung Nachbestellen", 7.5, 0)
    _update_inventory_material(app, material_id, min_quantity=2)
    set_dashboard_permission(user["username"], "inventory", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was muss nachbestellt werden?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "inventory_low_stock"
    assert payload["data"]["count"] == 1
    assert payload["data"]["items"][0]["name"] == "Dichtung Nachbestellen"


def test_ai_chat_inventory_answer_only_redacts_sources_and_data(
    app,
    client,
    make_user,
    make_material,
    set_dashboard_permission,
    auth_headers,
):
    """Verify answer-only mode redacts structured inventory evidence."""
    user = make_user(username="ai_inventory_answer_only_user")
    material_id = make_material("Lager Answer Only", 5.0, 1)
    _update_inventory_material(app, material_id, min_quantity=3)
    set_dashboard_permission(user["username"], "inventory", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Welches Ersatzteil geht bald aus?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "inventory_low_stock"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_dashboard_permission_override_controls_machine_counts(
    client,
    make_user,
    make_machine,
    set_dashboard_permission,
    auth_headers,
):
    """Verify AI count answers follow assigned machine dashboard permissions."""
    user = make_user(username="ai_machine_permission_override_user")
    make_machine(name="Permission Presse AI", produced_item="Deckel")

    blocked_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Maschinen gibt es?"},
    )
    set_dashboard_permission(user["username"], "machines", can_view=True)
    allowed_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Maschinen gibt es?"},
    )
    set_dashboard_permission(user["username"], "machines", can_view=False)
    revoked_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Maschinen gibt es?"},
    )

    blocked_payload = blocked_response.get_json()
    allowed_payload = allowed_response.get_json()
    revoked_payload = revoked_response.get_json()
    assert blocked_response.status_code == 200
    assert blocked_payload["type"] == "permission_denied"
    assert allowed_response.status_code == 200
    assert allowed_payload["type"] == "machines_count"
    assert allowed_payload["data"]["count"] == 1
    assert revoked_response.status_code == 200
    assert revoked_payload["type"] == "permission_denied"


def test_ai_chat_returns_sources_and_audit_metadata(
    app,
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify chat responses include sources and metadata-only audit records."""
    user = make_user(username="ai_sources_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Quelle", produced_item="Deckel")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Maschinen sind sichtbar?"},
    )

    payload = response.get_json()
    audit_id = payload["diagnostics"]["audit_event_id"]
    assert response.status_code == 200
    assert payload["chat_message_id"]
    source = payload["sources"][0]
    assert source["type"] == "machine"
    assert source["source_type"] == "machine"
    assert source["source_id"] == source["id"]
    assert source["title"] == "Anlage Quelle"
    assert source["module"] == "machines"
    assert source["machine"] == "Anlage Quelle"
    assert source["machine_id"] == source["id"]
    assert source["role_visibility"] == "public"
    assert source["created_at"]
    assert source["source_kind"] == "structured"
    assert source["relevance"] == source["normalized_score"]
    assert source["relevance"] >= 0
    assert "content" not in source
    assert payload["diagnostics"]["source_count"] == len(payload["sources"])
    assert payload["diagnostics"]["confidence_score"] == payload["confidence"]["score"]
    assert payload["diagnostics"]["confidence_level"] == payload["confidence"]["level"]
    assert payload["answer_quality"]["status"] == "grounded"
    assert payload["answer_quality"]["has_sources"] is True
    assert payload["answer_quality"]["source_count"] == len(payload["sources"])
    assert payload["answer_quality"]["confidence_score"] == payload["confidence"]["score"]
    assert payload["answer_quality"]["evidence_visible"] is True
    assert payload["answer_quality"]["no_answer"] is False

    with app.app_context():
        event = db.session.get(AIAuditEvent, audit_id)
        chat_message = db.session.get(ChatMessage, payload["chat_message_id"])
        assert event is not None
        assert chat_message is not None
        assert event.workflow == "assistant"
        assert event.source_count == len(payload["sources"])
        assert event.confidence_score == payload["confidence"]["score"]
        assert event.confidence_level == payload["confidence"]["level"]
        assert event.retrieval_explainability()["source_count"] == len(payload["sources"])
        assert chat_message.audit_event_id == audit_id
        assert chat_message.source_count == len(payload["sources"])
        assert chat_message.confidence_score == payload["confidence"]["score"]
        assert chat_message.confidence_level == payload["confidence"]["level"]
        assert not hasattr(event, "prompt")
        assert not hasattr(event, "response")


def test_ai_chat_bubble_redacts_evidence_for_non_it_users(
    app,
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify normal chat-bubble users receive answer-only AI responses."""
    user = make_user(username="ai_bubble_redacted_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Bubble", produced_item="Deckel")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Welche Maschinen sind sichtbar?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["answer"]
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"] == {
        "answer_origin": "local",
        "evidence_visible": False,
        "fallback_used": False,
        "status": "local_answer",
    }
    assert payload["answer_quality"]["evidence_visible"] is False
    assert payload["answer_quality"]["status_reason"]
    assert payload["answer_quality"]["source_count"] == 0
    assert payload["answer_quality"]["confidence_score"] is None
    assert "confidence" not in payload
    assert "rag" not in payload
    assert "action_preview" not in payload

    with app.app_context():
        chat_message = db.session.get(ChatMessage, payload["chat_message_id"])
        assert chat_message.source_count > 0
        assert chat_message.confidence_score is not None


def test_ai_chat_bubble_keeps_evidence_for_it_users(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify IT users may still inspect chat-bubble sources and diagnostics."""
    user = make_user(username="ai_bubble_it_user", role=Role.IT)
    make_machine(name="Anlage IT Bubble", produced_item="Deckel")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Welche Maschinen sind sichtbar?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["sources"]
    assert payload["diagnostics"]["source_count"] == len(payload["sources"])
    assert payload["confidence"]["score"] == payload["diagnostics"]["confidence_score"]
    assert payload["answer_quality"]["evidence_visible"] is True


def test_ai_confidence_scores_high_for_strong_sourced_context(app, make_user):
    """Verify strong sources, quality, machine match, and feedback yield high confidence."""
    user = make_user(username="ai_confidence_high_user")
    sources = [
        {
            "type": "knowledge",
            "id": 11,
            "chunk_id": 101,
            "title": "Presse 3 E104",
            "score": 120,
            "quality_status": "admin_approved",
            "machine_match": 1.0,
        },
        {"type": "error", "id": 12, "title": "E104", "score": 95},
        {"type": "machine", "id": 13, "title": "Presse 3", "score": 88},
    ]
    with app.app_context():
        db.session.add(
            AIFeedback(
                user_id=user["id"],
                prompt="Fehler E104 Presse 3",
                response="Sensor reinigen",
                response_type="assistant",
                rating="helpful",
                sources_json=json.dumps([sources[0]], ensure_ascii=True),
                source_count=1,
            ),
        )
        db.session.commit()

        confidence = calculate_ai_confidence(
            "Was hilft bei Fehler E104 an Presse 3?",
            sources,
            response_type="assistant",
        ).to_dict()

    assert confidence["level"] == "high"
    assert confidence["score"] >= 70
    assert confidence["factors"]["feedback"] > 0.58
    assert "hallucination detection" in confidence["method"]


def test_ai_audit_stores_sanitized_retrieval_explainability(app, make_user):
    """Verify audit explainability keeps scores and source ids but no sensitive text."""
    user = make_user(username="ai_explainability_audit_user")
    raw_explainability = {
        "source_count": 1,
        "explained_source_count": 1,
        "averages": {
            "semantic_similarity": 0.82,
            "lexical_score": 41.2,
            "machine_match": 0.9,
            "feedback_influence": 4.0,
            "recency_influence": 2.0,
        },
        "quality_status_counts": {"admin_approved": 1},
        "machine_match_count": 1,
        "feedback_influenced_count": 1,
        "recency_influenced_count": 1,
        "sources": [
            {
                "type": "knowledge",
                "id": 7,
                "source_type": "manual_training",
                "source_id": 42,
                "source_record_id": 42,
                "source_kind": "rag",
                "knowledge_source_type": "manual_training",
                "module": "knowledge",
                "machine_id": 99,
                "role_visibility": "department:Produktion",
                "employee_access_level": "shift",
                "created_at": "2026-05-30T10:00:00",
                "chunk_id": 70,
                "score": 118,
                "title": "Sensitive source title",
                "prompt": "Sensitive prompt",
                "context": "Sensitive retrieved content",
                "explainability": {
                    "semantic_similarity": 0.82,
                    "lexical_score": 41.2,
                    "lexical_similarity": 0.75,
                    "machine_match": 0.9,
                    "quality_status": "admin_approved",
                    "feedback_influence": 4.0,
                    "recency_influence": 2.0,
                },
            },
        ],
        "retrieval_debug": {
            "top_k": 4,
            "rerank_candidate_limit": 20,
            "vector_candidates_found": 12,
            "final_visible_sources": 3,
            "decision_trace": [
                {
                    "step": "vector_candidate_scan",
                    "status": "ok",
                    "reason": "candidate_pool",
                    "metrics": {"query": "Sensitive query", "candidate_count": 12},
                }
            ],
        },
    }

    with app.app_context():
        event_id = create_ai_audit_event(
            db.session.get(User, user["id"]),
            "assistant",
            {
                "status": "local_answer",
                "retrieval_explainability": raw_explainability,
            },
            source_count=1,
        )
        event = db.session.get(AIAuditEvent, event_id)
        explainability = event.retrieval_explainability()

    stored_json = json.dumps(explainability, ensure_ascii=True)
    assert explainability["explained_source_count"] == 1
    assert explainability["sources"][0]["type"] == "knowledge"
    assert explainability["sources"][0]["id"] == 7
    assert explainability["sources"][0]["source_type"] == "manual_training"
    assert explainability["sources"][0]["source_id"] == 42
    assert explainability["sources"][0]["source_record_id"] == 42
    assert explainability["sources"][0]["source_kind"] == "rag"
    assert explainability["sources"][0]["knowledge_source_type"] == "manual_training"
    assert explainability["sources"][0]["machine_id"] == 99
    assert explainability["sources"][0]["role_visibility"] == "department:Produktion"
    assert explainability["sources"][0]["employee_access_level"] == "shift"
    assert explainability["sources"][0]["explainability"]["semantic_similarity"] == 0.82
    assert explainability["retrieval_debug"]["reranking"]["candidate_limit"] == 20
    assert explainability["retrieval_debug"]["reranking"]["candidate_count"] == 12
    assert explainability["retrieval_debug"]["reranking"]["final_source_count"] == 3
    assert "query" not in explainability["retrieval_debug"]["decision_trace"][0]["metrics"]
    assert "Sensitive" not in stored_json
    assert "prompt" not in stored_json
    assert "context" not in stored_json


def test_ai_chat_marks_and_persists_low_confidence_answers(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify weak answers are visibly marked and persisted with low confidence."""
    user = make_user(
        username="ai_confidence_low_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie behebe ich Stoerung QX999 an Maschine Omega?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["confidence"]["level"] == "low"
    assert payload["diagnostics"]["confidence_level"] == "low"
    assert payload["answer_quality"]["status"] == "no_answer"
    assert payload["answer_quality"]["status_reason"] == "empty_retrieval_hallucination_guard"
    assert payload["answer_quality"]["uncertainty"] == "high"
    assert payload["answer_quality"]["no_answer"] is True
    assert payload["answer"].startswith("## Niedrige Confidence")
    assert payload["confidence"]["warning"]

    with app.app_context():
        event = db.session.get(AIAuditEvent, payload["diagnostics"]["audit_event_id"])
        chat_message = db.session.get(ChatMessage, payload["chat_message_id"])

    assert event.confidence_level == "low"
    assert chat_message.confidence_level == "low"
    assert chat_message.confidence_score == payload["confidence"]["score"]


def test_ai_chat_blocks_hallucination_when_retrieval_is_empty(
    client,
    make_user,
    auth_headers,
):
    """Verify unresolved error questions expose empty retrieval and avoid fake fixes."""
    user = make_user(
        username="ai_empty_retrieval_guard_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie behebe ich Stoerung QX999 an Maschine Omega?"},
    )

    payload = response.get_json()
    warnings = {warning["type"] for warning in payload["diagnostics"]["quality_warnings"]}
    assert response.status_code == 200
    assert "Keine belastbare Quelle gefunden" in payload["answer"]
    assert "Gepruefte Datenquellen" in payload["answer"]
    assert "Fehlerkatalog" in payload["answer"]
    assert "Erkannte Suchsignale" in payload["answer"]
    assert "Wahrscheinlicher Grund" in payload["answer"]
    assert "Fehlercode: QX999" in payload["answer"]
    assert "Maschinenhinweis: Omega" in payload["answer"]
    assert "Kandidaten gefunden" not in payload["answer"]
    assert payload["diagnostics"]["answer_mode"] == "error_analysis"
    assert payload["diagnostics"]["empty_retrieval"] is True
    assert payload["diagnostics"]["hallucination_warning"] is True
    assert {"empty_retrieval", "hallucination_risk"}.issubset(warnings)
    assert payload["answer_quality"]["status"] == "no_answer"
    assert payload["answer_quality"]["status_reason"] == "empty_retrieval_hallucination_guard"
    assert payload["answer_quality"]["warning_count"] >= 2
    assert "hallucination_risk" in payload["answer_quality"]["warning_types"]
    assert payload["answer_quality"]["primary_warning_type"] == "hallucination_risk"
    assert payload["sources"] == []


def test_ai_chat_empty_retrieval_admin_answer_includes_debug_counters(
    client,
    make_user,
    auth_headers,
):
    """Verify admins see prompt-safe retrieval counters in empty answers."""
    admin = make_user(
        username="ai_empty_retrieval_admin_user",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Wie behebe ich Stoerung EMPTYDBG999 an Maschine EmptyDbg?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["sources"] == []
    assert "Keine belastbare Quelle gefunden" in payload["answer"]
    assert "Diagnose fuer Admins" in payload["answer"]
    assert "Kandidaten gefunden" in payload["answer"]
    assert "Permission" in payload["answer"]
    assert "Quality" in payload["answer"]
    assert "Score/Anchor" in payload["answer"]
    assert "SQL candidate count" in payload["answer"]
    assert "vector candidate count" in payload["answer"]
    assert "filtered by permission" in payload["answer"]
    assert "filtered by quality" in payload["answer"]
    assert "filtered by score" in payload["answer"]
    assert "Wie behebe ich" not in payload["answer"]


def test_empty_retrieval_general_question_stays_neutral():
    """Verify broad empty retrieval answers stay helpful without inventing content."""
    answer = build_empty_retrieval_answer(
        "Kannst du eine unbekannte Wartungsregel erklaeren?",
        retrieval={
            "rag": {
                "query_classification": {
                    "query_type": "GENERAL",
                    "extracted_keywords": [],
                    "possible_entities": {},
                    "suggested_sources": [],
                }
            }
        },
    )

    assert "Keine belastbare Quelle gefunden" in answer
    assert "Gepruefte Datenquellen" in answer
    assert "Tasks" in answer
    assert "Fehlerkatalog" in answer
    assert "Wahrscheinlicher Grund" in answer
    assert "keine passenden Treffer ermittelt" in answer
    assert "Ohne Quelle" in answer
    assert "konkrete Loesung" in answer
    assert "Kandidaten gefunden" not in answer


def test_empty_retrieval_answer_explains_filtered_candidates_without_counts():
    """Verify non-admin empty answers explain filtering without exposing counters."""
    answer = build_empty_retrieval_answer(
        "Was bedeutet Fehler E404?",
        retrieval={
            "rag": {
                "query_classification": {
                    "query_type": "HYBRID",
                    "extracted_keywords": ["fehler"],
                    "possible_entities": {"error_codes": ["E404"]},
                    "suggested_sources": ["errors", "knowledge"],
                },
                "retrieval_debug": {
                    "sql_candidates_found": 1,
                    "vector_candidates_found": 2,
                    "permission_filtered": 1,
                    "quality_filtered": 1,
                    "score_anchor_filtered": 1,
                    "final_visible_sources": 0,
                },
            }
        },
    )

    assert "Wahrscheinlicher Grund" in answer
    assert "Sichtbarkeits-, Qualitaets- oder Relevanzpruefung" in answer
    assert "SQL candidate count" not in answer
    assert "vector candidate count" not in answer


def test_answer_quality_marks_conflicting_sources_as_uncertain(app):
    """Verify source conflicts are visible as answer-quality uncertainty."""
    from app.ai.status import finalize_chat_result_quality

    result = {
        "type": "assistant",
        "answer": "Quelle A und Quelle B nennen unterschiedliche naechste Schritte.",
        "sources": [{"type": "knowledge", "id": 1, "title": "Konfliktquelle"}],
        "confidence": {"score": 78, "level": "high"},
        "diagnostics": {
            "status": "openai_used",
            "source_conflicts": {
                "has_conflicts": True,
                "count": 1,
                "summary": "1 potenzielle Quellenkonflikte erkannt.",
            },
        },
    }

    with app.app_context():
        finalized = finalize_chat_result_quality(result, "Wie behebe ich Fehler C900?")
    warning_types = {warning["type"] for warning in finalized["diagnostics"]["quality_warnings"]}

    assert "source_conflict" in warning_types
    assert finalized["answer_quality"]["status"] == "conflicting_sources"
    assert finalized["answer_quality"]["status_reason"] == "source_conflict_detected"
    assert finalized["answer_quality"]["uncertainty"] == "medium"
    assert finalized["answer_quality"]["has_sources"] is True
    assert finalized["answer_quality"]["no_answer"] is False
    assert "Widerspruechliche Quellen" in finalized["answer_quality"]["recommended_user_action"]


def test_answer_quality_prioritizes_conflicts_over_low_confidence(app):
    """Verify source conflicts stay visible even when confidence is low."""
    from app.ai.status import finalize_chat_result_quality

    result = {
        "type": "assistant",
        "answer": "Quellen nennen unterschiedliche Reparaturschritte.",
        "sources": [{"type": "knowledge", "id": 1, "title": "Konflikt A"}],
        "confidence": {"score": 31, "level": "low"},
        "diagnostics": {
            "status": "openai_used",
            "source_conflicts": {
                "has_conflicts": True,
                "count": 2,
                "summary": "2 potenzielle Quellenkonflikte erkannt.",
            },
        },
    }

    finalized = finalize_chat_result_quality(result, "Wie behebe ich Fehler C901?")
    warning_types = {warning["type"] for warning in finalized["diagnostics"]["quality_warnings"]}

    assert {"low_confidence", "source_conflict"} <= warning_types
    assert finalized["answer_quality"]["status"] == "conflicting_sources"
    assert finalized["answer_quality"]["status_reason"] == "source_conflict_detected"
    assert finalized["answer_quality"]["uncertainty"] == "medium"
    assert finalized["answer_quality"]["confidence_level"] == "low"
    assert finalized["answer_quality"]["primary_warning_type"] == "source_conflict"
    assert finalized["answer_quality"]["no_answer"] is False


def test_ai_chat_tracks_knowledge_gap_when_no_sources_match(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify unanswered AI questions create an open knowledge-gap entry."""
    user = make_user(
        username="ai_gap_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie behebe ich Stoerung QX999 an Maschine Omega?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["knowledge_gap"]["status"] == "open"
    assert payload["knowledge_gap"]["machine"] == "Maschine Omega"
    assert payload["diagnostics"]["knowledge_gap_created"] is True
    with app.app_context():
        gap = KnowledgeGap.query.one()
        assert gap.question == "Wie behebe ich Stoerung QX999 an Maschine Omega?"
        assert gap.department == "Instandhaltung"
        assert gap.status == "open"
        assert gap.occurrence_count == 1


def test_ai_chat_does_not_track_gap_for_sourced_answer(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify sourced AI answers do not create unnecessary knowledge gaps."""
    user = make_user(
        username="ai_gap_sourced_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        "Anlage 4",
        "E104",
        "Sensor erkennt Produkt nicht",
        department_name="Instandhaltung",
        description="Sensor Signal fehlt sporadisch an Anlage 4.",
        solution="Sensor reinigen und Abstand pruefen.",
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was hilft bei Fehler E104 an Anlage 4?"},
    )

    assert response.status_code == 200
    assert "knowledge_gap" not in response.get_json()
    with app.app_context():
        assert KnowledgeGap.query.count() == 0


def test_ai_chat_deduplicates_recent_knowledge_gaps(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify repeated unanswered questions update one recent open gap."""
    user = make_user(
        username="ai_gap_duplicate_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])
    message = "Warum faellt Anlage Delta mit Fehler X999 aus?"

    first_response = client.post("/api/v1/ai/chat", headers=headers, json={"message": message})
    second_response = client.post("/api/v1/ai/chat", headers=headers, json={"message": message})

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert first_response.get_json()["knowledge_gap"]["created"] is True
    assert second_response.get_json()["knowledge_gap"]["created"] is False
    with app.app_context():
        gap = KnowledgeGap.query.one()
        assert gap.occurrence_count == 2


def test_ai_chat_returns_task_action_preview_without_writing(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify the assistant returns read-only task previews for form filling."""
    user = make_user(username="ai_preview_user", role=Role.INSTANDHALTUNG)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Task erstellen: Maschine 3 macht laute Geraeusche"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["action_preview"]["type"] == "task_draft"
    assert payload["action_preview"]["target"] == "tasks"
    assert payload["action_preview"]["payload"]["status"] == "open"
    with app.app_context():
        assert Task.query.count() == 0


def test_ai_chat_answers_machine_count_without_action_preview(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify explicit machine count questions return direct local answers."""
    user = make_user(username="ai_machine_count_user", role=Role.INSTANDHALTUNG)
    make_machine(name="Anlage Count 1")
    make_machine(name="Anlage Count 2")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "wie vile maschinen?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "machines_count"
    assert payload["data"]["count"] == 2
    assert "Gesamt" in payload["answer"]
    assert len(payload["sources"]) == 1
    _assert_aggregate_count_source(payload["sources"][0], "machines", "/machines", 2)
    assert payload["diagnostics"]["source_count"] == 1
    assert payload["answer_quality"]["source_count"] == 1
    assert "action_preview" not in payload


@pytest.mark.parametrize(
    ("scope", "expected_type", "module", "url"),
    [
        ("tasks", "tasks_count", "tasks", "/tasks"),
        ("errors", "errors_count", "errors", "/errors"),
        ("documents", "documents_count", "documents", "/documents"),
        ("inventory", "inventory_count", "inventory", "/inventory"),
    ],
)
def test_ai_count_answers_return_safe_aggregate_source_cards(
    app,
    make_user,
    make_task,
    make_error_entry,
    make_material,
    make_document,
    set_dashboard_permission,
    scope,
    expected_type,
    module,
    url,
):
    """Verify count answers expose one aggregate source card, not row details."""
    from app.ai.services import answer_count_question

    user = make_user(username=f"ai_{scope}_aggregate_count_user")
    set_dashboard_permission(user["username"], scope, can_view=True)
    task_id = make_task("Aggregate Count Task", creator_username=user["username"])
    if scope == "errors":
        make_error_entry("Aggregate Anlage", "AGG-1", "Aggregate Stoerung")
    elif scope == "documents":
        make_document(task_id, created_by=user["id"])
    elif scope == "inventory":
        make_material("Aggregate Lagerteil", 12.5, 3)

    with app.app_context():
        current_user = User.query.filter_by(username=user["username"]).one()
        result = answer_count_question(
            "Wie viele Eintraege gibt es?",
            current_user,
            {scope},
            {scope},
        )

    assert result["type"] == expected_type
    assert result["data"]["count"] == 1
    assert len(result["sources"]) == 1
    _assert_aggregate_count_source(result["sources"][0], module, url, 1)
    assert "description" not in result["sources"][0]
    assert "creator" not in result["sources"][0]
    assert result["diagnostics"]["source_count"] == 1
    assert result["answer_quality"]["source_count"] == 1


def test_ai_chat_employee_count_returns_access_level_aggregate_source(
    client,
    make_user,
    make_employee,
    set_dashboard_permission,
    auth_headers,
):
    """Verify employee count sources include access level and stay scoped."""
    user = make_user(username="ai_employee_count_source_user")
    denied_user = make_user(username="ai_employee_count_denied_user")
    make_employee(
        personnel_number="P-COUNT-1",
        name="Anna Count Produktion",
        department="Produktion",
    )
    make_employee(
        personnel_number="P-COUNT-2",
        name="Bernd Count IT",
        department="IT",
    )
    set_dashboard_permission(
        user["username"],
        "employees",
        can_view=True,
        employee_access_level="basic",
    )
    set_dashboard_permission(denied_user["username"], "employees", can_view=False)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie viele Mitarbeiter gibt es?"},
    )
    denied_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(denied_user["username"]),
        json={"message": "Wie viele Mitarbeiter gibt es?"},
    )

    payload = response.get_json()
    denied_payload = denied_response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "employee_count"
    assert payload["data"]["count"] == 1
    assert len(payload["sources"]) == 1
    _assert_aggregate_count_source(
        payload["sources"][0],
        "employees",
        "/employees",
        1,
        extra_fields={"employee_access_level"},
    )
    assert payload["sources"][0]["employee_access_level"] == "basic"
    assert payload["sources"][0]["role_visibility"] == "department:Produktion"
    assert denied_response.status_code == 200
    assert denied_payload["type"] == "permission_denied"
    assert denied_payload["sources"] == []


def test_ai_count_answer_only_redacts_aggregate_sources_for_normal_users(
    client,
    make_user,
    make_machine,
    set_dashboard_permission,
    auth_headers,
):
    """Verify answer-only mode redacts aggregate count evidence for normal users."""
    user = make_user(username="ai_count_answer_only_user")
    make_machine(name="Answer Only Count Anlage")
    set_dashboard_permission(user["username"], "machines", can_view=True)

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Wie viele Maschinen gibt es?",
            "response_mode": "answer_only",
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "machines_count"
    assert payload["sources"] == []
    assert payload["data"] == {}
    assert payload["evidence_visible"] is False
    assert payload["diagnostics"]["evidence_visible"] is False
    assert payload["answer_quality"]["evidence_visible"] is False


def test_ai_chat_answers_admin_user_count_permission_aware(
    client,
    make_user,
    auth_headers,
):
    """Verify user count is only answered from Admin Users permission."""
    admin = make_user(
        username="ai_user_count_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_user_count_normal")

    admin_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "wie viele user gibt es"},
    )
    user_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "wie viele user gibt es"},
    )

    admin_payload = admin_response.get_json()
    user_payload = user_response.get_json()
    assert admin_response.status_code == 200
    assert admin_payload["type"] == "admin_users_count"
    assert admin_payload["data"]["count"] == 2
    assert len(admin_payload["sources"]) == 1
    _assert_aggregate_count_source(
        admin_payload["sources"][0],
        "admin_users",
        "/admin/users",
        2,
    )
    assert admin_payload["sources"][0]["role_visibility"] == "admin_only"
    assert user_response.status_code == 200
    assert user_payload["type"] == "permission_denied"
    assert user_payload["sources"] == []
    assert "Admin" in user_payload["answer"]


def test_ai_chat_retrieves_admin_user_roles_for_admins_only(
    client,
    make_user,
    auth_headers,
):
    """Verify admin-user role data is a permission-aware structured source."""
    admin = make_user(
        username="ai_role_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_role_normal", role=Role.INSTANDHALTUNG)

    admin_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Welche Rollen und Berechtigungen haben User im System?"},
    )
    user_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Rollen und Berechtigungen haben User im System?"},
    )

    admin_payload = admin_response.get_json()
    user_payload = user_response.get_json()
    admin_sources = admin_payload["sources"]
    admin_user_source = next(source for source in admin_sources if source["type"] == "admin_user")
    serialized_payload = json.dumps(admin_payload, ensure_ascii=True)
    assert admin_response.status_code == 200
    assert admin_payload["type"] == "assistant"
    assert len(admin_payload["data"]["admin_users"]) == 2
    assert {item["username"] for item in admin_payload["data"]["admin_users"]} == {
        "ai_role_admin",
        "ai_role_normal",
    }
    assert "password_hash" not in serialized_payload
    assert admin_user_source["source_kind"] == "structured"
    assert admin_user_source["module"] == "admin_users"
    assert admin_user_source["role_visibility"] == "admin_only"
    assert admin_user_source["role"] in {Role.MASTER_ADMIN.value, Role.INSTANDHALTUNG.value}
    assert user_response.status_code == 200
    assert user_payload["type"] == "permission_denied"
    assert user_payload["sources"] == []


def test_ai_chat_retrieves_shift_handovers_as_structured_sources(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify shift handovers are used as permission-aware structured AI sources."""
    admin = make_user(
        username="ai_handover_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_handover_normal", role=Role.PRODUKTION)
    machine_id = make_machine(name="Handover AI Presse", produced_item="Gehauese")
    headers = auth_headers(admin["username"])
    create_response = client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "Produktion",
            "machine_id": machine_id,
            "shift_date": "2026-07-05",
            "shift_type": "Spaet",
            "status": "open",
            "production_status": "reduced",
            "machine_status": "warning",
            "problem_category": "Hydraulik",
            "content": "Hydraulikdruck schwankt an Handover AI Presse.",
            "open_tasks": "Filterpruefung offen.",
            "machine_notes": "Druckabfall bei Lastwechsel.",
            "next_notes": "Druck in der Nachtschicht eng beobachten.",
        },
    )
    assert create_response.status_code == 201
    handover_id = create_response.get_json()["data"]["id"]

    admin_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Was steht in der Schichtuebergabe zur Handover AI Presse?"},
    )
    user_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was steht in der Schichtuebergabe zur Handover AI Presse?"},
    )

    admin_payload = admin_response.get_json()
    user_payload = user_response.get_json()
    handover_source = next(
        source for source in admin_payload["sources"] if source["type"] == "shift_handover"
    )
    assert admin_response.status_code == 200
    assert admin_payload["type"] == "assistant"
    assert admin_payload["data"]["shift_handovers"][0]["id"] == handover_id
    assert handover_source["source_kind"] == "structured"
    assert handover_source["module"] == "shiftplans"
    assert handover_source["source_record_id"] == handover_id
    assert handover_source["machine_id"] == machine_id
    assert handover_source["role_visibility"] == "department:Produktion"
    assert handover_source["created_at"]
    assert user_response.status_code == 200
    assert user_payload["type"] == "permission_denied"
    assert user_payload["sources"] == []


def test_ai_chat_retrieves_maintenance_plans_as_structured_sources(
    app,
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify maintenance plans are used as permission-aware structured AI sources."""
    admin = make_user(
        username="ai_maintenance_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_maintenance_normal", role=Role.PRODUKTION)
    machine_id = make_machine(name="Wartung AI Presse", produced_item="Deckel")
    with app.app_context():
        department = Department.query.filter_by(name="Produktion").one()
        db.session.add(
            MaintenancePlan(
                title="Hydraulik Wartungsplan KI",
                description="Druckspeicher und Filter an Wartung AI Presse pruefen.",
                interval_days=14,
                next_due_date=date.today() + timedelta(days=3),
                priority=Priority.SOON,
                is_active=True,
                machine_id=machine_id,
                department=department,
                created_by=admin["id"],
            )
        )
        db.session.commit()

    admin_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Welche Wartungsplaene gibt es zur Wartung AI Presse?"},
    )
    user_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Welche Wartungsplaene gibt es zur Wartung AI Presse?"},
    )

    admin_payload = admin_response.get_json()
    user_payload = user_response.get_json()
    plan_source = next(
        source for source in admin_payload["sources"] if source["type"] == "maintenance_plan"
    )
    plan_payload = admin_payload["data"]["maintenance_plans"][0]
    assert admin_response.status_code == 200
    assert admin_payload["type"] == "assistant"
    assert plan_payload["title"] == "Hydraulik Wartungsplan KI"
    assert plan_source["source_kind"] == "structured"
    assert plan_source["module"] == "machines"
    assert plan_source["source_record_id"] == plan_payload["id"]
    assert plan_source["machine_id"] == machine_id
    assert plan_source["role_visibility"] == "department:Produktion"
    assert plan_source["created_at"]
    assert "Predictive" not in json.dumps(admin_payload, ensure_ascii=True)
    assert user_response.status_code == 200
    assert user_payload["type"] == "permission_denied"
    assert user_payload["sources"] == []


def test_ai_chat_uses_hybrid_general_mode_for_non_app_questions(
    client,
    make_user,
    auth_headers,
):
    """Verify general questions get short hybrid answers with tracking notice."""
    user = make_user(username="ai_general_chat_user")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["workflow"] == "general_chat"
    assert payload["sources"] == []
    assert "protokolliert" in payload["answer"]
    assert "Datenbank" not in payload["answer"]


def test_ai_chat_treats_concept_questions_as_general_chat(
    client,
    make_user,
    auth_headers,
):
    """Verify generic concept questions are not blocked as protected app data."""
    user = make_user(username="ai_concept_chat_user")

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist ein User?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["workflow"] == "general_chat"
    assert payload["sources"] == []
    assert "Keine Berechtigung" not in payload["answer"]


def test_ai_chat_general_question_uses_openai_answer_with_tracking_notice(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify successful general chat returns the provider answer plus tracking notice."""

    class SuccessfulGeneralProvider:
        """Fake provider for deterministic general chat tests."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "test-general-model",
        }

        def answer_general_question(self, question):
            """Return a deterministic provider answer."""
            return "## Antwort\n- **Kurz:** Tokio"

    user = make_user(username="ai_openai_general_user")
    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: SuccessfulGeneralProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "openai_used"
    assert payload["answer"].count("protokolliert") == 1
    assert "Tokio" in payload["answer"]
    assert "Lokaler Fallback" not in payload["answer"]


def test_ai_chat_general_fallback_explains_missing_openai_key(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify general chat reacts clearly when OpenAI is selected without a key."""
    user = make_user(username="ai_missing_key_chat_user")
    app.config["AI_PROVIDER"] = "openai"
    app.config["OPENAI_API_KEY"] = ""

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "api_key_missing"
    assert payload["diagnostics"]["fallback_used"] is True
    assert "OPENAI_API_KEY" in payload["answer"]
    assert payload["answer"].count("protokolliert") == 1
    assert "Lokaler Fallback" not in payload["answer"]
    assert "Quelle:" not in payload["answer"]


def test_ai_chat_general_fallback_reports_missing_compatible_base_url(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify OpenAI-compatible fallback reports missing AI_BASE_URL explicitly."""
    user = make_user(username="ai_missing_base_url_chat_user")
    app.config["AI_PROVIDER"] = "openai_compatible"
    app.config["OPENAI_API_KEY"] = "test-key"
    app.config["AI_BASE_URL"] = ""

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "base_url_missing"
    assert payload["diagnostics"]["fallback_used"] is True
    assert "AI_BASE_URL" in payload["answer"]


def test_ai_chat_general_fallback_reports_unsupported_provider(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify unsupported AI providers fall back visibly instead of key errors."""
    user = make_user(username="ai_unsupported_provider_chat_user")
    app.config["AI_PROVIDER"] = "gemini"
    app.config["OPENAI_API_KEY"] = "test-key"

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist die Hauptstadt von Japan?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "unsupported_provider"
    assert payload["diagnostics"]["fallback_used"] is True
    assert "AI_PROVIDER" in payload["answer"]


def test_openai_compatible_provider_uses_configured_base_url(app):
    """Verify OpenAI-compatible providers use the configured local API base URL."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "openai_compatible"
        app.config["OPENAI_API_KEY"] = "test-key"
        app.config["AI_BASE_URL"] = "http://127.0.0.1:11434/v1"

        provider = get_ai_provider()

    assert provider.name == "openai_compatible"
    assert str(provider.client.base_url).rstrip("/") == "http://127.0.0.1:11434/v1"


def test_openai_provider_ignores_local_base_url(app):
    """Verify official OpenAI mode does not inherit local compatible base URLs."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "openai"
        app.config["OPENAI_API_KEY"] = "test-key"
        app.config["AI_BASE_URL"] = "http://127.0.0.1:11434/v1"

        provider = get_ai_provider()

    assert provider.name == "openai"
    assert str(provider.client.base_url).rstrip("/") != "http://127.0.0.1:11434/v1"


def test_unsupported_ai_provider_falls_back_to_mock(app):
    """Verify unsupported providers stay safe until dedicated adapters exist."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "gemini"
        app.config["OPENAI_API_KEY"] = "test-key"

        provider = get_ai_provider()

    assert provider.name == "mock"


def test_ai_chat_general_openai_error_returns_short_tracked_message(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify provider failures do not create duplicate visible fallback text."""

    class FailingGeneralProvider:
        """Fake provider that simulates an OpenAI text failure."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "test-general-model",
        }

        def answer_general_question(self, question):
            """Raise the provider error expected by the chat service."""
            raise AIServiceError("provider failed")

    user = make_user(username="ai_openai_error_general_user")
    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: FailingGeneralProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie ist das Wetter heute?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "openai_error"
    assert payload["diagnostics"]["fallback_used"] is True
    assert payload["answer"].count("protokolliert") == 1
    assert "OpenAI ist gerade nicht erreichbar" in payload["answer"]
    assert "Lokaler Fallback" not in payload["answer"]
    assert "Quelle:" not in payload["answer"]


def test_ai_chat_uses_short_session_context_for_references(
    app,
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify referential chat turns receive bounded same-session context."""
    captured = {}

    class ContextAwareProvider:
        """Fake provider that records the prompt context."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "chat",
            "model": "test-context-model",
        }

        def answer_question(self, question, context, workflow="chat"):
            """Record contextual prompt inputs and return a deterministic answer."""
            captured["question"] = question
            captured["context"] = context
            captured["workflow"] = workflow
            return "## Antwort\n- **Status:** Kontext verstanden"

        def answer_general_question(self, question):
            """Record unexpected general fallback calls."""
            captured["general_question"] = question
            return "## Antwort\n- **Status:** Allgemein"

    admin = make_user(
        username="ai_context_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        db.session.add(
            ChatMessage(
                user_id=admin["id"],
                session_id="ctx-main",
                message="Fehler E104 an Presse 3: Was ist die L\u00f6sung?",
                response=(
                    "## Fehlerhilfe\n"
                    "- **Pr\u00fcfung:** Sensor reinigen und Abstand kontrollieren."
                ),
                response_type="error_help",
                diagnostics_json=json.dumps({"scopes": ["errors", "machines"]}),
                source_count=1,
            )
        )
        db.session.commit()

    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: ContextAwareProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={
            "message": "Was war die vorherige L\u00f6sung fuer den Fehler von eben?",
            "session_id": "ctx-main",
        },
    )

    payload = response.get_json()
    context_diagnostics = payload["diagnostics"]["conversation_context"]
    with app.app_context():
        saved = db.session.get(ChatMessage, payload["chat_message_id"])

    assert response.status_code == 200
    assert captured["workflow"] == "chat"
    assert "Kurzzeit-Gespraechskontext" in captured["context"]
    assert "Presse 3" in captured["context"]
    assert "E104" in captured["context"]
    assert "Sensor reinigen" in captured["context"]
    assert context_diagnostics["reference_detected"] is True
    assert context_diagnostics["applied"] is True
    assert context_diagnostics["message_count"] == 1
    assert saved.session_id == "ctx-main"


def test_ai_chat_context_is_scoped_to_session(
    app,
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify prior messages from another session are not used as memory."""
    captured = {}

    class GeneralProvider:
        """Fake provider that records whether context was supplied."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "test-context-model",
        }

        def answer_question(self, question, context, workflow="chat"):
            """Record contextual calls."""
            captured["context"] = context
            return "## Antwort\n- **Status:** Kontext"

        def answer_general_question(self, question):
            """Record general calls when no context is available."""
            captured["general_question"] = question
            return "## Antwort\n- **Status:** Kein Kontext"

    user = make_user(username="ai_context_session_user")
    with app.app_context():
        db.session.add(
            ChatMessage(
                user_id=user["id"],
                session_id="other-session",
                message="Fehler E999 an Presse 9",
                response="- **Pruefung:** Andere Maschine pruefen.",
                response_type="error_help",
                diagnostics_json=json.dumps({"scopes": ["errors", "machines"]}),
                source_count=1,
            )
        )
        db.session.commit()

    monkeypatch.setattr("app.ai.services.get_ai_provider", lambda: GeneralProvider())

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={
            "message": "Was war die vorherige L\u00f6sung?",
            "session_id": "current-session",
        },
    )

    payload = response.get_json()
    context_diagnostics = payload["diagnostics"]["conversation_context"]

    assert response.status_code == 200
    assert "general_question" in captured
    assert "context" not in captured
    assert context_diagnostics["reference_detected"] is True
    assert context_diagnostics["applied"] is False
    assert context_diagnostics["message_count"] == 0


def test_conversation_context_rechecks_permissions_for_legacy_scoped_messages(
    app,
    make_user,
    set_dashboard_permission,
):
    """Verify legacy unscoped chat history is inferred and permission-filtered."""
    user = make_user(username="ai_context_permission_user", role=Role.INSTANDHALTUNG)
    set_dashboard_permission(user["username"], "errors", can_view=False)

    with app.app_context():
        db.session.add(
            ChatMessage(
                user_id=user["id"],
                session_id="legacy-denied",
                message="Fehler E104 an Presse 3",
                response="Sensor reinigen und Abstand kontrollieren.",
                response_type="error_help",
                diagnostics_json="{}",
                source_count=1,
            )
        )
        db.session.commit()

        context = conversation_context_for_chat(
            db.session.get(User, user["id"]),
            "Was war der Fehler von eben?",
            "legacy-denied",
        )

    assert context.reference_detected is True
    assert context.applied is False
    assert context.message_count == 0
    assert context.error_codes == ()


def test_ai_chat_general_model_error_is_diagnosed(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify unavailable models are exposed as a precise safe diagnostic."""

    class ModelErrorProvider:
        """Fake provider that simulates a model access error."""

        name = "openai"
        last_call_metadata = {
            "provider": "openai",
            "workflow": "general_chat",
            "model": "blocked-model",
        }

        def answer_general_question(self, question):
            """Raise a model diagnostic error."""
            raise AIServiceError("provider failed", error_code="model_not_found")

    user = make_user(username="ai_model_error_general_user")
    monkeypatch.setattr(
        "app.ai.services.get_ai_provider",
        lambda: ModelErrorProvider(),
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist ein User?"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "general_chat"
    assert payload["diagnostics"]["status"] == "openai_error"
    assert payload["diagnostics"]["error"] == "model_not_found"
    assert "Modell" in payload["answer"]
    assert payload["answer"].count("protokolliert") == 1


def test_admin_ai_summary_is_admin_only(
    client,
    make_user,
    auth_headers,
):
    """Verify AI analytics summary is restricted to master admins."""
    admin = make_user(
        username="ai_summary_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_summary_user")

    forbidden_response = client.get(
        "/api/v1/admin/ai/summary",
        headers=auth_headers(user["username"]),
    )
    forbidden_user_metrics_response = client.get(
        "/api/v1/admin/ai/users",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/summary",
        headers=auth_headers(admin["username"]),
    )
    admin_user_metrics_response = client.get(
        "/api/v1/admin/ai/users",
        headers=auth_headers(admin["username"]),
    )

    assert forbidden_response.status_code == 403
    assert forbidden_user_metrics_response.status_code == 403
    assert admin_response.status_code == 200
    assert admin_user_metrics_response.status_code == 200
    assert set(admin_response.get_json().keys()) >= {
        "average_latency_ms",
        "estimated_cost_usd",
        "events_total",
        "fallback_count",
        "feedback",
        "langfuse_metrics",
        "latest_events",
        "price_configuration",
        "total_tokens",
        "user_metrics",
        "workflow_metrics",
    }
    assert "items" in admin_user_metrics_response.get_json()["data"]


def test_ai_analytics_summary_reports_ops_readiness(app, make_user):
    """Verify AI summary exposes demo-ready operational KPIs."""
    user = make_user(username="ai_ops_summary_user")
    with app.app_context():
        actor = type("UserRef", (), {"id": user["id"]})()
        create_ai_audit_event(
            actor,
            "task_suggestion",
            {
                "status": "openai_used",
                "input_tokens": 80,
                "cached_tokens": 20,
                "output_tokens": 20,
                "total_tokens": 100,
                "latency_ms": 200,
                "estimated_cost_usd": 0.01,
            },
        )
        create_ai_audit_event(
            actor,
            "general_chat",
            {
                "status": "openai_error",
                "error": "rate_limit",
                "fallback_used": True,
                "input_tokens": 40,
                "output_tokens": 10,
                "total_tokens": 50,
                "latency_ms": 1200,
                "estimated_cost_usd": 0.005,
            },
        )
        create_ai_audit_event(
            actor,
            "general_chat",
            {
                "status": "local_answer",
                "fallback_used": True,
            },
        )
        db.session.commit()

        summary = ai_analytics_summary(days=7)

    assert summary["fallback_rate"] == 0.67
    assert summary["error_rate"] == 0.33
    assert summary["cache_rate"] == 0.17
    assert summary["cost_per_1k_tokens"] == 0.1
    assert summary["price_configuration"]["message"] == "Kosten nicht konfiguriert"
    assert summary["user_metrics"][0]["username"] == user["username"]
    assert summary["user_metrics"][0]["langfuse_user_id"] == f"user:{user['id']}"
    assert summary["user_metrics"][0]["estimated_cost_usd"] == 0.015
    assert summary["top_workflows"][0]["workflow"] == "general_chat"
    assert summary["top_workflows"][0]["errors"] == 1
    assert summary["top_errors"][0] == {"error_category": "rate_limit", "count": 1}
    assert summary["readiness"]["status"] == "critical"
    assert summary["readiness"]["reasons"]
    assert "retrieval_quality" in summary


def test_ai_user_usage_metrics_group_costs_by_user(app, make_user):
    """Verify AI usage and costs are grouped by app user for admin reporting."""
    first_user = make_user(username="ai_cost_first_user")
    second_user = make_user(username="ai_cost_second_user")
    with app.app_context():
        first_actor = type("UserRef", (), {"id": first_user["id"]})()
        second_actor = type("UserRef", (), {"id": second_user["id"]})()
        create_ai_audit_event(
            first_actor,
            "chat",
            {
                "status": "openai_used",
                "input_tokens": 100,
                "output_tokens": 50,
                "total_tokens": 150,
                "estimated_cost_usd": 0.003,
            },
        )
        create_ai_audit_event(
            first_actor,
            "general_chat",
            {
                "status": "openai_error",
                "fallback_used": True,
                "input_tokens": 20,
                "output_tokens": 10,
                "total_tokens": 30,
                "estimated_cost_usd": 0.001,
                "error": "rate_limit",
            },
        )
        create_ai_audit_event(
            second_actor,
            "chat",
            {
                "status": "openai_used",
                "input_tokens": 40,
                "output_tokens": 10,
                "total_tokens": 50,
                "estimated_cost_usd": 0.01,
            },
        )
        db.session.commit()

        metrics = ai_user_usage_metrics(days=7, limit=10)

    assert metrics[0]["username"] == second_user["username"]
    assert metrics[0]["estimated_cost_usd"] == 0.01
    first_metrics = next(item for item in metrics if item["user_id"] == first_user["id"])
    assert first_metrics["langfuse_user_id"] == f"user:{first_user['id']}"
    assert first_metrics["events"] == 2
    assert first_metrics["fallback_rate"] == 0.5
    assert first_metrics["error_rate"] == 0.5
    assert first_metrics["total_tokens"] == 180
    assert first_metrics["estimated_cost_usd"] == 0.004


def test_retrieval_quality_analytics_aggregates_prompt_safe_signals(app, make_user):
    """Verify retrieval telemetry aggregates quality signals without raw content."""
    user = make_user(username="retrieval_telemetry_user")

    with app.app_context():
        used_document = KnowledgeDocument(
            source_type="upload",
            title="Telemetry Used Source",
            original_filename="used.txt",
            relative_path="uploads/used.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="admin_approved",
            is_public=True,
            chunk_count=1,
        )
        unused_document = KnowledgeDocument(
            source_type="upload",
            title="Telemetry Unused Source",
            original_filename="unused.txt",
            relative_path="uploads/unused.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="admin_approved",
            is_public=True,
            chunk_count=1,
        )
        db.session.add_all([used_document, unused_document])
        db.session.flush()
        used_text = "Sensitive used chunk text must not appear in telemetry."
        unused_text = "Sensitive unused chunk text must not appear in telemetry."
        used_chunk = KnowledgeChunk(
            document_id=used_document.id,
            chunk_index=0,
            text=used_text,
            token_text="telemetry used",
        )
        unused_chunk = KnowledgeChunk(
            document_id=unused_document.id,
            chunk_index=0,
            text=unused_text,
            token_text="telemetry unused",
            entities_json=json.dumps(
                {
                    "_chunk_metadata": {
                        "chunk_char_count": len(unused_text),
                        "chunk_line_count": 1,
                        "chunk_token_count": 8,
                        "chunk_block_count": 2,
                        "chunk_block_kinds": "list,paragraph",
                        "chunking_mode": "hybrid_semantic",
                        "section_title": "Unused Maintenance Notes",
                    }
                },
                ensure_ascii=True,
            ),
        )
        db.session.add_all([used_chunk, unused_chunk])
        db.session.flush()
        used_document_id = used_document.id
        used_chunk_id = used_chunk.id
        unused_chunk_id = unused_chunk.id
        source_payload = {
            "type": "knowledge",
            "id": used_document_id,
            "source_record_id": 44,
            "source_kind": "rag",
            "knowledge_source_type": "machine_manual",
            "module": "knowledge",
            "machine_id": 12,
            "role_visibility": "department:Produktion",
            "created_at": "2026-05-30T10:00:00",
            "chunk_id": used_chunk_id,
            "score": 12,
            "explainability": {
                "quality_status": "admin_approved",
                "final_score": 12,
            },
        }
        create_ai_audit_event(
            user=type("UserStub", (), {"id": user["id"]})(),
            workflow="general_chat",
            diagnostics={
                "status": "openai_used",
                "confidence_score": 82,
                "retrieval_explainability": {
                    "source_count": 1,
                    "explained_source_count": 1,
                    "retrieval_debug": {
                        "top_k": 4,
                        "rerank_candidate_limit": 20,
                        "vector_candidates_found": 10,
                        "final_visible_sources": 1,
                    },
                    "sources": [source_payload],
                },
            },
            source_count=1,
        )
        create_ai_audit_event(
            user=type("UserStub", (), {"id": user["id"]})(),
            workflow="general_chat",
            diagnostics={
                "status": "local_answer",
                "confidence_score": 18,
            },
            source_count=0,
        )
        db.session.add(
            AIFeedback(
                user_id=user["id"],
                prompt="Sensitive prompt must not appear.",
                response="Sensitive answer must not appear.",
                response_type="assistant",
                rating="not_helpful",
                sources_json=json.dumps(
                    [
                        {
                            "type": "knowledge",
                            "id": used_document_id,
                            "chunk_id": used_chunk_id,
                            "title": used_document.title,
                            "score": 12,
                        }
                    ],
                    ensure_ascii=True,
                ),
                source_count=1,
            )
        )
        db.session.add(
            KnowledgeGap(
                question="Sensitive gap question must not appear.",
                question_hash="a" * 64,
                occurrence_count=4,
                status="open",
                machine="Presse 3",
                department="Produktion",
                user_id=user["id"],
            )
        )
        db.session.commit()

        telemetry = retrieval_quality_analytics(days=30, limit=5)

    top_source = telemetry["source_usage"]["top_sources"][0]
    poor_source = telemetry["poor_sources"][0]
    top_gap = telemetry["knowledge_gaps"]["top_gaps"][0]
    unused_sample = telemetry["unused_chunks"]["sample"]
    telemetry_text = json.dumps(telemetry, ensure_ascii=True)

    assert top_source["id"] == used_document_id
    assert top_source["audit_uses"] == 1
    assert top_source["source_record_id"] == 44
    assert top_source["source_kind"] == "rag"
    assert top_source["knowledge_source_type"] == "machine_manual"
    assert top_source["machine_id"] == 12
    assert top_source["role_visibility"] == "department:Produktion"
    assert telemetry["source_usage"]["source_kind_distribution"]["rag"] == 1
    assert poor_source["not_helpful_feedback"] == 1
    assert poor_source["source_record_id"] == 44
    assert poor_source["source_kind"] == "rag"
    assert poor_source["knowledge_source_type"] == "machine_manual"
    assert telemetry["unsuccessful_questions"]["no_source_events"] == 1
    assert telemetry["unsuccessful_questions"]["low_confidence_events"] == 1
    assert telemetry["reranking"]["request_count"] == 1
    assert telemetry["reranking"]["average_candidate_limit"] == 20
    assert telemetry["reranking"]["average_candidate_count"] == 10
    assert telemetry["reranking"]["average_final_top_k"] == 4
    assert telemetry["reranking"]["average_final_source_count"] == 1
    assert telemetry["reranking"]["average_reduction_rate"] == 0.9
    assert top_gap["question_hash"] == "a" * 64
    assert "question" not in top_gap
    assert telemetry["negative_feedback"]["total"] == 1
    unused_item = next(item for item in unused_sample if item["chunk_id"] == unused_chunk_id)
    assert telemetry["unused_chunks"]["chunk_size_metrics"]["measured_chunk_count"] == 1
    assert telemetry["unused_chunks"]["chunk_size_metrics"]["average_char_count"] == len(
        unused_text
    )
    assert telemetry["unused_chunks"]["chunk_size_metrics"]["average_token_count"] == 8
    assert telemetry["unused_chunks"]["chunk_size_metrics"]["average_block_count"] == 2
    assert telemetry["unused_chunks"]["chunk_size_metrics"]["max_block_count"] == 2
    block_kind_distribution = {
        item["key"]: item["count"]
        for item in telemetry["unused_chunks"]["chunk_size_metrics"]["block_kind_distribution"]
    }
    assert block_kind_distribution["list"] == 1
    assert block_kind_distribution["paragraph"] == 1
    assert unused_item["chunk_char_count"] == len(unused_text)
    assert unused_item["chunk_line_count"] == 1
    assert unused_item["chunk_token_count"] == 8
    assert unused_item["chunk_block_count"] == 2
    assert unused_item["chunk_block_kinds"] == ["list", "paragraph"]
    assert unused_item["chunking_mode"] == "hybrid_semantic"
    assert unused_item["section_title"] == "Unused Maintenance Notes"
    assert "Sensitive prompt" not in telemetry_text
    assert "Sensitive answer" not in telemetry_text
    assert "Sensitive used chunk text" not in telemetry_text


def test_retrieval_slo_metrics_aggregate_operational_signals(app, make_user):
    """Verify retrieval SLO metrics combine audit, feedback, safety, and drift signals."""
    user = make_user(username="retrieval_slo_user")
    clear_vector_sync_observability()
    try:
        with app.app_context():
            stale_document = KnowledgeDocument(
                source_type="upload",
                title="SLO stale source",
                original_filename="slo-stale.txt",
                relative_path="uploads/slo-stale.txt",
                content_type="text/plain",
                department="Produktion",
                status="stale",
                quality_status="admin_approved",
                is_public=True,
                chunk_count=1,
            )
            db.session.add(stale_document)
            db.session.flush()
            record_vector_sync_failure(
                stale_document.id,
                "chroma",
                RuntimeError("sync failed"),
            )
            actor = type("UserStub", (), {"id": user["id"]})()
            create_ai_audit_event(
                user=actor,
                workflow="assistant",
                diagnostics={
                    "status": "openai_used",
                    "confidence_score": 82,
                    "retrieval_explainability": {
                        "retrieval_duration_ms": 100,
                        "safety": {"safety_relevant": False},
                    },
                },
                requested_scopes={"documents"},
                allowed_scopes={"documents"},
                source_count=1,
            )
            create_ai_audit_event(
                user=actor,
                workflow="assistant",
                diagnostics={
                    "status": "fallback_used",
                    "fallback_used": True,
                    "confidence_score": 20,
                    "retrieval_explainability": {
                        "retrieval_duration_ms": 1500,
                        "safety": {
                            "safety_relevant": True,
                            "risk_level": "high",
                            "categories": ["electrical_hazard"],
                        },
                    },
                },
                requested_scopes={"documents", "employees"},
                allowed_scopes={"documents"},
                source_count=0,
            )
            db.session.add_all(
                [
                    AIFeedback(
                        user_id=user["id"],
                        prompt="Prompt must not appear",
                        response="Answer must not appear",
                        response_type="assistant",
                        rating="not_helpful",
                        sources_json="[]",
                        source_count=0,
                    ),
                    AIFeedback(
                        user_id=user["id"],
                        prompt="Other prompt must not appear",
                        response="Other answer must not appear",
                        response_type="assistant",
                        rating="helpful",
                        sources_json="[]",
                        source_count=0,
                    ),
                ]
            )
            db.session.commit()

            telemetry = retrieval_quality_analytics(days=30, limit=5)
    finally:
        clear_vector_sync_observability()

    slo = telemetry["retrieval_slo"]
    values = slo["last_values"]
    assert values["retrieval_p95_ms"] == 1500
    assert values["no_source_rate"] == 0.5
    assert values["low_confidence_rate"] == 0.5
    assert values["permission_filtered_candidate_count"] == 1
    assert values["negative_feedback_rate"] == 0.5
    assert values["safety_risk_count"] == 1
    assert values["fallback_rate"] == 0.5
    assert values["vector_sync_failure_count"] == 1
    assert values["stale_index_count"] == 1
    assert slo["status"] == "critical"
    assert slo["trends"]["retrieval_p95_ms"]["direction"] == "up"
    assert "Prompt must not appear" not in json.dumps(slo, ensure_ascii=True)


def test_retrieval_slo_metrics_warn_on_source_metadata_gaps(app, make_user):
    """Verify retrieval SLOs flag incomplete public source metadata."""
    user = make_user(username="retrieval_slo_metadata_gap_user")
    with app.app_context():
        actor = type("UserStub", (), {"id": user["id"]})()
        create_ai_audit_event(
            user=actor,
            workflow="assistant",
            diagnostics={
                "status": "openai_used",
                "retrieval_explainability": {
                    "retrieval_duration_ms": 120,
                    "sources": [
                        {
                            "type": "knowledge",
                            "id": 10,
                            "source_type": "upload",
                            "source_id": 10,
                            "title": "Complete public metadata",
                            "module": "knowledge",
                            "role_visibility": "public",
                            "created_at": "2026-05-30T10:00:00",
                        },
                        {
                            "type": "knowledge",
                            "id": 11,
                            "title": "Missing derived metadata",
                        },
                    ],
                },
            },
            requested_scopes={"documents"},
            allowed_scopes={"documents"},
            source_count=2,
        )
        db.session.commit()

        telemetry = retrieval_quality_analytics(days=30, limit=5)

    slo = telemetry["retrieval_slo"]
    values = slo["last_values"]
    metadata_warning = next(
        warning
        for warning in slo["warnings"]
        if warning["metric"] == "source_metadata_missing_rate"
    )
    assert values["source_metadata_missing_rate"] == 0.5
    missing_fields = {
        item["field"]: item["count"] for item in values["source_metadata_missing_fields"]
    }
    assert missing_fields == {
        "module": 1,
        "role_visibility": 1,
        "created_at": 1,
    }
    assert metadata_warning["status"] == "critical"
    assert "Complete public metadata" not in json.dumps(slo, ensure_ascii=True)


def test_ai_observability_exposes_retrieval_slo_metadata_gap_warning(app, make_user):
    """Verify AI observability surfaces retrieval SLO metadata-gap warnings."""
    user = make_user(username="ai_observability_slo_gap_user")
    with app.app_context():
        actor = type("UserStub", (), {"id": user["id"]})()
        create_ai_audit_event(
            user=actor,
            workflow="assistant",
            diagnostics={
                "status": "openai_used",
                "retrieval_explainability": {
                    "retrieval_duration_ms": 100,
                    "sources": [
                        {
                            "type": "knowledge",
                            "id": 21,
                            "source_type": "upload",
                            "source_id": 21,
                            "module": "knowledge",
                            "role_visibility": "public",
                            "created_at": "2026-05-30T10:00:00",
                        },
                        {"type": "knowledge", "id": 22},
                    ],
                },
            },
            requested_scopes={"documents"},
            allowed_scopes={"documents"},
            source_count=2,
        )
        db.session.commit()

        dashboard = ai_observability_dashboard({"days": "30", "limit": "5"})

    retrieval_slo = dashboard["metrics"]["retrieval_slo"]
    metadata_warning = next(
        warning
        for warning in dashboard["metrics"]["retrieval_slo_warnings"]
        if warning["metric"] == "source_metadata_missing_rate"
    )
    assert dashboard["metrics"]["telemetry_status"] == "critical"
    assert retrieval_slo["status"] == "critical"
    assert retrieval_slo["source_metadata_missing_rate"] == 0.5
    missing_fields = {
        item["field"]: item["count"] for item in retrieval_slo["source_metadata_missing_fields"]
    }
    assert missing_fields == {
        "module": 1,
        "role_visibility": 1,
        "created_at": 1,
    }
    assert retrieval_slo["warning_count"] >= 1
    assert metadata_warning["status"] == "critical"


def test_retrieval_slo_metrics_handle_empty_data(app):
    """Verify retrieval SLO metrics return safe defaults for empty telemetry."""
    clear_vector_sync_observability()
    with app.app_context():
        telemetry = retrieval_quality_analytics(days=7, limit=5)

    slo = telemetry["retrieval_slo"]
    assert slo["status"] == "ok"
    assert slo["last_values"]["event_count"] == 0
    assert slo["last_values"]["retrieval_p95_ms"] == 0
    assert slo["last_values"]["no_source_rate"] == 0.0
    assert slo["warnings"] == []


def test_ai_observability_dashboard_combines_logs_quality_and_retrieval(
    app,
    make_user,
    make_error_entry,
):
    """Verify AI observability combines monitoring metrics and bounded debug data."""
    user = make_user(username="ai_observability_user")
    make_error_entry(
        "FU",
        "FU-000",
        "Unbekannter FU Fehler",
        description="FU Fehler ohne ausreichende Dokumentation.",
    )
    with app.app_context():
        document = KnowledgeDocument(
            source_type="upload",
            title="Observability Motor FU",
            original_filename="observability.txt",
            relative_path="uploads/observability.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="admin_approved",
            is_public=True,
            chunk_count=1,
        )
        db.session.add(document)
        db.session.flush()
        actor = type("UserStub", (), {"id": user["id"]})()
        audit_id = create_ai_audit_event(
            user=actor,
            workflow="assistant",
            diagnostics={
                "status": "openai_used",
                "latency_ms": 240,
                "input_tokens": 200,
                "output_tokens": 120,
                "total_tokens": 320,
                "estimated_cost_usd": 0.012,
                "confidence_score": 84,
                "confidence_level": "high",
                "retrieval_explainability": {
                    "retrieval_duration_ms": 42,
                    "retrieval_debug": {
                        "top_k": 4,
                        "rerank_candidate_limit": 20,
                        "vector_candidates_found": 12,
                        "final_visible_sources": 1,
                    },
                    "sources": [
                        {
                            "type": "knowledge",
                            "id": document.id,
                            "title": "Observability Motor FU",
                            "source_record_id": 123,
                            "source_kind": "rag",
                            "knowledge_source_type": "machine_manual",
                            "module": "knowledge",
                            "machine_id": 456,
                            "role_visibility": "department:Produktion",
                            "employee_access_level": "confidential",
                            "created_at": "2000-01-01T00:00:00",
                            "chunk_id": 77,
                            "score": 88,
                            "section_title": "FU Diagnose",
                            "explainability": {
                                "semantic_similarity": 0.82,
                                "final_score": 88,
                                "quality_status": "admin_approved",
                            },
                        },
                        {
                            "type": "knowledge",
                            "id": document.id,
                            "title": "Observability undated FU",
                            "source_record_id": 124,
                            "source_kind": "rag",
                            "knowledge_source_type": "machine_manual",
                            "module": "knowledge",
                            "machine_id": 456,
                            "role_visibility": "department:Produktion",
                            "chunk_id": 78,
                            "score": 20,
                            "section_title": "FU ohne Datum",
                            "explainability": {
                                "semantic_similarity": 0.82,
                            },
                        },
                    ],
                    "context_builder": {
                        "sections": [
                            {
                                "label": "Knowledge",
                                "source_count": 1,
                                "used_chars": 180,
                            }
                        ],
                        "stats": {"used_chars": 180, "max_chars": 2000},
                    },
                    "query_understanding": {"query_type": "document_question"},
                },
            },
            requested_scopes={"documents"},
            allowed_scopes={"documents"},
            source_count=1,
        )
        sourced_chat = ChatMessage(
            user_id=user["id"],
            message="Welche Dokumente helfen beim FU Fehler?",
            response="Dokument Observability Motor FU nutzen.",
            response_type="assistant",
            diagnostics_json=json.dumps(
                {
                    "confidence_score": 84,
                    "confidence_level": "high",
                    "quality_warnings": [],
                },
                ensure_ascii=True,
            ),
            source_count=1,
            confidence_score=84,
            confidence_level="high",
            audit_event_id=audit_id,
        )
        db.session.add(sourced_chat)
        db.session.add(
            ChatMessage(
                user_id=user["id"],
                message="Welche Quellen widersprechen sich beim FU Fehler?",
                response="Zwei Quellen nennen unterschiedliche naechste Schritte.",
                response_type="assistant",
                diagnostics_json=json.dumps(
                    {
                        "confidence_score": 78,
                        "confidence_level": "high",
                        "source_conflicts": {
                            "has_conflicts": True,
                            "count": 1,
                            "summary": "1 potenzielle Quellenkonflikte erkannt.",
                        },
                        "quality_warnings": [{"type": "source_conflict"}],
                    },
                    ensure_ascii=True,
                ),
                source_count=1,
                confidence_score=78,
                confidence_level="high",
            )
        )
        db.session.add(
            ChatMessage(
                user_id=user["id"],
                message="Welche Ursache hat der unbekannte Fehler FU-000?",
                response="Keine belegte Antwort vorhanden.",
                response_type="assistant",
                diagnostics_json=json.dumps(
                    {
                        "confidence_score": 18,
                        "confidence_level": "low",
                        "empty_retrieval": True,
                        "hallucination_warning": True,
                        "knowledge_gap_id": 321,
                        "knowledge_gap_created": True,
                        "quality_warnings": [
                            {"type": "empty_retrieval"},
                            {"type": "hallucination_risk"},
                        ],
                    },
                    ensure_ascii=True,
                ),
                source_count=0,
                confidence_score=18,
                confidence_level="low",
            )
        )
        db.session.flush()
        db.session.add(
            AIFeedback(
                user_id=user["id"],
                chat_message_id=sourced_chat.id,
                audit_event_id=audit_id,
                prompt="Welche Dokumente helfen beim FU Fehler?",
                response="Dokument Observability Motor FU nutzen.",
                response_type="assistant",
                rating="not_helpful",
                sources_json="[]",
                source_count=1,
            )
        )
        db.session.add(
            AIFeedback(
                user_id=user["id"],
                prompt="Welche Dokumente helfen beim FU Fehler?",
                response="Dokument Observability Motor FU nutzen.",
                response_type="assistant",
                rating="helpful",
                sources_json="[]",
                source_count=1,
            )
        )
        db.session.add(
            KnowledgeGap(
                question="Welche FU Dokumentation fehlt?",
                question_hash="b" * 64,
                occurrence_count=2,
                status="open",
                machine="FU",
                department="Produktion",
                user_id=user["id"],
            )
        )
        db.session.add(
            RetrievalEvaluationRun(
                query_count=4,
                recall_at_k=0.75,
                mrr=0.5,
                ndcg_at_k=0.625,
                keyword_query_count=2,
                keyword_hit_rate=0.5,
                permission_leak_count=1,
                forbidden_source_hit_count=1,
                no_result_count=1,
                no_result_rate=0.25,
                expected_no_result_count=1,
                expected_no_result_success_count=1,
                expected_no_result_success_rate=1.0,
                unexpected_no_result_count=1,
                unexpected_no_result_rate=0.3333,
                min_source_count_fail_count=1,
                min_source_count_pass_rate=0.75,
                query_type_expected_count=3,
                query_type_match_count=2,
                query_type_accuracy=0.6667,
                source_metadata_count=4,
                source_id_coverage_rate=1.0,
                source_type_coverage_rate=1.0,
                source_pair_coverage_rate=0.75,
                metadata_pair_coverage_rate=0.5,
            )
        )
        db.session.commit()

        dashboard = ai_observability_dashboard(
            {"days": "30", "limit": "5", "chat_message_id": str(sourced_chat.id)}
        )

    assert dashboard["metrics"]["average_response_ms"] == 240
    assert dashboard["metrics"]["p95_response_ms"] == 240
    assert dashboard["metrics"]["average_retrieval_ms"] == 42
    assert dashboard["metrics"]["p95_retrieval_ms"] == 42
    assert dashboard["metrics"]["average_final_top_k"] == 1
    assert dashboard["metrics"]["average_tokens"] == 320
    assert dashboard["metrics"]["provider_ready"] is True
    assert dashboard["metrics"]["provider_readiness_status"] == "ok"
    assert dashboard["metrics"]["provider_degraded_component_count"] == 0
    assert dashboard["metrics"]["provider_next_action_type"] == ""
    assert dashboard["metrics"]["cost_windows"]["month"] == 0.012
    assert dashboard["metrics"]["price_configuration"]["message"] == "Kosten nicht konfiguriert"
    assert dashboard["metrics"]["failed_request_count"] == 0
    assert dashboard["metrics"]["retrieval_hit_rate"] == 1
    assert dashboard["metrics"]["source_freshness"]["stale_source_count"] == 1
    assert dashboard["metrics"]["stale_source_count"] == 1
    assert dashboard["metrics"]["stale_source_rate"] == 1
    assert dashboard["metrics"]["undated_source_count"] == 1
    assert dashboard["metrics"]["retrieval_action_count"] == 3
    assert dashboard["metrics"]["retrieval_critical_action_count"] == 0
    assert dashboard["metrics"]["retrieval_high_action_count"] == 1
    assert dashboard["metrics"]["evaluation_action_count"] == 4
    assert dashboard["metrics"]["evaluation_critical_action_count"] == 1
    assert dashboard["metrics"]["evaluation_high_action_count"] == 1
    assert dashboard["metrics"]["evaluation_quality_gate_status"] == "fail"
    assert dashboard["metrics"]["evaluation_quality_gate_passed"] is False
    assert dashboard["metrics"]["evaluation_blocking_count"] == 2
    assert dashboard["metrics"]["evaluation_warning_count"] >= 1
    assert dashboard["metrics"]["evaluation_quality_gate_issue_count"] == (
        dashboard["metrics"]["evaluation_blocking_count"]
        + dashboard["metrics"]["evaluation_warning_count"]
    )
    assert dashboard["metrics"]["source_metadata_gap_count"] == 2
    assert dashboard["metrics"]["source_metadata_gap_fields"] == [
        "source_pair",
        "metadata_pair",
    ]
    assert dashboard["metrics"]["source_metadata_min_coverage_rate"] == 0.5
    assert dashboard["metrics"]["empty_retrieval_count"] == 1
    assert dashboard["metrics"]["no_answer_count"] == 1
    assert dashboard["metrics"]["no_answer_rate"] == 0.3333
    assert dashboard["metrics"]["source_conflict_count"] == 1
    assert dashboard["metrics"]["source_conflict_rate"] == 0.3333
    assert dashboard["metrics"]["answer_quality_distribution"] == {
        "grounded": 1,
        "conflicting_sources": 1,
        "no_answer": 1,
    }
    answer_quality_rows = {
        row["status"]: row for row in dashboard["metrics"]["answer_quality_distribution_rows"]
    }
    assert answer_quality_rows["grounded"]["rate"] == 0.3333
    assert answer_quality_rows["conflicting_sources"]["count"] == 1
    assert dashboard["metrics"]["answer_quality_reason_distribution"] == {
        "sources_available": 1,
        "source_conflict_detected": 1,
        "empty_retrieval_hallucination_guard": 1,
    }
    reason_rows = {
        row["status_reason"]: row
        for row in dashboard["metrics"]["answer_quality_reason_distribution_rows"]
    }
    assert reason_rows["source_conflict_detected"]["count"] == 1
    assert reason_rows["empty_retrieval_hallucination_guard"]["rate"] == 0.3333
    answer_quality_actions = {
        action["type"]: action for action in dashboard["metrics"]["answer_quality_actions"]
    }
    assert dashboard["metrics"]["answer_quality_action_count"] == 2
    assert answer_quality_actions["review_no_answer_guarded_questions"]["priority"] == "high"
    assert answer_quality_actions["review_no_answer_guarded_questions"]["count"] == 1
    assert (
        answer_quality_actions["review_conflicting_answer_sources"]["target"]
        == "source_conflict_detected"
    )
    answer_quality_action_summary = dashboard["metrics"]["answer_quality_action_summary"]
    assert answer_quality_action_summary["total"] == 2
    assert answer_quality_action_summary["high_priority_count"] == 1
    assert answer_quality_action_summary["next_action_type"] == "review_no_answer_guarded_questions"
    assert dashboard["metrics"]["primary_warning_distribution"] == {
        "none": 1,
        "source_conflict": 1,
        "hallucination_risk": 1,
    }
    primary_warning_rows = {
        row["warning_type"]: row
        for row in dashboard["metrics"]["primary_warning_distribution_rows"]
    }
    assert primary_warning_rows["source_conflict"]["count"] == 1
    assert primary_warning_rows["hallucination_risk"]["rate"] == 0.3333
    assert dashboard["metrics"]["uncertainty_distribution"] == {
        "low": 1,
        "medium": 1,
        "high": 1,
    }
    uncertainty_rows = {
        row["uncertainty"]: row for row in dashboard["metrics"]["uncertainty_distribution_rows"]
    }
    assert uncertainty_rows["high"]["count"] == 1
    assert uncertainty_rows["medium"]["rate"] == 0.3333
    assert dashboard["metrics"]["high_uncertainty_count"] == 1
    assert dashboard["metrics"]["high_uncertainty_rate"] == 0.3333
    assert dashboard["metrics"]["uncertain_answer_count"] == 2
    assert dashboard["metrics"]["uncertain_answer_rate"] == 0.6667
    assert dashboard["metrics"]["reranking_request_count"] == 1
    assert dashboard["metrics"]["average_rerank_candidate_limit"] == 20
    assert dashboard["metrics"]["average_rerank_candidate_count"] == 12
    assert dashboard["metrics"]["average_rerank_reduction_rate"] == 0.9167
    assert dashboard["metrics"]["reranking"]["average_final_top_k"] == 4
    assert dashboard["metrics"]["reranking"]["average_final_source_count"] == 1
    assert dashboard["metrics"]["hallucination_warning_count"] == 1
    assert dashboard["metrics"]["positive_feedback_count"] == 1
    assert dashboard["metrics"]["negative_feedback_count"] == 1
    assert dashboard["metrics"]["source_distribution"]["knowledge"] == 2
    assert dashboard["metrics"]["source_kind_distribution"]["rag"] == 2
    assert dashboard["metrics"]["top_questions"][0]["count"] == 1
    assert dashboard["metrics"]["frequent_questions"][0]["count"] == 1
    assert any(item["term"] == "fehler" for item in dashboard["metrics"]["frequent_search_terms"])
    assert dashboard["metrics"]["most_used_documents"][0]["source_id"] == document.id
    assert dashboard["metrics"]["knowledge_gaps"]["open_count"] == 1
    assert dashboard["metrics"]["knowledge_gaps"]["recurring_count"] == 1
    assert dashboard["metrics"]["knowledge_gaps"]["machine_gap_count"] == 1
    assert dashboard["metrics"]["knowledge_gaps"]["error_gap_count"] == 1
    assert dashboard["metrics"]["knowledge_gaps"]["uncovered_error_gap_count"] == 0
    assert dashboard["metrics"]["knowledge_gaps"]["critical_uncovered_error_gap_count"] == 0
    assert dashboard["metrics"]["knowledge_gaps"]["uncovered_machine_gap_count"] == 0
    assert dashboard["metrics"]["knowledge_gaps"]["critical_uncovered_machine_gap_count"] == 0
    assert dashboard["metrics"]["knowledge_gaps"]["uncovered_error_gaps"] == []
    assert dashboard["metrics"]["knowledge_gaps"]["uncovered_machine_gaps"] == []
    assert dashboard["metrics"]["knowledge_gaps"]["department_gap_count"] == 1
    assert dashboard["metrics"]["knowledge_gaps"]["uncertain_question_gap_count"] == 1
    assert dashboard["metrics"]["knowledge_gaps"]["high_uncertainty_answer_count"] == 1
    uncertain_gap = dashboard["metrics"]["knowledge_gaps"]["uncertain_question_gaps"][0]
    assert uncertain_gap["question"] == "Welche Ursache hat der unbekannte Fehler FU-000?"
    assert uncertain_gap["answer_uncertainty"] == "high"
    assert uncertain_gap["no_answer_count"] == 1
    assert uncertain_gap["knowledge_gap_id"] == 321
    uncertain_action = dashboard["metrics"]["knowledge_gaps"]["uncertain_question_actions"][0]
    assert dashboard["metrics"]["knowledge_gaps"]["uncertain_question_action_count"] == 1
    assert uncertain_action["type"] == "review_uncertain_answer_gap"
    assert uncertain_action["priority"] == "high"
    assert uncertain_action["target"] == uncertain_gap["question"]
    assert uncertain_action["target_id"] == 321
    assert uncertain_action["next_steps"]
    assert any(
        action["type"] == "review_uncertain_answer_gap"
        for action in dashboard["metrics"]["knowledge_gaps"]["recommended_actions"]
    )
    assert dashboard["metrics"]["knowledge_gaps"]["machine_gaps"][0]["machine"] == "FU"
    error_gap = dashboard["metrics"]["knowledge_gaps"]["error_gaps"][0]
    assert error_gap["error_code"] == "FU-000"
    assert error_gap["machine"] == "FU"
    assert error_gap["coverage"] == "thin"
    department_gap = dashboard["metrics"]["knowledge_gaps"]["department_gaps"][0]
    assert department_gap["department"] == "Produktion"
    assert any(
        item["term"] == "dokumentation"
        for item in dashboard["metrics"]["knowledge_gaps"]["frequent_terms"]
    )
    assert dashboard["metrics"]["knowledge_gaps"]["recommended_actions"][0]["type"] in {
        "thin_machine_documentation",
        "missing_machine_documentation",
    }
    assert dashboard["metrics"]["knowledge_gaps"]["action_count"] >= 1
    assert dashboard["metrics"]["knowledge_gaps"]["high_priority_action_count"] >= 0
    action_priorities = {
        item["key"]
        for item in dashboard["metrics"]["knowledge_gaps"]["action_priority_distribution"]
    }
    action_types = {
        item["key"] for item in dashboard["metrics"]["knowledge_gaps"]["action_type_distribution"]
    }
    assert {"medium"} <= action_priorities or {"high"} <= action_priorities
    assert {
        dashboard["metrics"]["knowledge_gaps"]["recommended_actions"][0]["type"]
    } <= action_types
    assert dashboard["recommended_actions"][0]["type"] == "fix_permission_leaks"
    assert dashboard["recommended_actions"][0]["action_source"] == "evaluation"
    assert dashboard["recommended_actions"][0]["rank"] == 1
    assert dashboard["recommended_actions"][0]["rank_label"] == "P1"
    assert dashboard["next_best_action"]["type"] == "fix_permission_leaks"
    assert dashboard["next_best_action"]["rank"] == 1
    assert dashboard["recommended_actions"][1]["type"] == "improve_retrieval_coverage"
    assert dashboard["recommended_actions"][1]["rank"] == 2
    assert any(
        action["action_source"] == "retrieval_quality"
        and action["type"] == "review_low_quality_retrieval_hits"
        for action in dashboard["recommended_actions"]
    )
    assert any(
        action["action_source"] == "knowledge_gap" for action in dashboard["recommended_actions"]
    )
    recommended_summary = dashboard["recommended_action_summary"]
    assert recommended_summary["total"] == 5
    assert recommended_summary["critical_priority_count"] == 1
    assert recommended_summary["high_priority_count"] == 3
    assert recommended_summary["medium_priority_count"] == 1
    assert recommended_summary["next_action_type"] == "fix_permission_leaks"
    assert recommended_summary["next_action_priority"] == "critical"
    assert recommended_summary["next_action_source"] == "evaluation"
    assert recommended_summary["answer_quality_action_count"] == 2
    assert recommended_summary["answer_quality_high_action_count"] == 1
    assert (
        recommended_summary["answer_quality_next_action_type"]
        == "review_no_answer_guarded_questions"
    )
    assert recommended_summary["answer_quality_next_action_priority"] == "high"
    recommended_sources = {item["key"] for item in recommended_summary["type_distribution"]}
    recommended_action_sources = {
        item["key"]: item["count"] for item in recommended_summary["source_distribution"]
    }
    assert {
        "fix_permission_leaks",
        "improve_retrieval_coverage",
        "review_low_quality_retrieval_hits",
    } <= recommended_sources
    assert recommended_action_sources["evaluation"] == 3
    assert recommended_action_sources["retrieval_quality"] == 1
    assert recommended_action_sources["knowledge_gap"] == 1
    assert dashboard["langfuse_metrics"]["available"] is False
    assert dashboard["langfuse_metrics"]["status"] == "disabled"
    assert dashboard["privacy"]["source_ids_visible"] is False
    assert dashboard["privacy"]["source_metadata_aggregates_visible"] is True
    assert dashboard["quality_metrics"]["retrieval_hit_rate"] == 1
    assert dashboard["quality_metrics"]["average_similarity_score"] == 0.82
    assert dashboard["quality_metrics"]["recall_at_k"] == 0.75
    assert dashboard["quality_metrics"]["keyword_hit_rate"] == 0.5
    assert dashboard["quality_metrics"]["keyword_query_count"] == 2
    assert dashboard["quality_metrics"]["no_result_rate"] == 0.25
    assert dashboard["quality_metrics"]["no_result_count"] == 1
    assert dashboard["quality_metrics"]["expected_no_result_count"] == 1
    assert dashboard["quality_metrics"]["expected_no_result_success_count"] == 1
    assert dashboard["quality_metrics"]["expected_no_result_success_rate"] == 1.0
    assert dashboard["quality_metrics"]["unexpected_no_result_count"] == 1
    assert dashboard["quality_metrics"]["unexpected_no_result_rate"] == 0.3333
    assert dashboard["quality_metrics"]["min_source_count_fail_count"] == 1
    assert dashboard["quality_metrics"]["min_source_count_pass_rate"] == 0.75
    assert dashboard["quality_metrics"]["query_type_expected_count"] == 3
    assert dashboard["quality_metrics"]["query_type_match_count"] == 2
    assert dashboard["quality_metrics"]["query_type_accuracy"] == 0.6667
    assert dashboard["quality_metrics"]["permission_leak_count"] == 1
    assert dashboard["quality_metrics"]["forbidden_source_hit_count"] == 1
    assert dashboard["quality_metrics"]["evaluation_quality_gate"]["status"] == "fail"
    assert dashboard["quality_metrics"]["evaluation_quality_gate"]["passed"] is False
    assert (
        dashboard["quality_metrics"]["evaluation_quality_gate"]["blocking"][0]["metric"]
        == "permission_leak_count"
    )
    assert dashboard["quality_metrics"]["evaluation_blocking_count"] == 2
    assert "permission_leak_count" in dashboard["quality_metrics"]["evaluation_blocking_metrics"]
    blocking_rows = {
        item["metric"]: item for item in dashboard["quality_metrics"]["evaluation_blocking_rows"]
    }
    assert blocking_rows["permission_leak_count"]["value"] == 1
    assert blocking_rows["permission_leak_count"]["threshold"] == 0
    assert (
        blocking_rows["permission_leak_count"]["reason"]
        == "retrieved_forbidden_or_invisible_source"
    )
    assert dashboard["quality_metrics"]["evaluation_warning_count"] >= 1
    assert "keyword_hit_rate" in dashboard["quality_metrics"]["evaluation_warning_metrics"]
    warning_rows = {
        item["metric"]: item for item in dashboard["quality_metrics"]["evaluation_warning_rows"]
    }
    assert warning_rows["keyword_hit_rate"]["value"] == 0.5
    assert warning_rows["keyword_hit_rate"]["threshold"] == 0.6
    assert warning_rows["keyword_hit_rate"]["reason"] == "expected_keywords_missing"
    evaluation_actions = {
        item["type"]: item for item in dashboard["quality_metrics"]["evaluation_actions"]
    }
    assert evaluation_actions["fix_permission_leaks"]["priority"] == "critical"
    assert evaluation_actions["fix_permission_leaks"]["count"] == 1
    coverage_action = evaluation_actions["improve_retrieval_coverage"]
    assert coverage_action["unexpected_no_result_count"] == 1
    assert coverage_action["min_source_count_fail_count"] == 1
    evaluation_action_summary = dashboard["quality_metrics"]["evaluation_action_summary"]
    assert evaluation_action_summary["total"] == 4
    assert evaluation_action_summary["critical_priority_count"] == 1
    assert evaluation_action_summary["high_priority_count"] == 1
    assert evaluation_action_summary["medium_priority_count"] == 2
    assert evaluation_action_summary["next_action_type"] == "fix_permission_leaks"
    assert evaluation_action_summary["next_action_priority"] == "critical"
    evaluation_action_types = {
        item["key"] for item in evaluation_action_summary["type_distribution"]
    }
    assert {
        "fix_permission_leaks",
        "improve_retrieval_coverage",
        "complete_evaluation_source_metadata",
        "review_evaluation_warnings",
    } <= evaluation_action_types
    warning_action = evaluation_actions["review_evaluation_warnings"]
    assert warning_action["count"] >= 1
    assert "keyword_hit_rate" in warning_action["warning_metrics"]
    assert dashboard["quality_metrics"]["source_metadata_count"] == 4
    assert dashboard["quality_metrics"]["source_id_coverage_rate"] == 1.0
    assert dashboard["quality_metrics"]["source_type_coverage_rate"] == 1.0
    assert dashboard["quality_metrics"]["source_pair_coverage_rate"] == 0.75
    assert dashboard["quality_metrics"]["metadata_pair_coverage_rate"] == 0.5
    metadata_gaps = {
        item["field"]: item for item in dashboard["quality_metrics"]["source_metadata_gaps"]
    }
    assert "source_id" not in metadata_gaps
    assert "source_type" not in metadata_gaps
    assert metadata_gaps["source_pair"]["missing_rate"] == 0.25
    assert metadata_gaps["metadata_pair"]["missing_rate"] == 0.5
    metadata_action = evaluation_actions["complete_evaluation_source_metadata"]
    assert metadata_action["fields"] == ["source_pair", "metadata_pair"]
    top_hit = dashboard["retrieval_monitoring"]["top_hits"][0]
    assert top_hit["title"] == "Observability Motor FU"
    assert top_hit["source_record_id"] == 123
    assert top_hit["source_kind"] == "rag"
    assert top_hit["knowledge_source_type"] == "machine_manual"
    assert top_hit["machine_id"] == 456
    assert top_hit["role_visibility"] == "department:Produktion"
    assert top_hit["source_created_at"] == "2000-01-01T00:00:00"
    assert top_hit["source_age_days"] >= 180
    assert top_hit["retrieved_at"]
    assert top_hit["employee_access_level"] == "confidential"
    source_freshness = dashboard["retrieval_monitoring"]["source_freshness"]
    assert source_freshness["stale_threshold_days"] == 180
    assert source_freshness["measured_source_count"] == 1
    assert source_freshness["undated_source_count"] == 1
    assert source_freshness["stale_source_count"] == 1
    assert source_freshness["stale_source_rate"] == 1
    assert source_freshness["oldest_source_age_days"] >= 180
    stale_source = dashboard["retrieval_monitoring"]["stale_sources"][0]
    assert stale_source["title"] == "Observability Motor FU"
    assert stale_source["source_age_days"] >= 180
    assert stale_source["stale_threshold_days"] == 180
    undated_source = dashboard["retrieval_monitoring"]["undated_sources"][0]
    assert undated_source["source_record_id"] == 124
    assert undated_source["section_title"] == "FU ohne Datum"
    assert undated_source["source_created_at"] == ""
    assert undated_source["source_age_days"] is None
    metadata_actions = {
        item["type"]: item for item in dashboard["retrieval_monitoring"]["metadata_quality_actions"]
    }
    stale_action = metadata_actions["review_stale_sources"]
    assert stale_action["count"] == 1
    assert stale_action["stale_threshold_days"] == 180
    assert stale_action["sample_sources"][0]["title"] == "Observability Motor FU"
    undated_action = metadata_actions["complete_source_dates"]
    assert undated_action["count"] == 1
    assert undated_action["sample_sources"][0]["source_record_id"] == 124
    quality_action = dashboard["retrieval_monitoring"]["retrieval_quality_actions"][0]
    assert quality_action["type"] == "review_low_quality_retrieval_hits"
    assert quality_action["priority"] == "high"
    assert quality_action["count"] == 2
    assert quality_action["low_score_count"] == 1
    assert quality_action["sample_sources"][0]["title"] == "Observability Motor FU"
    action_summary = dashboard["retrieval_monitoring"]["action_summary"]
    assert action_summary["total"] == 3
    assert action_summary["critical_priority_count"] == 0
    assert action_summary["high_priority_count"] == 1
    assert action_summary["medium_priority_count"] == 2
    assert action_summary["next_action_type"] == "review_low_quality_retrieval_hits"
    assert action_summary["next_action_priority"] == "high"
    action_types = {item["key"] for item in action_summary["type_distribution"]}
    assert {
        "review_low_quality_retrieval_hits",
        "review_stale_sources",
        "complete_source_dates",
    } <= action_types
    assert dashboard["retrieval_monitoring"]["top_hits"][0]["label"].startswith(
        "Observability Motor FU",
    )
    sourced_log = next(
        item
        for item in dashboard["ai_logs"]
        if item["user_question"] == "Welche Dokumente helfen beim FU Fehler?"
    )
    no_answer_log = next(
        item
        for item in dashboard["ai_logs"]
        if item["user_question"] == "Welche Ursache hat der unbekannte Fehler FU-000?"
    )
    conflict_log = next(
        item
        for item in dashboard["ai_logs"]
        if item["user_question"] == "Welche Quellen widersprechen sich beim FU Fehler?"
    )
    assert sourced_log["answer_quality"]["status"] == "grounded"
    assert sourced_log["answer_quality"]["uncertainty"] == "low"
    assert sourced_log["confidence"]["uncertainty"] == "low"
    assert sourced_log["answer_quality"]["source_count"] == 1
    assert sourced_log["answer_quality_label"] == "good"
    assert sourced_log["sources"][0]["title"] == "Observability Motor FU"
    assert sourced_log["sources"][0]["source_record_id"] == 123
    assert sourced_log["sources"][0]["source_kind"] == "rag"
    assert sourced_log["sources"][0]["knowledge_source_type"] == "machine_manual"
    assert sourced_log["sources"][0]["machine_id"] == 456
    assert sourced_log["sources"][0]["role_visibility"] == "department:Produktion"
    assert sourced_log["sources"][0]["employee_access_level"] == "confidential"
    assert no_answer_log["answer_quality"]["status"] == "no_answer"
    assert no_answer_log["confidence"]["uncertainty"] == "high"
    assert no_answer_log["answer_quality_label"] == "risk"
    assert no_answer_log["knowledge_gap_id"] == 321
    assert no_answer_log["knowledge_gap_created"] is True
    assert conflict_log["answer_quality"]["status"] == "conflicting_sources"
    assert conflict_log["answer_quality_label"] == "conflict"
    assert conflict_log["answer_quality"]["uncertainty"] == "medium"
    assert conflict_log["confidence"]["uncertainty"] == "medium"
    assert dashboard["debug_tools"]["prompt_blueprint"]["system_prompt"]
    assert dashboard["debug_tools"]["request_analysis"]["retrieval"]["source_count"] == 1
    assert dashboard["debug_tools"]["request_analysis"]["answer_quality"]["status"] == ("grounded")
    assert dashboard["debug_tools"]["request_analysis"]["confidence"]["uncertainty"] == "low"
    available = {item["question"]: item for item in dashboard["debug_tools"]["available_requests"]}
    assert (
        available["Welche Ursache hat der unbekannte Fehler FU-000?"]["answer_uncertainty"]
        == "high"
    )


def test_ai_observability_dashboard_tracks_structured_and_rag_answer_metrics(
    app,
    make_user,
):
    """Verify AI Admin metrics distinguish structured, RAG, and no-source answers."""
    user = make_user(username="ai_structured_observability_user")
    with app.app_context():
        db.session.add_all(
            [
                ChatMessage(
                    user_id=user["id"],
                    message="Welche offenen Aufgaben gibt es?",
                    response="2 offene Aufgaben gefunden.",
                    response_type="structured_scope",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "tasks"},
                            "scopes": ["tasks"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=2,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche offenen Aufgaben gibt es?",
                    response="1 Task in Bearbeitung gefunden.",
                    response_type="tasks_status",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "tasks"},
                            "scopes": ["tasks"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Stoerungen sind kritisch?",
                    response="1 kritische Stoerung gefunden.",
                    response_type="structured_scope",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "incidents"},
                            "scopes": ["errors"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Maschine hatte die meiste Ausfallzeit?",
                    response="Presse 3 hatte die meiste Ausfallzeit.",
                    response_type="machine_downtime",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "machines"},
                            "scopes": ["machines"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=2,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Wie ist mein letzter Urlaubsantrag?",
                    response="Kein sichtbarer Urlaubsantrag gefunden.",
                    response_type="vacation_own_status",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "vacations"},
                            "scopes": ["employees"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=0,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Mitarbeiter sind heute verfuegbar?",
                    response="Mitarbeiterliste geladen.",
                    response_type="employee_available",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "employees"},
                            "scopes": ["employees"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Dokumente wurden zuletzt geaendert?",
                    response="Zuletzt geaenderte Dokumente geladen.",
                    response_type="document_recent",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "documents"},
                            "scopes": ["documents"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Wer ist morgen in der Fruehschicht?",
                    response="Schichtplanung fuer morgen geladen.",
                    response_type="shiftplan_entries",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "shiftplans"},
                            "scopes": ["shiftplans"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Lagerartikel muessen nachbestellt werden?",
                    response="Nachzubestellende Materialien geladen.",
                    response_type="inventory_low_stock",
                    diagnostics_json=json.dumps(
                        {
                            "structured_context": {"entity_type": "inventory"},
                            "scopes": ["inventory"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Dokumente zur Pumpe helfen?",
                    response="Dokument Pumpenhandbuch nutzen.",
                    response_type="assistant",
                    diagnostics_json=json.dumps({"scopes": ["documents"]}, ensure_ascii=True),
                    source_count=1,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Welche Maschinen sind sichtbar?",
                    response="Keine Berechtigung fuer Maschinen.",
                    response_type="permission_denied",
                    diagnostics_json=json.dumps(
                        {
                            "status": "permission_denied",
                            "structured_context": {"entity_type": "machines"},
                            "scopes": ["machines"],
                        },
                        ensure_ascii=True,
                    ),
                    source_count=0,
                ),
                ChatMessage(
                    user_id=user["id"],
                    message="Gibt es unbekannte Hinweise?",
                    response="Keine belegte Antwort vorhanden.",
                    response_type="assistant",
                    diagnostics_json=json.dumps({"empty_retrieval": True}, ensure_ascii=True),
                    source_count=0,
                ),
            ]
        )
        db.session.commit()

        dashboard = ai_observability_dashboard({"days": "30", "limit": "5"})

    metrics = dashboard["metrics"]
    assert metrics["structured_answer_count"] == 9
    assert metrics["structured_answer_rate"] == 0.75
    assert metrics["rag_answer_count"] == 1
    assert metrics["rag_answer_rate"] == 0.0833
    assert metrics["no_source_count"] == 3
    assert metrics["no_source_rate"] == 0.25
    assert metrics["no_source_permission_denied_count"] == 1
    assert metrics["no_source_no_data_count"] == 1
    assert metrics["no_source_answer_count"] == 1
    assert metrics["source_count_average"] == 0.9167
    assert metrics["average_answer_source_count"] == 0.9167
    assert metrics["source_count_average_answered"] == 1.1
    assert metrics["structured_module_distribution"] == {
        "tasks": 2,
        "errors": 1,
        "machines": 1,
        "vacations": 1,
        "employees": 1,
        "documents": 1,
        "shiftplans": 1,
        "inventory": 1,
    }
    assert metrics["structured_domain_distribution"] == metrics["structured_module_distribution"]
    assert metrics["top_structured_modules"][0] == {
        "module": "tasks",
        "label": "Tasks",
        "count": 2,
        "rate": 0.2222,
    }
    top_modules = {item["module"]: item for item in metrics["top_structured_modules"]}
    assert top_modules["errors"]["label"] == "Stoerungen"
    assert top_modules["machines"]["label"] == "Maschinen"
    assert top_modules["vacations"]["label"] == "Urlaub"
    assert top_modules["employees"]["label"] == "Mitarbeiter"
    assert top_modules["documents"]["label"] == "Dokumente"
    assert top_modules["shiftplans"]["label"] == "Schichtplanung"
    assert top_modules["inventory"]["label"] == "Lager"
    assert dashboard["top_structured_modules"] == metrics["top_structured_modules"]
    assert any(
        item["question"] == "Welche offenen Aufgaben gibt es?" and item["count"] == 2
        for item in dashboard["top_questions"]
    )
    assert any(item["term"] == "aufgaben" for item in dashboard["frequent_search_terms"])


def test_ai_observability_dashboard_exposes_failed_requests_without_prompts(
    app,
    make_user,
):
    """Verify failed AI requests are visible as metadata-only admin rows."""
    user = make_user(username="ai_observability_failed_user")
    with app.app_context():
        actor = type("UserStub", (), {"id": user["id"]})()
        create_ai_audit_event(
            user=actor,
            workflow="general_chat",
            diagnostics={
                "status": "openai_error",
                "error": "rate_limit",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "model_tier": "balanced",
                "fallback_used": True,
                "latency_ms": 1800,
                "total_tokens": 25,
            },
            source_count=0,
        )
        create_ai_audit_event(
            user=actor,
            workflow="general_chat",
            diagnostics={
                "status": "unsupported_provider",
                "error": "AI_PROVIDER is not supported by a dedicated adapter yet",
                "provider": "mock",
                "fallback_used": True,
                "latency_ms": 10,
                "total_tokens": 0,
            },
            source_count=0,
        )
        create_ai_audit_event(
            user=actor,
            workflow="general_chat",
            diagnostics={
                "status": "base_url_missing",
                "provider": "mock",
                "fallback_used": True,
                "latency_ms": 5,
                "total_tokens": 0,
            },
            source_count=0,
        )
        db.session.commit()

        dashboard = ai_observability_dashboard({"days": "30", "limit": "5"})

    failed = next(item for item in dashboard["failed_requests"] if item["status"] == "openai_error")
    unsupported = next(
        item for item in dashboard["failed_requests"] if item["status"] == "unsupported_provider"
    )
    missing_base_url = next(
        item for item in dashboard["failed_requests"] if item["status"] == "base_url_missing"
    )
    serialized = json.dumps(dashboard["failed_requests"], ensure_ascii=True)
    reason_counts = {
        item["reason"]: item["count"]
        for item in dashboard["metrics"]["failure_reason_distribution"]
    }
    assert dashboard["metrics"]["failed_request_count"] == 3
    assert reason_counts["rate_limit"] == 1
    assert reason_counts["unsupported_provider"] == 1
    assert reason_counts["base_url_missing"] == 1
    assert failed["workflow"] == "general_chat"
    assert failed["status"] == "openai_error"
    assert failed["failure_reason"] == "rate_limit"
    assert failed["error_category"] == "rate_limit"
    assert failed["fallback_used"] is True
    assert failed["latency_ms"] == 1800
    assert unsupported["failure_reason"] == "unsupported_provider"
    assert unsupported["error_category"] == (
        "AI_PROVIDER is not supported by a dedicated adapter yet"
    )
    assert missing_base_url["failure_reason"] == "base_url_missing"
    assert missing_base_url["error_category"] == ""
    assert "prompt" not in serialized.lower()
    assert "question" not in serialized.lower()
    assert "answer" not in serialized.lower()


def test_admin_ai_observability_endpoint_is_admin_only(
    client,
    make_user,
    auth_headers,
):
    """Verify AI observability endpoint is restricted to master admins."""
    admin = make_user(
        username="ai_observability_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_observability_regular")

    forbidden_response = client.get(
        "/api/v1/admin/ai/observability",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/observability?days=30&limit=5",
        headers=auth_headers(admin["username"]),
    )

    payload = admin_response.get_json()["data"]
    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert set(payload.keys()) >= {
        "provider_readiness",
        "metrics",
        "retrieval_monitoring",
        "ai_logs",
        "failed_requests",
        "quality_metrics",
        "recommended_actions",
        "next_best_action",
        "recommended_action_summary",
        "debug_tools",
        "langfuse_metrics",
        "metric_catalog",
        "privacy",
    }
    catalog_keys = {item["key"] for item in payload["metric_catalog"]}
    assert {
        "frequent_questions",
        "frequent_search_terms",
        "average_final_top_k",
        "average_tokens",
        "cost_windows",
        "provider_ready",
        "provider_readiness_status",
        "provider_degraded_component_count",
        "provider_next_action_type",
        "failed_request_count",
        "retrieval_hit_rate",
        "source_freshness",
        "no_answer_rate",
        "recall_at_k",
        "mrr",
        "keyword_hit_rate",
        "no_result_rate",
        "min_source_count_pass_rate",
        "query_type_accuracy",
        "permission_leak_count",
        "evaluation_quality_gate_status",
        "evaluation_quality_gate_issue_count",
        "evaluation_blocking_count",
        "evaluation_warning_count",
        "source_metadata_gap_count",
        "source_metadata_min_coverage_rate",
        "answer_quality_reason_distribution",
        "answer_quality_action_count",
        "retrieval_action_count",
        "evaluation_action_count",
        "feedback",
        "most_used_documents",
        "knowledge_gaps",
    } <= catalog_keys
    assert payload["provider_readiness"]["provider_status"]["provider"] == "mock"
    assert payload["provider_readiness"]["readiness"]["next_action"] is None
    assert not any(
        action["action_source"] == "provider_readiness" for action in payload["recommended_actions"]
    )
    assert payload["privacy"]["raw_chunk_text_visible"] is False


def test_ai_observability_includes_provider_readiness_actions(app):
    """Verify observability exposes provider readiness remediation without secrets."""
    with app.app_context():
        app.config["AI_PROVIDER"] = "gemini"
        app.config["OPENAI_API_KEY"] = "test-secret-key"
        dashboard = ai_observability_dashboard({"days": "30", "limit": "5"})

    provider_readiness = dashboard["provider_readiness"]
    next_action = provider_readiness["readiness"]["next_action"]
    serialized = str(provider_readiness)
    assert provider_readiness["ready"] is False
    assert provider_readiness["provider"] == "gemini"
    assert provider_readiness["provider_status"]["effective_provider"] == "mock"
    assert dashboard["metrics"]["provider_ready"] is False
    assert dashboard["metrics"]["provider_readiness_status"] == "degraded"
    assert dashboard["metrics"]["provider_degraded_component_count"] == 1
    assert dashboard["metrics"]["provider_next_action_type"] == ("select_supported_provider")
    assert next_action["component"] == "provider"
    assert next_action["configuration_action"] == "select_supported_provider"
    assert "AI_PROVIDER" in next_action["recommended_action"]
    assert dashboard["next_best_action"]["action_source"] == "provider_readiness"
    assert dashboard["next_best_action"]["type"] == "select_supported_provider"
    assert dashboard["next_best_action"]["priority"] == "critical"
    assert dashboard["next_best_action"]["rank"] == 1
    assert dashboard["recommended_action_summary"]["next_action_source"] == "provider_readiness"
    assert "test-secret-key" not in serialized
    assert "api_key" not in serialized.lower().replace("api_key_configured", "")


def test_ai_observability_provider_action_outranks_evaluation_action():
    """Verify provider outages are ranked before other critical admin actions."""
    provider_readiness = {
        "ready": False,
        "readiness": {
            "next_action": {
                "component": "provider",
                "reason": "unsupported_provider",
                "configuration_action": "select_supported_provider",
                "recommended_action": "AI_PROVIDER korrigieren.",
            }
        },
    }
    quality_metrics = {
        "evaluation_actions": [
            {
                "type": "fix_permission_leaks",
                "priority": "critical",
                "target": "permission_leak_count",
            }
        ]
    }

    actions = _observability_recommended_actions(
        {"knowledge_gaps": {}},
        {},
        quality_metrics,
        provider_readiness,
        limit=5,
    )

    assert actions[0]["action_source"] == "provider_readiness"
    assert actions[0]["type"] == "select_supported_provider"
    assert actions[0]["rank"] == 1
    assert actions[1]["action_source"] == "evaluation"
    assert actions[1]["type"] == "fix_permission_leaks"
    assert actions[1]["rank"] == 2


def test_ai_observability_evaluation_warning_action_targets_chunk_structure():
    """Verify chunk-structure evaluation warnings get specific admin guidance."""
    actions = _evaluation_quality_actions(
        latest_eval={"query_count": 1},
        quality_gate={
            "warnings": [
                {
                    "metric": "block_metadata_coverage_rate",
                    "value": 0.5,
                    "threshold": 0.8,
                    "reason": "chunk_structure_metadata_incomplete",
                }
            ]
        },
        source_metadata_gaps=[],
    )

    warning_action = actions[0]
    assert warning_action["type"] == "review_evaluation_warnings"
    assert warning_action["warning_metrics"] == ["block_metadata_coverage_rate"]
    assert warning_action["focus_areas"] == ["chunk_structure_metadata"]
    assert "Chunk-Strukturmetadaten" in warning_action["recommended_action"]
    assert any("chunk_block_count" in step for step in warning_action["next_steps"])
    assert any(
        "block_metadata_coverage_rate" in criterion
        for criterion in warning_action["success_criteria"]
    )


def test_admin_retrieval_telemetry_endpoint_is_admin_only(
    client,
    make_user,
    auth_headers,
):
    """Verify retrieval telemetry is exposed only to master admins."""
    admin = make_user(
        username="retrieval_telemetry_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="retrieval_telemetry_regular")

    forbidden_response = client.get(
        "/api/v1/admin/ai/retrieval-telemetry",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/retrieval-telemetry?days=30&limit=5",
        headers=auth_headers(admin["username"]),
    )

    payload = admin_response.get_json()["data"]
    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert set(payload.keys()) >= {
        "retrieval_slo",
        "retrieval_evaluation_history",
        "source_usage",
        "poor_sources",
        "unsuccessful_questions",
        "knowledge_gaps",
        "negative_feedback",
        "unused_chunks",
    }


def test_ai_chat_history_is_user_scoped_and_admin_searchable(
    client,
    make_user,
    auth_headers,
):
    """Verify users see their own chat history and admins can search all chats."""
    admin = make_user(
        username="ai_history_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_history_user")
    other = make_user(username="ai_history_other")

    client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was ist ein User?"},
    )
    client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(other["username"]),
        json={"message": "Was ist Hydraulik?"},
    )

    own_response = client.get(
        "/api/v1/ai/chat/history?q=User",
        headers=auth_headers(user["username"]),
    )
    forbidden_response = client.get(
        "/api/v1/admin/ai/chats",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/admin/ai/chats?q=Hydraulik",
        headers=auth_headers(admin["username"]),
    )

    own_items = own_response.get_json()["data"]["items"]
    admin_items = admin_response.get_json()["data"]["items"]
    assert own_response.status_code == 200
    assert len(own_items) == 1
    assert own_items[0]["user_id"] == user["id"]
    assert own_items[0]["response_type"] == "general_chat"
    assert own_items[0]["answer_quality"]["status"] in {
        "fallback",
        "low_confidence",
        "unverified",
    }
    assert own_items[0]["answer_quality"]["source_count"] == 0
    assert own_items[0]["answer_quality"]["recommended_user_action"]
    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert len(admin_items) == 1
    assert admin_items[0]["user"]["username"] == other["username"]
    assert "answer_quality" in admin_items[0]


def test_admin_ai_events_are_filterable(
    client,
    make_user,
    auth_headers,
):
    """Verify admin AI event search filters metadata without prompts."""
    admin = make_user(
        username="ai_events_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_events_user")
    with client.application.app_context():
        event_id = create_ai_audit_event(
            type("UserRef", (), {"id": user["id"]})(),
            "general_chat",
            {
                "status": "openai_error",
                "error": "rate_limit",
                "total_tokens": 10,
            },
        )
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/events?error=rate_limit",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["items"][0]["id"] == event_id
    assert payload["items"][0]["error_category"] == "rate_limit"
    assert "prompt" not in payload["items"][0]


def test_knowledge_upload_and_chat_retrieval_respect_permissions(
    client,
    make_user,
    auth_headers,
    set_dashboard_permission,
):
    """Verify local RAG chunks are indexed and returned as chat sources."""
    admin = make_user(
        username="knowledge_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked = make_user(
        username="knowledge_blocked",
        role=Role.PRODUKTION,
        department_name="Instandhaltung",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    set_dashboard_permission(blocked["username"], "documents", can_view=True)

    forbidden_response = client.get(
        "/api/v1/admin/ai/knowledge",
        headers=auth_headers(user["username"]),
    )
    upload_response = client.post(
        "/api/v1/admin/ai/knowledge/upload",
        headers=auth_headers(admin["username"]),
        data={
            "department": "Produktion",
            "file": (BytesIO(b"Hydraulikfilter X900 taeglich pruefen."), "manual.txt"),
        },
        content_type="multipart/form-data",
    )
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Wie funktioniert Hydraulikfilter X900?"},
    )
    blocked_chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(blocked["username"]),
        json={"message": "Wie funktioniert Hydraulikfilter X900?"},
    )

    assert forbidden_response.status_code == 403
    assert upload_response.status_code == 201
    assert upload_response.get_json()["data"]["status"] == "indexed"
    assert any(source["type"] == "knowledge" for source in chat_response.get_json()["sources"])
    assert not any(
        source["type"] == "knowledge" for source in blocked_chat_response.get_json()["sources"]
    )
    with client.application.app_context():
        document = db.session.get(KnowledgeDocument, upload_response.get_json()["data"]["id"])
        assert document.chunk_count == 1


def test_ai_chat_admin_exposes_retrieval_debug_counters(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify admin chat responses expose prompt-safe retrieval debug counters."""
    admin = make_user(
        username="retrieval_debug_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_error_entry(
        machine="Presse DBG900",
        error_code="DBG900",
        title="Hydraulikdruck pruefen",
        department_name="Produktion",
        description="DBG900 Hydraulikdruck faellt ab.",
    )
    _create_retrieval_debug_document(
        app,
        title="DBG900 Hydraulik Wissen",
        text="DBG900 Hydraulikdruck an Presse DBG900 mit Manometer pruefen.",
        token_text="dbg900 hydraulikdruck presse manometer pruefen",
        department="Produktion",
        quality_status="admin_approved",
        created_by=admin["id"],
    )

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Fehler DBG900 Hydraulikdruck an Presse DBG900"},
    )

    payload = response.get_json()
    debug = payload["diagnostics"]["retrieval_debug"]
    assert response.status_code == 200
    assert debug["sql_candidates_found"] >= 1
    assert debug["vector_candidates_found"] >= 1
    assert debug["final_visible_sources"] == len(payload["sources"])
    assert debug["candidate_counts"]["sql"] == debug["sql_candidates_found"]
    assert debug["candidate_counts"]["vector"] == debug["vector_candidates_found"]
    assert debug["filtered_by"]["score_anchor"] == debug["score_anchor_filtered"]
    assert debug["reranking"]["candidate_limit"] >= debug["reranking"]["final_top_k"]
    assert debug["reranking"]["candidate_count"] == debug["vector_candidates_found"]
    assert debug["reranking"]["final_source_count"] == debug["final_visible_sources"]
    assert any(decision["step"] == "final_visible_sources" for decision in debug["decision_trace"])
    assert "DBG900" not in json.dumps(debug)


def test_ai_chat_hides_retrieval_debug_for_non_admin_in_production_mode(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify non-admin production responses do not expose retrieval debug data."""
    user = make_user(username="retrieval_debug_hidden_user")
    make_error_entry(
        machine="Presse DBG901",
        error_code="DBG901",
        title="Ventil pruefen",
        department_name="Produktion",
    )
    old_testing = app.config.get("TESTING")
    old_debug = app.config.get("DEBUG")
    app.config["TESTING"] = False
    app.config["DEBUG"] = False
    try:
        response = client.post(
            "/api/v1/ai/chat",
            headers=auth_headers(user["username"]),
            json={"message": "Fehler DBG901 an Presse DBG901"},
        )
    finally:
        app.config["TESTING"] = old_testing
        app.config["DEBUG"] = old_debug

    assert response.status_code == 200
    assert "retrieval_debug" not in response.get_json()["diagnostics"]


def test_ai_chat_retrieval_debug_counts_filtered_candidates(
    app,
    client,
    make_user,
    auth_headers,
    set_dashboard_permission,
):
    """Verify retrieval debug reports quality, permission, and score filters."""
    user = make_user(
        username="retrieval_debug_filter_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    _create_retrieval_debug_document(
        app,
        title="DBG902 abgelehnt",
        text="DBG902 Hydraulik abgelehnte Quelle.",
        token_text="dbg902 hydraulik abgelehnte quelle",
        department="Produktion",
        quality_status="rejected",
        created_by=user["id"],
    )
    _create_retrieval_debug_document(
        app,
        title="DBG902 fremder Bereich",
        text="DBG902 Hydraulik fremder Bereich.",
        token_text="dbg902 hydraulik fremder bereich",
        department="Instandhaltung",
        quality_status="admin_approved",
        created_by=user["id"],
    )
    _create_retrieval_debug_document(
        app,
        title="Unverbundene Quelle",
        text="Kalibrierprotokoll ohne passende Begriffe.",
        token_text="kalibrierprotokoll ohne passende begriffe",
        department="Produktion",
        quality_status="admin_approved",
        created_by=user["id"],
    )
    old_threshold = app.config.get("RAG_SEMANTIC_ONLY_MIN_SIMILARITY")
    app.config["RAG_SEMANTIC_ONLY_MIN_SIMILARITY"] = 1.01
    try:
        response = client.post(
            "/api/v1/ai/chat",
            headers=auth_headers(user["username"]),
            json={"message": "Fehler DBG902 Hydraulik"},
        )
    finally:
        app.config["RAG_SEMANTIC_ONLY_MIN_SIMILARITY"] = old_threshold

    debug = response.get_json()["diagnostics"]["retrieval_debug"]
    assert response.status_code == 200
    assert debug["quality_filtered"] >= 1
    assert debug["permission_filtered"] >= 1
    assert debug["score_filtered"] >= 1
    assert debug["score_anchor_filtered"] >= 1
    assert debug["filtered_by"]["permissions"] == debug["permission_filtered"]
    assert debug["filtered_by"]["quality"] == debug["quality_filtered"]
    assert debug["filtered_by"]["score_anchor"] == debug["score_anchor_filtered"]
    assert any(decision["step"] == "score_anchor_filter" for decision in debug["decision_trace"])
    assert debug["final_visible_sources"] == len(response.get_json()["sources"])


def test_admin_training_crud_marks_knowledge_stale_and_deletes_document(
    client,
    make_user,
    auth_headers,
):
    """Verify master admins can maintain manual assistant training entries."""
    admin = make_user(
        username="training_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="training_user")
    admin_headers = auth_headers(admin["username"])

    forbidden_response = client.get(
        "/api/v1/admin/ai/training",
        headers=auth_headers(user["username"]),
    )
    invalid_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={"answer": "Ohne Titel"},
    )
    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Hydraulikfilter X900",
            "question": "Wie wird X900 gepflegt?",
            "answer": "Hydraulikfilter X900 taeglich pruefen und Befund dokumentieren.",
            "keywords": ["Hydraulikfilter", "X900", "Filterpflege"],
            "category": "wartung",
            "department": "Produktion",
            "priority": 80,
        },
    )
    entry_id = create_response.get_json()["data"]["id"]
    update_response = client.put(
        f"/api/v1/admin/ai/training/{entry_id}",
        headers=admin_headers,
        json={"answer": "X900 je Schicht pruefen.", "priority": 90},
    )
    list_response = client.get(
        "/api/v1/admin/ai/training?q=X900",
        headers=admin_headers,
    )

    assert forbidden_response.status_code == 403
    assert invalid_response.status_code == 400
    assert invalid_response.get_json()["missing_information"]["status"] == "needs_information"
    assert create_response.status_code == 201
    assert create_response.get_json()["data"]["keywords"] == "Hydraulikfilter, X900, Filterpflege"
    assert (
        create_response.get_json()["data"]["missing_information"]["status"] == "needs_information"
    )
    assert update_response.status_code == 200
    assert update_response.get_json()["data"]["priority"] == 90
    assert list_response.get_json()["data"]["pagination"]["total"] == 1
    with client.application.app_context():
        document = KnowledgeDocument.query.filter_by(
            source_type="manual_training",
            source_id=entry_id,
        ).one()
        assert document.status == "stale"

    delete_response = client.delete(
        f"/api/v1/admin/ai/training/{entry_id}",
        headers=admin_headers,
    )

    assert delete_response.status_code == 200
    with client.application.app_context():
        assert db.session.get(AssistantTrainingEntry, entry_id) is None
        assert (
            KnowledgeDocument.query.filter_by(
                source_type="manual_training",
                source_id=entry_id,
            ).first()
            is None
        )


def test_training_active_state_controls_knowledge_document(
    client,
    make_user,
    auth_headers,
):
    """Verify inactive manual training is removed from RAG sources."""
    admin = make_user(
        username="training_active_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    headers = auth_headers(admin["username"])
    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=headers,
        json={
            "title": "Aktives Training",
            "question": "Wie pruefe ich Training aktiv?",
            "answer": "Training aktiv pruefen und Quelle reindexieren.",
            "is_active": True,
        },
    )
    entry_id = create_response.get_json()["data"]["id"]

    inactive_response = client.put(
        f"/api/v1/admin/ai/training/{entry_id}",
        headers=headers,
        json={"is_active": False},
    )
    with client.application.app_context():
        inactive_document = KnowledgeDocument.query.filter_by(
            source_type="manual_training",
            source_id=entry_id,
        ).first()

    active_response = client.put(
        f"/api/v1/admin/ai/training/{entry_id}",
        headers=headers,
        json={"is_active": True},
    )
    with client.application.app_context():
        active_document = KnowledgeDocument.query.filter_by(
            source_type="manual_training",
            source_id=entry_id,
        ).one()

    assert create_response.status_code == 201
    assert inactive_response.status_code == 200
    assert inactive_document is None
    assert active_response.status_code == 200
    assert active_document.status == "pending"


def test_admin_training_missing_information_complete_state(
    client,
    make_user,
    auth_headers,
):
    """Verify complete manual knowledge entries do not need follow-up prompts."""
    admin = make_user(
        username="training_prompt_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    response = client.post(
        "/api/v1/admin/ai/training",
        headers=auth_headers(admin["username"]),
        json={
            "title": "Maschine 3 E104 Sensor Signal",
            "question": "Was tun bei E104 an Maschine 3, wenn der Sensor kein Signal meldet?",
            "answer": (
                "Maschine 3 sichern, Sensor gereinigt, Kabel geprueft und "
                "Probelauf erfolgreich. Stoerung behoben."
            ),
            "keywords": ["Maschine 3", "E104", "Sensor"],
            "category": "stoerung",
            "department": "Instandhaltung",
            "priority": 80,
        },
    )

    assert response.status_code == 201
    assert response.get_json()["data"]["missing_information"]["status"] == "complete"
    assert response.get_json()["data"]["missing_information"]["missing_fields"] == []


def test_generated_knowledge_documents_default_to_ai_suggested(app):
    """Verify generated knowledge is never implicitly admin-approved."""
    with app.app_context():
        register_source_document(
            source_type="generated_document",
            source_id=99,
            title="AI Wartungsbericht",
            department="Instandhaltung",
            url_path="/documents",
        )
        db.session.commit()

        document = KnowledgeDocument.query.filter_by(
            source_type="generated_document",
            source_id=99,
        ).one()
        assert document.quality_status == "ai_suggested"


def test_master_admin_can_update_knowledge_quality_status(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify master admins can approve a knowledge document explicitly."""
    admin = make_user(
        username="knowledge_quality_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        document = KnowledgeDocument(
            source_type="upload",
            title="Hydraulik Anleitung",
            original_filename="hydraulik.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="draft",
        )
        rejected_document = KnowledgeDocument(
            source_type="upload",
            title="Blockierte OCR Quelle",
            original_filename="ocr.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="low_quality",
        )
        db.session.add_all([document, rejected_document])
        db.session.commit()
        document_id = document.id
        rejected_document_id = rejected_document.id

    response = client.put(
        f"/api/v1/admin/ai/knowledge/{document_id}/quality-status",
        headers=auth_headers(admin["username"]),
        json={"quality_status": "admin_approved"},
    )
    rejected_response = client.put(
        f"/api/v1/admin/ai/knowledge/{rejected_document_id}/quality-status",
        headers=auth_headers(admin["username"]),
        json={"quality_status": "rejected"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["quality_status"] == "admin_approved"
    assert rejected_response.status_code == 200
    assert rejected_response.get_json()["data"]["quality_status"] == "rejected"
    with app.app_context():
        assert db.session.get(KnowledgeDocument, document_id).quality_status == "admin_approved"
        assert db.session.get(KnowledgeDocument, rejected_document_id).quality_status == "rejected"


def test_technician_quality_status_permissions_are_scoped(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify technicians can confirm local knowledge but cannot approve it."""
    technician = make_user(
        username="knowledge_quality_tech",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    with app.app_context():
        own_document = KnowledgeDocument(
            source_type="upload",
            title="Eigener Eintrag",
            original_filename="own.txt",
            content_type="text/plain",
            department="Instandhaltung",
            status="indexed",
            quality_status="draft",
        )
        foreign_document = KnowledgeDocument(
            source_type="upload",
            title="Fremder Eintrag",
            original_filename="foreign.txt",
            content_type="text/plain",
            department="Produktion",
            status="indexed",
            quality_status="draft",
        )
        db.session.add_all([own_document, foreign_document])
        db.session.commit()
        own_id = own_document.id
        foreign_id = foreign_document.id

    headers = auth_headers(technician["username"])
    confirm_response = client.put(
        f"/api/v1/admin/ai/knowledge/{own_id}/quality-status",
        headers=headers,
        json={"quality_status": "technician_confirmed"},
    )
    approve_response = client.put(
        f"/api/v1/admin/ai/knowledge/{own_id}/quality-status",
        headers=headers,
        json={"quality_status": "admin_approved"},
    )
    foreign_response = client.put(
        f"/api/v1/admin/ai/knowledge/{foreign_id}/quality-status",
        headers=headers,
        json={"quality_status": "outdated"},
    )

    assert confirm_response.status_code == 200
    assert confirm_response.get_json()["data"]["quality_status"] == "technician_confirmed"
    assert approve_response.status_code == 403
    assert foreign_response.status_code == 403


def test_manual_training_rag_respects_active_state_and_department(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify manual training sources are indexed and permission-aware."""
    admin = make_user(
        username="training_rag_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="training_rag_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked = make_user(
        username="training_rag_blocked",
        role=Role.PRODUKTION,
        department_name="Instandhaltung",
    )
    no_scope = make_user(
        username="training_rag_no_scope",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    set_dashboard_permission(blocked["username"], "documents", can_view=True)
    set_dashboard_permission(no_scope["username"], "documents", can_view=False)
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])
    blocked_headers = auth_headers(blocked["username"])
    no_scope_headers = auth_headers(no_scope["username"])

    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "X900 Filterpflege",
            "question": "Was ist bei X900 wichtig?",
            "answer": "X900 Filter taeglich pruefen und Druckverlust dokumentieren.",
            "keywords": "X900, Druckverlust",
            "department": "Produktion",
        },
    )
    client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Y900 inaktiv",
            "question": "Was ist bei Y900 wichtig?",
            "answer": "Dieser Eintrag ist inaktiv.",
            "keywords": "Y900",
            "department": "Produktion",
            "is_active": False,
        },
    )
    client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Z900 andere Abteilung",
            "question": "Was ist bei Z900 wichtig?",
            "answer": "Z900 gehoert zur Instandhaltung.",
            "keywords": "Z900",
            "department": "Instandhaltung",
        },
    )
    reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex?mode=stale",
        headers=admin_headers,
    )
    admin_visible_response = client.post(
        "/api/v1/ai/chat",
        headers=admin_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )
    visible_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )
    inactive_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei Y900 wichtig?"},
    )
    department_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei Z900 wichtig?"},
    )
    blocked_response = client.post(
        "/api/v1/ai/chat",
        headers=blocked_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )
    no_scope_response = client.post(
        "/api/v1/ai/chat",
        headers=no_scope_headers,
        json={"message": "Was ist bei X900 Druckverlust wichtig?"},
    )

    assert create_response.status_code == 201
    assert reindex_response.status_code == 200
    assert any(
        source["type"] == "knowledge" and "X900" in source["title"]
        for source in admin_visible_response.get_json()["sources"]
    )
    assert any(
        source["type"] == "knowledge" and "X900" in source["title"]
        for source in visible_response.get_json()["sources"]
    )
    assert not any("Y900" in source["title"] for source in inactive_response.get_json()["sources"])
    assert not any(
        "Z900" in source["title"] for source in department_response.get_json()["sources"]
    )
    assert not any("X900" in source["title"] for source in blocked_response.get_json()["sources"])
    assert not any("X900" in source["title"] for source in no_scope_response.get_json()["sources"])


def test_chat_templates_are_permission_aware(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify chat template suggestions are filtered by dashboard permissions."""
    user = make_user(username="chat_template_user")
    set_dashboard_permission(user["username"], "tasks", can_view=True, can_write=False)
    set_dashboard_permission(user["username"], "errors", can_view=False)
    set_dashboard_permission(user["username"], "machines", can_view=True)

    response = client.get(
        "/api/v1/ai/chat/templates",
        headers=auth_headers(user["username"]),
    )

    messages = [item["message"] for item in response.get_json()["data"]["items"]]
    assert response.status_code == 200
    assert "Welche Tasks sind heute wichtig?" in messages
    assert "Welche Maschinen brauchen Aufmerksamkeit?" in messages
    assert "Was bedeutet Fehler E104?" not in messages
    assert "Task erstellen: Maschine 3 macht Geraeusche" not in messages


def test_knowledge_reindex_registers_generated_documents(
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify reindex adds generated documents to the local knowledge base."""
    admin = make_user(
        username="knowledge_reindex_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    task_id = make_task("Wartung X900", creator_username=admin["username"])
    make_document(task_id=task_id, created_by=admin["id"], department="Produktion")

    response = client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["documents"] >= 1


def test_knowledge_reindex_reports_outdated_database_schema(
    client,
    make_user,
    auth_headers,
    monkeypatch,
):
    """Verify reindex returns actionable diagnostics when migrations are missing."""
    admin = make_user(
        username="knowledge_schema_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    schema_status = {
        "ok": False,
        "missing_tables": [],
        "missing_columns": {"generated_document": ["status"]},
        "migration_command": "flask --app run:app db upgrade",
    }
    monkeypatch.setattr(
        "app.admin.routes.database_schema_status",
        lambda: schema_status,
    )

    response = client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 503
    assert payload["error"] == "database_schema_outdated"
    assert payload["data"]["missing_columns"]["generated_document"] == ["status"]
    assert "db upgrade" in payload["message"]


def test_knowledge_reindex_registers_structured_rag_sources(
    client,
    make_user,
    make_task,
    make_error_entry,
    make_machine,
    make_material,
    auth_headers,
):
    """Verify reindex ingests structured maintenance records for RAG."""
    admin = make_user(
        username="knowledge_structured_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_structured_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    blocked = make_user(
        username="knowledge_structured_blocked",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_task(
        "Hydraulikfilter X900 pruefen",
        creator_username=user["username"],
        department_name="Produktion",
        description="Hydraulikfilter X900 taeglich kontrollieren.",
    )
    make_error_entry(
        "Anlage X900",
        "H900",
        "Hydraulikfilter Druckverlust",
        department_name="Produktion",
        possible_causes="Hydraulikfilter X900 verschmutzt",
        solution="Filter pruefen und bei Bedarf ersetzen",
    )
    machine_id = make_machine(name="Montage Linie", produced_item="Rahmen")
    make_material("Rahmen Rohling", 12.5, 8, machine_id=machine_id)

    reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": "Was wissen wir ueber Hydraulikfilter X900?"},
    )
    blocked_response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(blocked["username"]),
        json={"message": "Was wissen wir ueber Hydraulikfilter X900?"},
    )

    sources = chat_response.get_json()["sources"]
    blocked_sources = blocked_response.get_json()["sources"]
    assert reindex_response.status_code == 200
    assert reindex_response.get_json()["data"]["sources"]["task"] == 1
    assert reindex_response.get_json()["data"]["sources"]["error_entry"] == 1
    assert reindex_response.get_json()["data"]["sources"]["machine"] == 1
    assert reindex_response.get_json()["data"]["sources"]["inventory_material"] == 1
    assert "chunk_quality" in reindex_response.get_json()["data"]
    assert any(source["type"] == "knowledge" for source in sources)
    assert any("Hydraulikfilter" in source["title"] for source in sources)
    assert not any(source["type"] == "knowledge" for source in blocked_sources)


def test_knowledge_status_reports_rag_index_diagnostics(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify admins can inspect RAG index readiness and source diagnostics."""
    admin = make_user(
        username="knowledge_status_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_task(
        "Status RAG Hydraulik",
        creator_username=admin["username"],
        department_name="Instandhaltung",
        description="Hydraulikstatus fuer RAG Diagnose.",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )
    with client.application.app_context():
        db.session.add(
            KnowledgeDocument(
                source_type="upload",
                title="Fehlerhafte RAG Quelle",
                original_filename="broken.txt",
                status="error",
                error_message="Text konnte nicht extrahiert werden.",
                created_by=admin["id"],
            )
        )
        db.session.add(
            KnowledgeDocument(
                source_type="manual_training",
                title="Veraltete Trainingsquelle",
                original_filename="",
                status="stale",
                created_by=admin["id"],
            )
        )
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["documents"] >= 1
    assert payload["indexed"] >= 1
    assert payload["searchable_documents"] >= 1
    assert payload["chunks"] >= 1
    assert "stale" in payload
    assert "pending" in payload
    assert payload["diagnostics"]["rag_enabled"] is True
    assert payload["diagnostics"]["vector_store"] == "local"
    assert set(payload["chunk_quality"]) == {
        "accepted_chunks",
        "total_chunks_seen",
        "skipped_empty_chunks",
        "skipped_short_chunks",
        "skipped_duplicate_chunks",
        "skipped_low_quality_chunks",
        "skipped_bad_ocr_chunks",
        "affected_documents",
    }
    assert 0 <= payload["readiness_score"] < 100
    assert payload["readiness_reasons"]
    assert any(item["status"] == "error" for item in payload["problem_documents"])
    assert any(item["status"] == "stale" for item in payload["problem_documents"])
    assert any(item["source_type"] == "task" for item in payload["source_types"])


def test_knowledge_lifecycle_status_covers_training_rag_feedback_flow(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify the lifecycle read model covers draft, RAG use, and feedback review."""
    admin = make_user(
        username="knowledge_lifecycle_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_lifecycle_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "documents", can_view=True)
    admin_headers = auth_headers(admin["username"])
    user_headers = auth_headers(user["username"])

    create_response = client.post(
        "/api/v1/admin/ai/training",
        headers=admin_headers,
        json={
            "title": "Lifecycle Filterpflege",
            "question": "Was ist bei Lifecycle Filterpflege wichtig?",
            "answer": (
                "Lifecycle Filterpflege taeglich pruefen und Druckverlust " "dokumentieren."
            ),
            "keywords": "Lifecycle, Filterpflege, Druckverlust",
            "department": "Produktion",
        },
    )
    reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex?mode=stale",
        headers=admin_headers,
    )
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=user_headers,
        json={"message": "Was ist bei Lifecycle Filterpflege wichtig?"},
    )
    chat_payload = chat_response.get_json()
    feedback_response = client.post(
        "/api/v1/ai/feedback",
        headers=user_headers,
        json={
            "chat_message_id": chat_payload["chat_message_id"],
            "rating": "helpful",
            "sources": chat_payload["sources"],
        },
    )
    status_response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=admin_headers,
    )

    lifecycle = status_response.get_json()["data"]["lifecycle"]
    step_keys = {step["key"] for step in lifecycle["steps"]}
    assert create_response.status_code == 201
    assert reindex_response.status_code == 200
    assert chat_response.status_code == 200
    assert any(source["type"] == "knowledge" for source in chat_payload["sources"])
    assert feedback_response.status_code == 201
    assert status_response.status_code == 200
    assert lifecycle["indexed_documents"] >= 1
    assert lifecycle["drafts"] >= 1
    assert lifecycle["feedback_open"] >= 1
    assert lifecycle["rag_quality_gate"]["enabled"] is True
    assert lifecycle["rag_quality_gate"]["non_approved_indexed_documents"] >= 1
    assert lifecycle["rag_quality_gate"]["quality_weighted_indexed_documents"] >= 1
    assert {"draft_creation", "rag_usage", "feedback", "knowledge_gaps"} <= step_keys


def test_task_update_marks_rag_source_stale_and_reindex_recovers(
    app,
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify changed source data becomes stale and can be reindexed granularly."""
    admin = make_user(
        username="knowledge_stale_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="knowledge_stale_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Stale RAG Task",
        creator_username=user["username"],
        department_name="Instandhaltung",
        description="Alter RAG Inhalt",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    update_response = client.put(
        f"/api/v1/tasks/{task_id}",
        headers=auth_headers(user["username"]),
        json={"title": "Aktualisierter Stale RAG Task"},
    )
    stale_response = client.get(
        "/api/v1/admin/ai/knowledge/status",
        headers=auth_headers(admin["username"]),
    )
    stale_reindex_response = client.post(
        "/api/v1/admin/ai/knowledge/reindex?mode=stale",
        headers=auth_headers(admin["username"]),
    )

    with app.app_context():
        db.session.expire_all()
        document = KnowledgeDocument.query.filter_by(
            source_type="task",
            source_id=task_id,
        ).one()
        document_id = document.id
        assert document.status == "indexed"
        assert document.title == "Aktualisierter Stale RAG Task"

    single_reindex_response = client.post(
        f"/api/v1/admin/ai/knowledge/{document_id}/reindex",
        headers=auth_headers(admin["username"]),
    )

    assert update_response.status_code == 200
    assert stale_response.status_code == 200
    assert stale_response.get_json()["data"]["stale"] >= 1
    assert stale_reindex_response.status_code == 200
    assert stale_reindex_response.get_json()["data"]["documents"] == 1
    assert single_reindex_response.status_code == 200
    assert single_reindex_response.get_json()["data"]["status"] == "indexed"


def test_order_plan_selects_machine_staff_and_material(
    app,
    client,
    make_user,
    make_machine,
    make_material,
    make_employee,
    auth_headers,
):
    """Verify the order planner checks machine fit, staffing and stock."""
    admin = make_user(
        username="order_plan_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(
        name="Deckel Linie 1",
        produced_item="Deckel",
        required_employees=2,
    )
    make_material("Deckel Rohling", 1.5, 12, machine_id=machine_id)
    first_employee_id = make_employee(
        personnel_number="OP-001",
        name="Anna Plan",
        department="Produktion",
        qualifications="Deckel Linie",
    )
    second_employee_id = make_employee(
        personnel_number="OP-002",
        name="Ben Plan",
        department="Produktion",
        qualifications="Deckel Linie",
    )
    with app.app_context():
        db.session.add(
            EmployeeMachineQualification(
                employee_id=first_employee_id,
                machine_id=machine_id,
                level="trained",
            )
        )
        db.session.add(
            EmployeeMachineQualification(
                employee_id=second_employee_id,
                machine_id=machine_id,
                level="expert",
            )
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/order-plan",
        headers=auth_headers(admin["username"]),
        json={
            "product": "Deckel",
            "quantity": 10,
            "department": "Produktion",
            "work_date": "2026-05-18",
        },
    )

    payload = response.get_json()["data"]
    recommended = payload["recommended_plan"]
    assert response.status_code == 200
    assert payload["type"] == "order_plan"
    assert recommended["machine"]["id"] == machine_id
    assert recommended["status"] == "feasible"
    assert recommended["material_check"]["status"] == "enough"
    assert recommended["staffing"]["status"] == "covered"
    assert len(recommended["staffing"]["assigned_employees"]) == 2
    assert payload["diagnostics"]["workflow"] == "order_planning"


def test_order_plan_reports_material_shortage(
    client,
    make_user,
    make_machine,
    make_material,
    make_employee,
    auth_headers,
):
    """Verify the order planner exposes missing stock as a blocker."""
    admin = make_user(
        username="order_shortage_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Gehaeuse Linie", produced_item="Gehaeuse")
    make_material("Gehaeuse Rohling", 2.0, 3, machine_id=machine_id)
    make_employee(
        personnel_number="OP-003",
        name="Cara Plan",
        department="Produktion",
        qualifications="Gehaeuse Linie",
    )

    response = client.post(
        "/api/v1/ai/order-plan",
        headers=auth_headers(admin["username"]),
        json={"product": "Gehaeuse", "quantity": 5, "department": "Produktion"},
    )

    recommended = response.get_json()["data"]["recommended_plan"]
    assert response.status_code == 200
    assert recommended["status"] == "blocked"
    assert recommended["material_check"]["status"] == "shortage"
    assert recommended["material_check"]["missing"][0]["shortage"] == 2
    assert "fehlen" in recommended["blockers"][0]


def test_ai_chat_can_return_order_plan(
    app,
    client,
    make_user,
    make_machine,
    make_material,
    make_employee,
    auth_headers,
):
    """Verify chat can trigger the structured order planning workflow."""
    admin = make_user(
        username="order_chat_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Pumpen Linie", produced_item="Pumpe")
    make_material("Pumpen Rohling", 3.0, 8, machine_id=machine_id)
    employee_id = make_employee(
        personnel_number="OP-004",
        name="Dina Plan",
        department="Produktion",
        qualifications="Pumpen Linie",
    )
    with app.app_context():
        db.session.add(
            EmployeeMachineQualification(
                employee_id=employee_id,
                machine_id=machine_id,
                level="trained",
            )
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(admin["username"]),
        json={"message": "Plane Auftrag 4 Stueck Pumpe mit Maschine und Personal"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["type"] == "order_plan"
    assert payload["data"]["recommended_plan"]["machine"]["id"] == machine_id
    assert "Auftragsplanung" in payload["answer"]


def test_ai_workflow_routing_uses_balanced_defaults(app):
    """Verify workflow routing selects models, temperature and output budgets."""
    with app.app_context():
        app.config["OPENAI_MODEL_FAST"] = "fast-test-model"
        app.config["OPENAI_MODEL_BALANCED"] = "balanced-test-model"
        app.config["OPENAI_MODEL_QUALITY"] = "quality-test-model"

        task_profile = workflow_profile("task_suggestion")
        priority_profile = workflow_profile("task_prioritization")
        chat_profile = workflow_profile("chat")
        quality_profile = workflow_profile("quality_analysis")

    assert task_profile.model == "fast-test-model"
    assert task_profile.tier == "fast"
    assert task_profile.temperature == 0.1
    assert priority_profile.model == "fast-test-model"
    assert priority_profile.timeout_seconds == 6.0
    assert priority_profile.max_retries == 0
    assert chat_profile.model == "balanced-test-model"
    assert chat_profile.tier == "balanced"
    assert chat_profile.max_tokens == 750
    assert quality_profile.model == "quality-test-model"
    assert quality_profile.tier == "quality"


def test_ai_workflow_routing_falls_back_to_configured_model(app):
    """Verify missing tier overrides use the configured base model."""
    with app.app_context():
        for key in ("OPENAI_MODEL_FAST", "OPENAI_MODEL_BALANCED", "OPENAI_MODEL_QUALITY"):
            app.config.pop(key, None)

        task_profile = workflow_profile("task_suggestion")
        chat_profile = workflow_profile("chat")
        quality_profile = workflow_profile("quality_analysis")

    assert task_profile.model == "test-model"
    assert chat_profile.model == "test-model"
    assert quality_profile.model == "test-model"


def test_ai_audit_stores_usage_metrics_without_content(app, monkeypatch):
    """Verify audit events store usage metadata but no prompts or answers."""
    monkeypatch.setenv("AI_PRICE_TEST_MODEL_INPUT_PER_1M", "1")
    monkeypatch.setenv("AI_PRICE_TEST_MODEL_OUTPUT_PER_1M", "2")

    with app.app_context():
        cost = estimate_cost_usd("test-model", 1000, 500)
        event_id = create_ai_audit_event(
            None,
            "assistant",
            {
                "status": "openai_used",
                "provider": "openai",
                "model": "test-model",
                "model_tier": "balanced",
                "temperature": 0.2,
                "latency_ms": 123,
                "input_tokens": 1000,
                "output_tokens": 500,
                "cached_tokens": 0,
                "total_tokens": 1500,
                "estimated_cost_usd": cost,
            },
        )
        event = db.session.get(AIAuditEvent, event_id)
        assert event.model == "test-model"
        assert event.model_tier == "balanced"
        assert event.temperature == 0.2
        assert event.latency_ms == 123
        assert event.input_tokens == 1000
        assert event.output_tokens == 500
        assert event.estimated_cost_usd == 0.002
        assert not hasattr(event, "prompt")
        assert not hasattr(event, "response")


def test_ai_feedback_validates_rating_and_required_text(
    client,
    make_user,
    auth_headers,
):
    """Verify AI feedback validation and persistence response shape."""
    user = make_user(username="ai_feedback_user")
    headers = auth_headers(user["username"])

    invalid_rating = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={"prompt": "p", "response": "r", "rating": "ok"},
    )
    missing_text = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={"rating": "helpful", "prompt": "", "response": "r"},
    )
    valid_response = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={
            "prompt": "Was bedeutet E104?",
            "response": "Sensor pruefen",
            "rating": "helpful",
            "comment": "Passt",
        },
    )

    assert invalid_rating.status_code == 400
    assert missing_text.status_code == 400
    assert valid_response.status_code == 201
    assert valid_response.get_json()["rating"] == "helpful"


def test_ai_feedback_links_chat_message_without_sources(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify feedback can reference a saved chat answer even without sources."""
    user = make_user(username="ai_feedback_chat_user")
    headers = auth_headers(user["username"])
    chat_response = client.post(
        "/api/v1/ai/chat",
        headers=headers,
        json={"message": "Was ist Predictive Maintenance?"},
    )
    chat_payload = chat_response.get_json()

    feedback_response = client.post(
        "/api/v1/ai/feedback",
        headers=headers,
        json={
            "chat_message_id": chat_payload["chat_message_id"],
            "rating": "partially_helpful",
            "comment": "Teilweise gut, Quellen fehlen.",
        },
    )
    feedback_payload = feedback_response.get_json()

    with app.app_context():
        feedback_entry = db.session.get(AIFeedback, feedback_payload["id"])
        stored_prompt = feedback_entry.prompt
        stored_source_count = feedback_entry.source_count
        stored_sources = feedback_entry.sources()

    assert chat_response.status_code == 200
    assert feedback_response.status_code == 201
    assert feedback_payload["rating"] == "partially_helpful"
    assert feedback_payload["chat_message_id"] == chat_payload["chat_message_id"]
    assert feedback_payload["audit_event_id"] == chat_payload["diagnostics"]["audit_event_id"]
    assert feedback_payload["source_count"] == 0
    assert stored_prompt == "Was ist Predictive Maintenance?"
    assert stored_source_count == 0
    assert stored_sources == []


def test_ai_feedback_stores_source_and_chunk_metadata(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify feedback stores source and chunk links without mutating knowledge."""
    user = make_user(username="ai_feedback_sources_user")
    with app.app_context():
        event_id = create_ai_audit_event(
            user=type("UserStub", (), {"id": user["id"]})(),
            workflow="assistant",
            diagnostics={"status": "local_answer"},
            source_count=1,
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/feedback",
        headers=auth_headers(user["username"]),
        json={
            "prompt": "Wie behebe ich E104?",
            "response": "Sensor pruefen.",
            "rating": "not_helpful",
            "audit_event_id": event_id,
            "sources": [
                {
                    "type": "knowledge",
                    "id": 7,
                    "chunk_id": 13,
                    "title": "Sensor Manual",
                    "module": "knowledge",
                    "score": 42,
                }
            ],
        },
    )
    payload = response.get_json()

    with app.app_context():
        feedback_entry = db.session.get(AIFeedback, payload["id"])
        stored_source = feedback_entry.sources()[0]
        stored_audit_event_id = feedback_entry.audit_event_id

    assert response.status_code == 201
    assert payload["source_count"] == 1
    assert payload["review_status"] == "open"
    assert stored_source["id"] == 7
    assert stored_source["chunk_id"] == 13
    assert stored_audit_event_id == event_id


def test_ai_status_is_admin_only_and_redacted(app, client, make_user, auth_headers):
    """Verify AI status requires admin access and never exposes API keys."""
    admin = make_user(
        username="ai_status_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(username="ai_status_user")
    with app.app_context():
        from app.ai import status as ai_status_module

        app.config["AI_PROVIDER"] = "mock"
        app.config["OPENAI_API_KEY"] = ""
        ai_status_module.LAST_OPENAI_ERROR = None

    forbidden_response = client.get(
        "/api/v1/ai/status",
        headers=auth_headers(user["username"]),
    )
    admin_response = client.get(
        "/api/v1/ai/status",
        headers=auth_headers(admin["username"]),
    )

    assert forbidden_response.status_code == 403
    assert admin_response.status_code == 200
    assert "api_key" not in str(admin_response.get_json()).lower().replace(
        "api_key_configured",
        "",
    )
    payload = admin_response.get_json()
    assert payload["api_key_configured"] is False
    assert payload["provider_status"]["provider"] == "mock"
    assert payload["provider_status"]["configuration_action"] == "none"
    assert "Provider" in payload["provider_status"]["recommended_action"]
    assert any(
        item["provider"] == "openai_compatible" and item["status"] == "supported"
        for item in payload["provider_catalog"]
    )
    assert any(
        item["provider"] == "gemini"
        and item["status"] == "planned"
        and item["effective_fallback"] == "mock"
        for item in payload["provider_catalog"]
    )
    assert payload["embedding_provider_status"]["provider"] == "hashing"
    assert payload["embedding_provider_status"]["configuration_action"] == "none"
    assert "Embedding" in payload["embedding_provider_status"]["recommended_action"]
    assert any(
        item["provider"] == "hashing" and item["status"] == "supported"
        for item in payload["embedding_provider_catalog"]
    )
    assert any(
        item["provider"] == "openai_compatible"
        and item["requires_base_url"] is True
        and item["effective_fallback"] == "hashing"
        for item in payload["embedding_provider_catalog"]
    )
    assert payload["readiness"]["ready"] is True
    assert payload["readiness"]["degraded_components"] == []
    assert payload["readiness"]["actions"] == []
    assert payload["readiness"]["next_action"] is None


def test_ai_status_reports_effective_provider_for_unsupported_provider(
    app,
    client,
    make_user,
    auth_headers,
):
    """Verify admin AI status shows safe fallback for unsupported providers."""
    admin = make_user(
        username="ai_status_unsupported_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        app.config["AI_PROVIDER"] = "gemini"
        app.config["OPENAI_API_KEY"] = "test-key"

    response = client.get(
        "/api/v1/ai/status",
        headers=auth_headers(admin["username"]),
    )
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["provider"] == "gemini"
    assert payload["provider_status"]["provider"] == "gemini"
    assert payload["provider_status"]["reason"] == "unsupported_provider"
    assert payload["provider_status"]["effective_provider"] == "mock"
    assert payload["provider_status"]["configuration_action"] == "select_supported_provider"
    assert "AI_PROVIDER" in payload["provider_status"]["recommended_action"]
    gemini_entry = next(
        item for item in payload["provider_catalog"] if item["provider"] == "gemini"
    )
    assert gemini_entry["status"] == "planned"
    assert gemini_entry["mode"] == "unsupported"
    assert payload["readiness"]["ready"] is False
    assert "provider" in payload["readiness"]["degraded_components"]
    assert payload["readiness"]["next_action"]["component"] == "provider"
    assert (
        payload["readiness"]["next_action"]["configuration_action"] == "select_supported_provider"
    )
    assert "AI_PROVIDER" in payload["readiness"]["next_action"]["recommended_action"]


def test_daily_briefing_respects_permissions_and_uses_local_fallback(
    client,
    make_user,
    make_task,
    make_error_entry,
    auth_headers,
):
    """Verify daily briefing returns only permitted local sections."""
    user = make_user(
        username="briefing_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    make_task(
        "Ueberfaelliger Task",
        creator_username=user["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
        due_date_value=date.today() - timedelta(days=1),
    )
    make_error_entry(
        "Anlage Briefing",
        "E555",
        "Neuer Fehler",
        department_name="Produktion",
    )

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    section_types = {section["type"] for section in payload["sections"]}
    assert response.status_code == 200
    assert payload["diagnostics"]["status"] == "local_answer"
    assert "tasks" in section_types
    assert "errors" in section_types
    assert "documents" not in section_types


def test_daily_briefing_includes_recurring_issue_trends(
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify daily briefing surfaces recurring visible error trends."""
    user = make_user(
        username="briefing_recurring_issue_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        "Anlage Trend",
        "TR104",
        "Sensor Signal fehlt",
        department_name="Instandhaltung",
        description="Sensor Signal fehlt sporadisch.",
        solution="Sensor reinigen",
    )
    make_error_entry(
        "Anlage Trend",
        "TR104",
        "Sensor erkennt Produkt nicht",
        department_name="Instandhaltung",
        description="Sensor meldet kein Signal.",
        solution="Sensor reinigen",
    )

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    recurring_section = next(
        section for section in payload["sections"] if section["type"] == "recurring_issues"
    )
    assert response.status_code == 200
    assert recurring_section["count"] == 1
    assert recurring_section["items"][0]["occurrence_count"] == 2
    assert "Anlage Trend" in recurring_section["items"][0]["title"]


def test_daily_briefing_includes_rag_knowledge_section_after_reindex(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify daily briefing can include visible indexed RAG context."""
    admin = make_user(
        username="briefing_rag_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="briefing_rag_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_task(
        "Kritische Wartung Maschine RAG",
        creator_username=user["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
        description="Maschine RAG braucht Wartung wegen Stoerung.",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    section_types = {section["type"] for section in payload["sections"]}
    assert response.status_code == 200
    assert "knowledge" in section_types
    assert payload["diagnostics"]["rag_source_count"] >= 1


def test_daily_briefing_returns_no_sections_without_permissions(
    client,
    make_user,
    make_task,
    make_error_entry,
    set_dashboard_permission,
    auth_headers,
):
    """Verify daily briefing does not expose sections without dashboard rights."""
    user = make_user(
        username="briefing_no_rights_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    make_task(
        "Verdeckter Briefing Task",
        creator_username=user["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
        due_date_value=date.today() - timedelta(days=1),
    )
    make_error_entry(
        "Anlage Briefing Sperre",
        "E556",
        "Verdeckter Fehler",
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "tasks", can_view=False)
    set_dashboard_permission(user["username"], "errors", can_view=False)

    response = client.get(
        "/api/v1/ai/daily-briefing",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["sections"] == []
    assert payload["summary"] == "Heute sind keine kritischen Hinweise sichtbar."


def test_dashboard_contains_daily_briefing_and_priority_ui(client):
    """Verify dashboard exposes briefing and task priority UI hooks."""
    response = client.get("/")
    script_response = client.get("/static/pages/dashboard-island.js")
    css_response = client.get("/static/css/output.css")
    html = response.get_data(as_text=True)
    script = dashboard_runtime_source(client)
    source = html + script
    chat_script = chat_runtime_source()
    css = css_response.get_data(as_text=True)

    assert response.status_code == 200
    assert script_response.status_code == 200
    assert css_response.status_code == 200
    assert "maintenance-dashboard-root" in html
    assert "data-react-dashboard-fallback" not in html
    assert "data-ai-ops-cockpit" not in html
    assert "data-daily-briefing-list" in source
    assert "data-dashboard-priority-list" in source
    assert "data-ai-ops-priority-rail" in source
    assert "data-ai-system-rail" in source
    assert "data-ai-risk-radar" in source
    assert "data-ai-knowledge-health" in source
    assert "data-dashboard-low-confidence-count" in source
    assert "data-dashboard-frequent-codes" in source
    assert "maintenance-shell-chat-root" in html
    assert "data-react-shell-chat-fallback" in html
    assert "data-chat-suggestions" in chat_script
    assert "data-chat-history-panel" in chat_script
    assert "data-chat-history-search" in chat_script
    assert ".chat-history-item" in css
    assert "briefingItems" in script
    assert "prioritySignals" in script
    assert "/api/v1/admin/ai/retrieval-telemetry" in script
    assert "/api/v1/admin/ai/knowledge/status" in script
    assert "/api/v1/admin/ai/knowledge-gaps" in script
    assert "/api/v1/ai/status" in script
    assert "/api/v1/ai/chat" in chat_script
    assert "maintenance_ai_chat_session_id" in chat_script
    assert "session_id: chatSessionId()" in chat_script
    assert "resetChatSession()" in chat_script
    assert "answerFromPayload" in chat_script
    assert "fallback_used" in chat_script
    assert "api_key_missing" in chat_script
    assert "openai_error" in chat_script


def test_admin_users_page_contains_ai_analytics_ui(client):
    """Verify Admin Users exposes React AI analytics UI hooks."""
    page_response = client.get("/admin/users")
    html = page_response.get_data(as_text=True)
    runtime = admin_users_runtime_source()

    assert page_response.status_code == 200
    assert "maintenance-admin-users-root" in html
    assert "data-react-admin-users-fallback" not in html
    assert "data-ai-analytics-card" in runtime
    assert "data-ai-latency" in runtime
    assert "data-ai-tokens" in runtime
    assert "data-ai-cost" in runtime
    assert "data-ai-cost-status" in runtime
    assert "data-ai-user-costs" in runtime
    assert "data-ai-workflows" in runtime
    assert "data-ai-error-categories" in runtime
    assert "data-audit-log-list" in runtime
    assert "data-backup-list" in runtime
    assert "data-permission-defaults" in runtime
    assert "/api/v1/admin/ai/summary" in runtime
    assert "AiAnalyticsPanel" in runtime
    assert "props.userMetrics.map" in runtime
    assert "/api/v1/admin/audit-log" in runtime
    assert "/api/v1/admin/backups" in runtime
    assert "/api/v1/admin/permissions/schema" in runtime


def chat_runtime_source():
    """Return the React shell chat source."""
    return (REPO_ROOT / "frontend" / "src" / "layout" / "ShellChatWidget.tsx").read_text(
        encoding="utf-8"
    )


def dashboard_runtime_source(client):
    """Return the React dashboard runtime and route loader source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "dashboard").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "dashboard").rglob("*.tsx"))
    source_paths.append(REPO_ROOT / "app" / "static" / "pages" / "dashboard-island.js")
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def admin_ai_runtime_source(client):
    """Return the React AI admin runtime and route loader source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "admin-ai").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "admin-ai").rglob("*.tsx"))
    source_paths.append(REPO_ROOT / "app" / "static" / "pages" / "admin-ai-island.js")
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def admin_users_runtime_source():
    """Return the React admin users runtime and route loader source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "admin-users").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "admin-users").rglob("*.tsx"))
    source_paths.append(REPO_ROOT / "app" / "static" / "pages" / "admin-users-island.js")
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def document_runtime_source():
    """Return the React document runtime and route loader source."""
    source_paths = list((REPO_ROOT / "frontend" / "src" / "documents").rglob("*.ts"))
    source_paths.extend((REPO_ROOT / "frontend" / "src" / "documents").rglob("*.tsx"))
    source_paths.append(REPO_ROOT / "app" / "static" / "pages" / "documents-island.js")
    return "\n".join(path.read_text(encoding="utf-8") for path in source_paths)


def test_admin_ai_page_contains_ai_and_knowledge_ui(client):
    """Verify AI admin pages expose route-specific management UI hooks."""
    script_response = client.get("/static/pages/admin-ai-island.js")
    script = admin_ai_runtime_source(client)
    routes = {
        "/admin/ai": ("overview", 'id="ai-models"'),
        "/admin/ai/rag-board": ("rag_board", 'id="ai-rag-board"'),
        "/admin/ai/source-check": ("source_check", 'id="ai-source-check"'),
        "/admin/ai/prompt-faq": ("prompt_faq", 'id="ai-prompts"'),
        "/admin/ai/effectiveness": ("effectiveness", 'id="ai-costs"'),
        "/admin/ai/technical": ("technical", 'id="ai-technical"'),
    }
    pages = {}
    for route, (view_name, marker) in routes.items():
        response = client.get(route)
        page_html = response.get_data(as_text=True)
        pages[route] = page_html
        assert response.status_code == 200
        assert "maintenance-admin-ai-root" in page_html
        assert "data-react-admin-ai-fallback" not in page_html
        assert "data-admin-ai-page" not in page_html
        assert view_name in script
        assert marker in script

    legacy_routes = {
        "/admin/ai/prompts": "/admin/ai/prompt-faq",
        "/admin/ai/faq": "/admin/ai/prompt-faq",
        "/admin/ai/knowledge": "/admin/ai/rag-board",
        "/admin/ai/lab": "/admin/ai/source-check",
        "/admin/ai/costs": "/admin/ai/effectiveness",
        "/admin/ai/feedback": "/admin/ai/effectiveness",
        "/admin/ai/models": "/admin/ai#ai-models",
        "/admin/ai/retrieval": "/admin/ai/technical",
        "/admin/ai/training": "/admin/ai/rag-board",
        "/admin/ai/diagnostics": "/admin/ai/technical",
        "/admin/ai/indexing": "/admin/ai/technical",
    }
    for route, target in legacy_routes.items():
        response = client.get(route)
        assert response.status_code == 302
        assert response.headers["Location"] == target

    html = "\n".join(pages.values())
    source = html + script

    assert script_response.status_code == 200
    for route in routes:
        assert f'href: "{route}"' in script or f'href="{route}"' in script
    for section_id in (
        "ai-rag-board",
        "ai-source-check",
        "ai-prompts",
        "ai-faq",
        "ai-costs",
        "ai-technical",
        "ai-models",
        "ai-retrieval",
        "ai-knowledge-sources",
        "ai-training-data",
        "ai-diagnostics",
        "ai-feedback",
        "ai-indexing-status",
    ):
        assert f'id="{section_id}"' in source
    assert "data-ai-failed-queries" in source
    assert "indexed" in source
    assert "rejected" in source
    assert "active" in source
    assert "disabled" in source
    assert "Low Quality" in source
    assert "duplicate" in source
    assert "low_quality" in script
    assert "data-ai-health-panel" in source
    assert "data-retrieval-slo-panel" in source
    assert "data-retrieval-slo-kpi={key}" in source
    assert "data-retrieval-slo-trends" in source
    assert "data-retrieval-slo-warnings" in source
    assert "data-retrieval-evaluation-history-panel" in source
    assert "data-retrieval-evaluation-kpi={key}" in source
    assert "data-retrieval-evaluation-run" in source
    assert "data-retrieval-evaluation-regression" in source
    assert "data-retrieval-evaluation-runs" in source
    assert "data-ai-workflows" in source
    assert "data-ai-top-errors" in source
    assert "data-ai-chat-search" in source
    assert "data-ai-training-form" in source
    assert "data-ai-training-search" in source
    assert "data-ai-knowledge-upload" in source
    assert "data-ai-knowledge-search" in source
    assert "data-ai-knowledge-source" in source
    assert "data-ai-knowledge-quality" in source
    assert "data-knowledge-origin-legend" in source
    assert "is-source-automatic" in source
    assert "is-source-manual" in source
    assert "is-source-prebuilt" in source
    assert "data-knowledge-lifecycle-panel" in source
    assert "data-lifecycle-kpi={key}" in source
    assert '"drafts"' in source
    assert '"non_approved_indexed_documents"' in source
    assert "data-knowledge-lifecycle-review" in source
    assert "data-knowledge-lifecycle-gate" in source
    assert "data-knowledge-lifecycle-actions" in source
    assert "data-knowledge-lifecycle-steps" in source
    assert "data-knowledge-network-panel" in source
    assert "data-knowledge-network-canvas" in source
    assert "data-knowledge-network-detail" in source
    assert "data-knowledge-network-legend" in source
    assert "data-knowledge-network-search" in source
    assert "data-knowledge-network-focus-type" in source
    assert "data-knowledge-network-groups" in source
    assert "data-knowledge-network-relations" in source
    assert "data-retrieval-debug-panel" in source
    assert "data-retrieval-debug-rows" in source
    assert "data-retrieval-debug-type" in source
    assert "data-retrieval-flow-panel" in source
    assert "data-retrieval-flow-timeline" in source
    assert "data-retrieval-flow-source-map" in source
    assert "data-retrieval-flow-answer" in source
    assert "Qualität" in source
    assert "data-ai-knowledge-gaps" in source
    assert "data-ai-knowledge-gap-count" in source
    assert "data-rag-source-status" in source
    assert "data-rag-diagnostics" in source
    assert "data-rag-readiness-score" in source
    assert "data-rag-readiness-reasons" in source
    assert "data-rag-problem-documents" in source
    assert "data-rag-kpi={key}" in source
    assert '"searchable_documents"' in source
    assert '"stale"' in source
    assert "data-rag-vector-sync" in source
    assert "data-rag-vector-issues" in source
    assert "data-ai-reindex-stale" in source
    assert "data-ai-queue-stale" in source
    assert "data-ai-jobs" in source
    assert "data-ai-job-status" in source
    assert "data-queue-knowledge" in script
    assert "resolveAdminAiViewFromPathname" in script
    assert "maintenanceAdminAiReactRuntime" in script
    assert "/api/v1/admin/ai/events" in source
    assert "/api/v1/admin/ai/chats" in source
    assert "/api/v1/admin/ai/knowledge-gaps" in source
    assert "/api/v1/admin/jobs" in source
    assert "/api/v1/admin/ai/knowledge/upload" in source
    assert "/api/v1/admin/ai/knowledge/status" in source
    assert "vectorStatus" in source
    assert "retrievalSloValues" in script
    assert "retrievalSloValue" in script
    assert "evaluationHistory" in script
    assert "loadRetrievalTelemetry" in script
    assert "/api/v1/admin/ai/knowledge-network" in source
    assert "/api/v1/admin/ai/retrieval-telemetry" in source
    assert "/api/v1/admin/ai/retrieval-evaluations/run" in source
    assert "/api/v1/admin/ai/retrieval-debug" in source
    assert "/api/v1/admin/ai/knowledge/reindex/jobs" in source
    assert "/api/v1/admin/ai/knowledge/reindex" in source
    assert "?mode=stale" in source
    assert "/api/v1/admin/ai/training" in source
    assert "manual_training" in source
    assert "sourceTypeLabel" in script
    assert "qualityStatusClass" in script
    assert "knowledge-source-cell" in script
    assert "data-knowledge-quality-status" in script
    assert "qualityStatusLabel" in script
    assert "KnowledgeNetworkPanel" in script
    assert "data-knowledge-network-groups" in script
    assert "data-knowledge-network-relations" in script
    assert "data-network-relation" in script
    assert "networkTypeLabel" in script
    assert "focus_type" in script
    assert "task_question" in script
    assert "loadRetrievalDebug" in script
    assert "data-ai-failed-queries" in script
    assert "selectedRetrievalDebugItem" in script
    assert "data-retrieval-flow-summary" in script
    assert "decision_trace" in script
    assert "query_type" in script
    assert "data-knowledge-quality-select" in script
    assert "data-update-knowledge-quality" in script
    assert "/quality-status" in source
    assert "/reindex" in source


def test_admin_can_list_knowledge_gaps(app, client, make_user, auth_headers):
    """Verify master admins can inspect tracked knowledge gaps."""
    admin = make_user(
        username="knowledge_gap_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    with app.app_context():
        gap = KnowledgeGap(
            question="Wie behebe ich Fehler X?",
            question_hash="abc",
            context_text="Keine Quellen",
            machine="Anlage X",
            department="Instandhaltung",
            status="open",
        )
        db.session.add(gap)
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/knowledge-gaps",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["open_count"] == 1
    assert payload["items"][0]["question"] == "Wie behebe ich Fehler X?"


def test_admin_knowledge_gaps_include_detection_summary(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify knowledge-gap admin data includes actionable coverage detection."""
    admin = make_user(
        username="knowledge_gap_detection_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    make_error_entry(
        "Presse 42",
        "P42-HYD",
        "Hydraulikdruck faellt ab",
        description="Presse 42 verliert Hydraulikdruck.",
    )
    uncovered_error_id = make_error_entry(
        "Mixer 7",
        "M7-TEMP",
        "Temperatur zu hoch",
        description="Mixer 7 ueberhitzt wiederholt.",
    )
    with app.app_context():
        uncovered_error = db.session.get(ErrorEntry, uncovered_error_id)
        uncovered_error.severity = "critical"
        uncovered_error.repeat_count = 4
        uncovered_error.downtime_minutes = 45
        uncovered_machine = Machine(
            name="Kritische Presse 77",
            produced_item="Hydraulikteil",
            required_employees=2,
            criticality="critical",
            status="offline",
        )
        db.session.add_all(
            [
                uncovered_machine,
                KnowledgeGap(
                    question="Wie behebe ich Druckverlust an Presse 42?",
                    question_hash="gap-detect-1",
                    context_text="Keine Quellen",
                    machine="Presse 42",
                    department="Instandhaltung",
                    status="open",
                    occurrence_count=3,
                ),
                KnowledgeGap(
                    question="Welche Dichtung braucht Presse 42?",
                    question_hash="gap-detect-2",
                    context_text="Keine Quellen",
                    machine="Presse 42",
                    department="Instandhaltung",
                    status="open",
                    occurrence_count=1,
                ),
                KnowledgeDocument(
                    source_type="machine_manual",
                    title="Presse 99 Handbuch",
                    original_filename="presse-99.pdf",
                    department="Instandhaltung",
                    status="indexed",
                    is_public=True,
                ),
            ]
        )
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/knowledge-gaps?limit=10",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()["data"]
    detection = payload["detection"]
    machine_gap = detection["machine_gaps"][0]
    error_gap = detection["error_gaps"][0]
    action = detection["knowledge_gap_actions"][0]
    assert response.status_code == 200
    assert detection["summary"]["open_gap_count"] == 2
    assert detection["summary"]["recurring_gap_count"] == 1
    assert detection["summary"]["error_gap_count"] == 1
    assert detection["summary"]["uncovered_error_gap_count"] == 1
    assert detection["summary"]["critical_uncovered_error_gap_count"] == 1
    assert detection["summary"]["uncovered_machine_gap_count"] == 1
    assert detection["summary"]["critical_uncovered_machine_gap_count"] == 1
    assert machine_gap["machine"] == "Presse 42"
    assert machine_gap["coverage"] == "missing"
    assert machine_gap["document_count"] == 0
    assert machine_gap["related_error_count"] == 1
    assert error_gap["error_code"] == "P42-HYD"
    assert error_gap["machine"] == "Presse 42"
    assert error_gap["coverage"] == "missing"
    assert error_gap["open_gap_count"] == 2
    assert action["type"] == "missing_machine_documentation"
    assert action["priority"] == "high"
    assert action["target_type"] == "machine"
    assert action["machine"] == "Presse 42"
    assert action["next_steps"]
    assert "Fehlerhistorie" in " ".join(action["next_steps"])
    assert action["success_criteria"]
    assert any(
        item["type"] == "missing_error_documentation"
        and item["target"] == "P42-HYD"
        and item["target_type"] == "error_entry"
        and item["error_id"]
        and item["title"] == "Hydraulikdruck faellt ab"
        and item["next_steps"]
        for item in detection["knowledge_gap_actions"]
    )
    uncovered_gap = detection["uncovered_error_gaps"][0]
    assert uncovered_gap["error_code"] == "M7-TEMP"
    assert uncovered_gap["priority"] == "high"
    assert "kein passendes Fehler-Knowledge-Dokument" in uncovered_gap["reason"]
    uncovered_machine_gap = detection["uncovered_machine_gaps"][0]
    assert uncovered_machine_gap["machine"] == "Kritische Presse 77"
    assert uncovered_machine_gap["priority"] == "high"
    assert "maschinenspezifische Knowledge-Quelle" in uncovered_machine_gap["reason"]
    assert any(
        item["type"] == "missing_high_impact_error_documentation"
        and item["target"] == "M7-TEMP"
        and item["target_id"] == uncovered_error_id
        and "High-Impact-Fehler" in item["next_steps"][0]
        and item["success_criteria"]
        for item in detection["knowledge_gap_actions"]
    )
    assert any(
        item["type"] == "missing_high_impact_machine_documentation"
        and item["target"] == "Kritische Presse 77"
        and item["target_type"] == "machine"
        and item["next_steps"]
        and item["success_criteria"]
        for item in detection["knowledge_gap_actions"]
    )


def test_admin_knowledge_gap_detection_respects_error_specific_documents(
    app,
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """Verify high-impact errors with specific knowledge docs are not flagged."""
    admin = make_user(
        username="knowledge_gap_error_coverage_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    error_id = make_error_entry(
        "Ofen 3",
        "O3-HEAT",
        "Temperaturregelung instabil",
        description="Ofen 3 faellt wegen instabiler Regelung aus.",
    )
    with app.app_context():
        error_entry = db.session.get(ErrorEntry, error_id)
        error_entry.severity = "high"
        error_entry.repeat_count = 5
        covered_machine = Machine(
            name="Ofen 3",
            produced_item="Waermebehandlung",
            required_employees=1,
            criticality="high",
            status="running",
        )
        db.session.add(covered_machine)
        db.session.flush()
        db.session.add(
            KnowledgeDocument(
                source_type="error_catalog",
                source_id=error_id,
                title="O3-HEAT Fehlerleitfaden",
                original_filename="o3-heat.md",
                department="Produktion",
                status="indexed",
                is_public=True,
            )
        )
        db.session.add(
            KnowledgeDocument(
                source_type="machine_manual",
                source_id=covered_machine.id,
                title="Ofen 3 Maschinenhandbuch",
                original_filename="ofen-3.pdf",
                department="Produktion",
                status="indexed",
                is_public=True,
            )
        )
        db.session.commit()

    response = client.get(
        "/api/v1/admin/ai/knowledge-gaps?limit=10",
        headers=auth_headers(admin["username"]),
    )

    detection = response.get_json()["data"]["detection"]
    assert response.status_code == 200
    assert detection["summary"]["uncovered_error_gap_count"] == 0
    assert detection["summary"]["uncovered_machine_gap_count"] == 0
    assert detection["uncovered_error_gaps"] == []
    assert detection["uncovered_machine_gaps"] == []


def test_document_path_rejects_storage_escape(app):
    """Verify document path resolution blocks traversal outside document storage."""
    with app.app_context():
        document = GeneratedDocument(
            task_id=1,
            document_type="maintenance_report",
            title="Bad path",
            relative_path="../outside.html",
            department="Produktion",
            machine="",
            created_by=1,
        )

        with pytest.raises(ValueError, match="escapes document storage"):
            document_path(document)


def test_generated_document_download_uses_temp_storage(
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify generated documents are listed and downloaded from test storage."""
    user = make_user(
        username="document_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Dokument Task",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    list_response = client.get("/api/v1/documents", headers=headers)
    download_response = client.get(
        f"/api/v1/documents/{document_id}/download",
        headers=headers,
    )

    assert list_response.status_code == 200
    assert list_response.get_json()[0]["id"] == document_id
    assert download_response.status_code == 200
    assert b"report" in download_response.data


def test_document_review_only_allows_visible_documents(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify users can only review documents visible to their department."""
    user = make_user(
        username="document_review_visible",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review sichtbar",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    visible_document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
        machine="Anlage Review",
    )
    hidden_document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        relative_path="2026/05/task_hidden/maintenance_report.html",
        department="Produktion",
        machine="Anlage Review",
    )
    _write_report(
        app,
        visible_document_id,
        {
            "Maschine": "Anlage Review",
            "Ursache": "Sensor verschmutzt",
            "Durchgefuehrte Massnahme": "Sensor gereinigt",
            "Ergebnis": "Anlage laeuft stabil",
            "Notizen": "Nachkontrolle eingeplant",
        },
    )
    headers = auth_headers(user["username"])

    visible_response = client.post(
        f"/api/v1/documents/{visible_document_id}/review",
        headers=headers,
    )
    hidden_response = client.post(
        f"/api/v1/documents/{hidden_document_id}/review",
        headers=headers,
    )

    assert visible_response.status_code == 200
    assert hidden_response.status_code == 404


def test_document_review_missing_file_returns_404(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify document review reports missing files explicitly."""
    user = make_user(
        username="document_review_missing",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review Datei fehlt",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
    )
    _delete_document_file(app, document_id)

    response = client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=auth_headers(user["username"]),
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "document_file_not_found"
    assert response.get_json()["message"] == "Document file not found"


def test_document_review_local_fallback_finds_missing_required_fields(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify local review detects incomplete maintenance report fields."""
    user = make_user(
        username="document_review_incomplete",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review unvollstaendig",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Instandhaltung",
    )
    _write_report(
        app,
        document_id,
        {
            "Maschine": "-",
            "Ursache": "",
            "Durchgefuehrte Massnahme": "-",
            "Ergebnis": "",
            "Notizen": "-",
        },
    )

    response = client.post(
        f"/api/v1/documents/{document_id}/review",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    fields = {finding["field"] for finding in payload["findings"]}
    assert response.status_code == 200
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["status"] == "incomplete"
    assert fields == {
        "Maschine",
        "Ursache",
        "Durchgefuehrte Massnahme",
        "Ergebnis",
        "Notizen",
    }


def test_document_review_scores_complete_report_higher(
    app,
    client,
    make_user,
    make_task,
    make_document,
    auth_headers,
):
    """Verify complete reports receive better local review scores."""
    user = make_user(
        username="document_review_score",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    task_id = make_task(
        "Review Score",
        creator_username=user["username"],
        department_name="Instandhaltung",
    )
    incomplete_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        relative_path="2026/05/task_score_incomplete/maintenance_report.html",
        department="Instandhaltung",
    )
    complete_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        relative_path="2026/05/task_score_complete/maintenance_report.html",
        department="Instandhaltung",
    )
    _write_report(
        app,
        incomplete_id,
        {
            "Maschine": "-",
            "Ursache": "-",
            "Durchgefuehrte Massnahme": "-",
            "Ergebnis": "-",
            "Notizen": "-",
        },
    )
    _write_report(
        app,
        complete_id,
        {
            "Maschine": "Anlage 12",
            "Ursache": "Druckschwankung in der Versorgung",
            "Durchgefuehrte Massnahme": "Dichtung ersetzt und Druck geprueft",
            "Ergebnis": "Anlage arbeitet wieder im Sollbereich",
            "Notizen": "Ersatzdichtung nachbestellen",
        },
    )
    headers = auth_headers(user["username"])

    incomplete_response = client.post(
        f"/api/v1/documents/{incomplete_id}/review",
        headers=headers,
    )
    complete_response = client.post(
        f"/api/v1/documents/{complete_id}/review",
        headers=headers,
    )

    assert incomplete_response.status_code == 200
    assert complete_response.status_code == 200
    assert (
        complete_response.get_json()["quality_score"]
        > incomplete_response.get_json()["quality_score"]
    )
    assert complete_response.get_json()["status"] == "good"


def test_uploaded_document_check_validates_and_reviews_file(
    client,
    make_user,
    auth_headers,
):
    """Verify uploaded document checking handles missing, invalid and valid files."""
    user = make_user(
        username="document_upload_check",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    missing_response = client.post("/api/v1/documents/check", headers=headers)
    invalid_response = client.post(
        "/api/v1/documents/check",
        headers=headers,
        data={"file": (BytesIO(b"binary"), "report.pdf")},
        content_type="multipart/form-data",
    )
    valid_response = client.post(
        "/api/v1/documents/check",
        headers=headers,
        data={
            "file": (
                BytesIO(
                    b"Maschine: Anlage 7\n"
                    b"Ursache: Sensor verschmutzt\n"
                    b"Durchgefuehrte Massnahme: Sensor gereinigt\n"
                    b"Ergebnis: Anlage laeuft\n"
                    b"Notizen: Nachkontrolle geplant\n"
                ),
                "report.txt",
            ),
        },
        content_type="multipart/form-data",
    )

    payload = valid_response.get_json()
    assert missing_response.status_code == 400
    assert invalid_response.status_code == 400
    assert valid_response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["diagnostics"]["status"] == "local_answer"
    assert payload["data"]["status"] == "good"


def test_documents_page_contains_review_ui(client):
    """Verify the documents page and React runtime expose review UI hooks."""
    page_response = client.get("/documents")
    html = page_response.get_data(as_text=True)
    runtime = document_runtime_source()

    assert page_response.status_code == 200
    assert "maintenance-documents-root" in html
    assert "data-react-documents-fallback" not in html
    assert "data-document-review-panel" in runtime
    assert "data-document-review-findings" in runtime
    assert "data-document-upload-check-form" in runtime
    assert '"/api/v1/documents/check"' in runtime
    assert "checkUploadedDocument" in runtime
    assert "ReviewFindingItem" in runtime
    assert "waitForReactIsland" in runtime
    assert "initializeReactIslandFallback" not in runtime


def test_complete_task_can_generate_maintenance_report(
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify completing a task can generate document metadata and a temp file."""
    user = make_user(username="report_user")
    task_id = make_task("Bericht Task", creator_username=user["username"])

    response = client.post(
        f"/api/v1/tasks/{task_id}/complete",
        headers=auth_headers(user["username"]),
        json={"generate_report": True, "machine": "Anlage 7", "result": "OK"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["status"] == "done"
    assert payload["generated_document"]["machine"] == "Anlage 7"


def test_search_returns_only_dashboards_visible_to_user(
    client,
    make_user,
    make_task,
    make_error_entry,
    make_document,
    auth_headers,
):
    """Verify knowledge search respects dashboard permissions and department filters."""
    user = make_user(
        username="search_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    task_id = make_task(
        "Anlage Sensor pruefen",
        creator_username=user["username"],
        department_name="Produktion",
    )
    make_error_entry(
        "Anlage Sensor",
        "E111",
        "Sensorfehler",
        department_name="Produktion",
    )
    make_document(task_id=task_id, created_by=user["id"], department="Produktion")

    response = client.get(
        "/api/v1/search?q=Anlage",
        headers=auth_headers(user["username"]),
    )

    result_types = {result["type"] for result in response.get_json()["results"]}
    visible_results = response.get_json()["results"]
    task_result = next(result for result in visible_results if result["type"] == "task")
    error_result = next(result for result in visible_results if result["type"] == "error")
    assert response.status_code == 200
    assert "task" in result_types
    assert "error" in result_types
    assert "document" not in result_types
    assert task_result["entity_id"] == task_id
    assert task_result["ui_url"].startswith("/tasks?search=")
    assert task_result["url"] == f"/api/tasks/{task_id}"
    assert error_result["ui_url"].startswith("/errors?search=")
    assert "status" in error_result


def test_search_results_include_ui_links_for_core_entities(
    client,
    make_user,
    make_task,
    make_error_entry,
    make_document,
    auth_headers,
):
    """Verify search results expose UI deeplinks without removing API URLs."""
    user = make_user(
        username="search_admin_user",
        role=Role.MASTER_ADMIN,
        department_name="Produktion",
    )
    task_id = make_task(
        "Anlage Hydraulik pruefen",
        creator_username=user["username"],
        department_name="Produktion",
    )
    error_id = make_error_entry(
        "Anlage Hydraulik",
        "HYD-42",
        "Hydraulikdruck faellt",
        department_name="Produktion",
    )
    document_id = make_document(
        task_id=task_id,
        created_by=user["id"],
        department="Produktion",
        machine="Anlage Hydraulik",
    )

    response = client.get(
        "/api/v1/search?q=Anlage",
        headers=auth_headers(user["username"]),
    )

    results_by_type = {result["type"]: result for result in response.get_json()["results"]}
    assert response.status_code == 200
    assert results_by_type["task"]["entity_id"] == task_id
    assert results_by_type["task"]["ui_url"].startswith("/tasks?search=")
    assert results_by_type["task"]["url"] == f"/api/tasks/{task_id}"
    assert results_by_type["error"]["entity_id"] == error_id
    assert results_by_type["error"]["ui_url"].startswith("/errors?search=")
    assert results_by_type["error"]["url"] == f"/api/errors/{error_id}"
    assert results_by_type["document"]["entity_id"] == document_id
    assert results_by_type["document"]["ui_url"].startswith("/documents?search=")
    assert results_by_type["document"]["url"].startswith("/api/v1/documents/")


def test_search_requires_query(client, make_user, auth_headers):
    """Verify search rejects missing query text."""
    user = make_user(username="search_empty_user")

    response = client.get("/api/v1/search?q=   ", headers=auth_headers(user["username"]))

    assert response.status_code == 400


def _create_retrieval_debug_document(
    app,
    title,
    text,
    token_text,
    department,
    quality_status,
    created_by,
):
    """Create one indexed knowledge document for retrieval debug tests."""
    with app.app_context():
        document = KnowledgeDocument(
            source_type="upload",
            source_id=None,
            title=title,
            original_filename=f"{title}.txt",
            relative_path=f"uploads/{title}.txt",
            content_type="text/plain",
            department=department,
            status="indexed",
            quality_status=quality_status,
            is_public=True,
            chunk_count=1,
            created_by=created_by,
        )
        db.session.add(document)
        db.session.flush()
        db.session.add(
            KnowledgeChunk(
                document_id=document.id,
                chunk_index=0,
                text=text,
                token_text=token_text,
            )
        )
        db.session.commit()
        return document.id


def _write_report(app, document_id, rows):
    """Write a generated report table for a test document."""
    with app.app_context():
        document = db.session.get(GeneratedDocument, document_id)
        table_rows = "\n".join(
            f"<tr><th>{label}</th><td>{value}</td></tr>" for label, value in rows.items()
        )
        document_path(document).write_text(
            f"<html><body><table>{table_rows}</table></body></html>",
            encoding="utf-8",
        )


def _delete_document_file(app, document_id):
    """Delete the stored file for a test document."""
    with app.app_context():
        document = db.session.get(GeneratedDocument, document_id)
        path = document_path(document)
        if path.exists():
            path.unlink()
