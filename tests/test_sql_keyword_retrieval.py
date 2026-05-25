"""Tests for SQL keyword fallback retrieval."""

from datetime import UTC, datetime

from app.extensions import db
from app.models import Employee, KnowledgeDocument, Role, Task, User
from app.services.retrieval_service import retrieve_context
from app.services.sql_keyword_retrieval_service import retrieve_sql_keyword_fallback


def test_sql_keyword_fallback_finds_old_task_outside_structured_limit(
    app,
    client,
    make_user,
    make_task,
    auth_headers,
):
    """Verify chat retrieval finds an old task outside the standard recent window."""
    user = make_user(username="sql_fallback_old_task_user")
    old_task_id = make_task(
        "Sonderpruefung SQLFALLBACK900",
        creator_username=user["username"],
        description="Alter Task ausserhalb des normalen Retrieval-Limits.",
    )
    for index in range(35):
        make_task(
            f"Neuer Task {index}",
            creator_username=user["username"],
            description="Aktueller Task ohne Spezialbegriff.",
        )
    with app.app_context():
        old_task = db.session.get(Task, old_task_id)
        old_task.updated_at = datetime(2020, 1, 1, tzinfo=UTC)
        db.session.commit()

    response = client.post(
        "/api/v1/ai/chat",
        headers=auth_headers(user["username"]),
        json={"message": f"Zeige Task #{old_task_id} SQLFALLBACK900"},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert any(
        source["type"] == "task" and source["id"] == old_task_id for source in payload["sources"]
    )
    assert payload["diagnostics"]["empty_retrieval"] is False


def test_sql_keyword_fallback_prioritizes_exact_error_code(
    app,
    make_user,
    make_error_entry,
):
    """Verify exact error-code matches outrank broader keyword matches."""
    user = make_user(username="sql_fallback_error_user")
    exact_id = make_error_entry(
        "Presse 1",
        "E777",
        "Exakter Druckfehler",
        description="Druck Hydraulik.",
    )
    make_error_entry(
        "Presse 2",
        "E778",
        "Hydraulik Stoerung",
        description="Hydraulik mit anderem Fehlercode.",
    )

    with app.app_context():
        db_user = User.query.filter_by(username=user["username"]).one()
        result = retrieve_sql_keyword_fallback("Fehler E777 Hydraulik", db_user, limit=2)

    assert result["candidates"][0].source_type == "error"
    assert result["candidates"][0].source_id == exact_id


def test_sql_keyword_fallback_finds_machine_by_exact_name(app, make_user, make_machine):
    """Verify machine names are searched directly by SQL fallback."""
    user = make_user(username="sql_fallback_machine_user", role=Role.INSTANDHALTUNG)
    machine_id = make_machine(name="Presse SQL-42", produced_item="Deckel")

    with app.app_context():
        db_user = User.query.filter_by(username=user["username"]).one()
        result = retrieve_sql_keyword_fallback("Presse SQL-42", db_user, limit=2)

    assert any(
        candidate.source_type == "machine" and candidate.source_id == machine_id
        for candidate in result["candidates"]
    )


def test_retrieve_context_uses_sql_fallback_when_vector_is_empty(
    app,
    make_user,
    make_task,
):
    """Verify SQL fallback supplies sources when vector retrieval has no hits."""
    user = make_user(username="sql_fallback_vector_empty_user")
    old_task_id = make_task(
        "SQLONLY903 Altanlage pruefen",
        creator_username=user["username"],
        description="Seltener strukturierter Treffer nur ueber SQL-Fallback.",
    )
    for index in range(35):
        make_task(
            f"SQLONLY903 irrelevanter neuer Task {index}",
            creator_username=user["username"],
            description="Aktueller Task ohne den gesuchten Anlagenbezug.",
        )
    with app.app_context():
        old_task = db.session.get(Task, old_task_id)
        old_task.updated_at = datetime(2020, 1, 1, tzinfo=UTC)
        db.session.commit()
        db_user = User.query.filter_by(username=user["username"]).one()
        payload = retrieve_context("Altanlage pruefen", db_user)

    assert any(
        source["type"] == "task" and source["id"] == old_task_id for source in payload["sources"]
    )
    assert payload["retrieval_debug"]["vector_candidates_found"] == 0
    assert payload["retrieval_debug"]["sql_keyword_fallback_used"] is True
    assert payload["retrieval_debug"]["keyword_candidates_found"] >= 1


def test_sql_keyword_fallback_blocks_rejected_linked_source(
    app,
    make_user,
    make_machine,
):
    """Verify rejected knowledge quality blocks linked SQL fallback sources."""
    user = make_user(username="sql_fallback_rejected_user")
    machine_id = make_machine(name="Rejected SQL Machine", produced_item="Teil")
    with app.app_context():
        _create_linked_document(
            source_type="machine",
            source_id=machine_id,
            title="Rejected SQL Machine",
            department="Produktion",
            quality_status="rejected",
            created_by=user["id"],
        )
        db_user = User.query.filter_by(username=user["username"]).one()
        result = retrieve_sql_keyword_fallback("Rejected SQL Machine", db_user, limit=2)

    assert all(candidate.source_id != machine_id for candidate in result["candidates"])


def test_sql_keyword_fallback_blocks_foreign_department_task(
    app,
    make_user,
    make_task,
):
    """Verify department-scoped SQL fallback does not leak foreign tasks."""
    user = make_user(username="sql_fallback_department_user", department_name="Produktion")
    foreign = make_user(
        username="sql_fallback_department_foreign",
        department_name="Instandhaltung",
    )
    foreign_task_id = make_task(
        "Fremder SQLFALLBACK901 Task",
        creator_username=foreign["username"],
        department_name="Instandhaltung",
    )

    with app.app_context():
        db_user = User.query.filter_by(username=user["username"]).one()
        result = retrieve_sql_keyword_fallback("SQLFALLBACK901", db_user, limit=3)

    assert all(candidate.source_id != foreign_task_id for candidate in result["candidates"])


def test_sql_keyword_fallback_does_not_search_employee_data(app, make_user):
    """Verify employee records are not part of the general SQL fallback pool."""
    user = make_user(username="sql_fallback_no_employee_user")
    with app.app_context():
        employee = Employee(
            personnel_number="SQL-EMP-900",
            name="Secret Employee SQLFALLBACK902",
            department="Produktion",
        )
        db.session.add(employee)
        db.session.commit()
        db_user = User.query.filter_by(username=user["username"]).one()
        result = retrieve_sql_keyword_fallback("SQLFALLBACK902", db_user, limit=3)

    assert result["candidates"] == []
    assert "employees" not in result["data"]


def _create_linked_document(source_type, source_id, title, department, quality_status, created_by):
    """Create a linked knowledge document for source-visibility tests."""
    document = KnowledgeDocument(
        source_type=source_type,
        source_id=source_id,
        title=title,
        original_filename=f"{title}.txt",
        relative_path=f"uploads/{title}.txt",
        content_type="text/plain",
        department=department,
        status="indexed",
        quality_status=quality_status,
        is_public=True,
        chunk_count=0,
        created_by=created_by,
    )
    db.session.add(document)
    db.session.commit()
    return document.id
