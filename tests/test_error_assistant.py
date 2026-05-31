"""Tests for POST /api/v1/ai/error-assistant.

Covers: auth guard, input validation, response shape, local search,
error-code extraction, department scoping, limit parameter, and
empty-catalog behaviour.
"""

from datetime import date

from app.extensions import db
from app.models import Role, ShiftHandover, User

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_error_assistant_requires_auth(client):
    """Unauthenticated requests must be rejected with 401."""
    response = client.post("/api/v1/ai/error-assistant", json={"query": "Fehler E42"})
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


def test_error_assistant_rejects_missing_query(client, make_user, auth_headers):
    """Request without a query field must return 400."""
    user = make_user(username="ea_no_query")
    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={},
    )
    assert response.status_code == 400
    assert response.get_json()["success"] is False


def test_error_assistant_rejects_blank_query(client, make_user, auth_headers):
    """Request with a whitespace-only query must return 400."""
    user = make_user(username="ea_blank_query")
    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "   "},
    )
    assert response.status_code == 400


def test_error_assistant_rejects_query_over_limit(client, make_user, auth_headers):
    """Queries exceeding 1000 characters must return 400."""
    user = make_user(username="ea_long_query")
    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "x" * 1001},
    )
    assert response.status_code == 400


def test_error_assistant_rejects_invalid_limit(client, make_user, auth_headers):
    """A limit outside 1–20 must return 400."""
    user = make_user(username="ea_bad_limit")
    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Sensor defekt", "limit": 0},
    )
    assert response.status_code == 400


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


def test_error_assistant_response_shape(client, make_user, auth_headers):
    """Every successful response must expose all required top-level and diagnostic keys."""
    user = make_user(username="ea_shape")
    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Sensor meldet kein Signal"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True

    data = payload["data"]
    assert set(data.keys()) >= {
        "query",
        "matches",
        "causes",
        "fixes",
        "root_cause_analysis",
        "diagnostics",
    }

    diag = data["diagnostics"]
    assert set(diag.keys()) >= {
        "status",
        "provider",
        "match_count",
        "extracted_error_code",
        "extracted_machine",
        "ai_enhanced",
        "root_cause_confidence",
    }
    # In test mode the mock provider never enhances results
    assert diag["ai_enhanced"] is False

    rca = data["root_cause_analysis"]
    assert set(rca.keys()) >= {
        "summary",
        "possible_causes",
        "similar_cases",
        "next_steps",
        "confidence",
        "insufficient_evidence",
        "evidence",
    }
    assert rca["confidence"] == diag["root_cause_confidence"]


# ---------------------------------------------------------------------------
# Empty catalog
# ---------------------------------------------------------------------------


def test_error_assistant_empty_catalog(client, make_user, auth_headers):
    """A valid query against an empty catalog must succeed and return empty lists."""
    user = make_user(username="ea_empty")
    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Maschine 5 vibriert stark"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["matches"] == []
    assert data["causes"] == []
    assert data["fixes"] == []
    assert data["root_cause_analysis"]["insufficient_evidence"] is True
    assert data["root_cause_analysis"]["confidence"]["level"] == "low"
    assert data["root_cause_analysis"]["confidence"]["uncertainty"] == "high"
    assert data["diagnostics"]["match_count"] == 0


# ---------------------------------------------------------------------------
# Successful local search
# ---------------------------------------------------------------------------


def test_error_assistant_finds_matching_entry(client, make_user, make_error_entry, auth_headers):
    """A query matching catalog content must return causes and fixes from that entry."""
    user = make_user(
        username="ea_match_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        machine="Anlage 3",
        error_code="E42",
        title="Lager defekt",
        department_name="Instandhaltung",
        possible_causes="Lager verschlissen, Schmiermittel fehlt",
        solution="Lager austauschen und neu schmieren",
    )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Anlage 3 zeigt Fehler E42 — lautes Lagergeraeusch"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["diagnostics"]["match_count"] > 0
    assert len(data["matches"]) > 0
    assert len(data["causes"]) > 0
    assert len(data["fixes"]) > 0
    assert any("Lager" in c for c in data["causes"])
    assert any("schmieren" in f or "austauschen" in f for f in data["fixes"])
    rca = data["root_cause_analysis"]
    assert rca["insufficient_evidence"] is False
    assert rca["possible_causes"][0]["cause"] == "Lager verschlissen, Schmiermittel fehlt"
    assert rca["similar_cases"][0]["error_code"] == "E42"
    assert rca["evidence"]["similar_case_sources"][0]["error_code"] == "E42"
    assert rca["evidence"]["similar_case_sources"][0]["type"] == "error"
    assert rca["evidence"]["similar_case_sources"][0]["score"] >= 45
    assert rca["evidence"]["rag_sources"] == []
    fix_step = next(step for step in rca["next_steps"] if "Lager austauschen" in step["step"])
    assert fix_step["source"] == "similar_case_solution"
    assert fix_step["source_id"] == rca["similar_cases"][0]["id"]
    assert fix_step["error_code"] == "E42"
    assert rca["confidence"]["score"] >= 45
    assert rca["confidence"]["uncertainty"] in {"low", "medium", "high"}


def test_error_assistant_returns_rag_sources_and_task_draft(
    client,
    make_user,
    make_error_entry,
    auth_headers,
):
    """A fault query should return RAG sources and a read-only task draft."""
    admin = make_user(
        username="ea_rag_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    user = make_user(
        username="ea_rag_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    make_error_entry(
        machine="Anlage RAG Fehler",
        error_code="ER900",
        title="Hydraulikfilter Druckverlust",
        department_name="Instandhaltung",
        possible_causes="Hydraulikfilter verschmutzt",
        solution="Filter pruefen und Druck messen",
    )
    client.post(
        "/api/v1/admin/ai/knowledge/reindex",
        headers=auth_headers(admin["username"]),
    )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Anlage RAG Fehler meldet Hydraulikfilter Druckverlust"},
    )

    data = response.get_json()["data"]
    assert response.status_code == 200
    assert data["diagnostics"]["rag_source_count"] >= 1
    assert any(source["type"] == "knowledge" for source in data["sources"])
    rca_sources = data["root_cause_analysis"]["evidence"]["rag_sources"]
    assert rca_sources
    assert rca_sources[0]["type"] == "knowledge"
    assert rca_sources[0]["source_type"] == "error_entry"
    assert rca_sources[0]["source_id"]
    assert rca_sources[0]["chunk_id"]
    assert rca_sources[0]["module"] == "knowledge"
    assert rca_sources[0]["role_visibility"] == "department:Instandhaltung"
    assert rca_sources[0]["created_at"]
    assert rca_sources[0]["title"]
    assert "text" not in rca_sources[0]
    assert data["action_preview"]["type"] == "task_draft"
    assert data["action_preview"]["payload"]["status"] == "open"


def test_error_assistant_uses_visible_task_and_handover_history(
    app,
    client,
    make_user,
    make_error_entry,
    make_machine,
    make_task,
    auth_headers,
    set_dashboard_permission,
):
    """Root-cause analysis should include visible machine task and handover history."""
    user = make_user(
        username="ea_history_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    for dashboard in ("errors", "tasks", "shiftplans"):
        set_dashboard_permission(user["username"], dashboard, can_view=True)
    machine_id = make_machine(name="Anlage RCA 9")
    task_id = make_task(
        "Anlage RCA 9 Hydraulikleck pruefen",
        user["username"],
        department_name="Instandhaltung",
        description="Aktuelle Stoerung: Hydraulikleck und Druckverlust an Anlage RCA 9.",
    )
    make_error_entry(
        machine="Anlage RCA 9",
        error_code="RC900",
        title="Hydraulikleck",
        department_name="Instandhaltung",
        possible_causes="Dichtung am Ventilblock undicht",
        solution="Ventilblock pruefen und Dichtung ersetzen",
    )

    with app.app_context():
        db_user = db.session.get(User, user["id"])
        handover = ShiftHandover(
            department="Instandhaltung",
            area="RCA",
            machine_id=machine_id,
            shift_date=date.today(),
            shift_type="Spaet",
            status="open",
            handed_over_by=db_user.id,
            content="Anlage RCA 9 zeigt weiter Druckverlust.",
            open_tasks="Hydraulikleck pruefen und Task nachziehen.",
            machine_notes="Ventilblock und Dichtung beobachten.",
            next_notes="Drucktest in der naechsten Schicht wiederholen.",
        )
        db.session.add(handover)
        db.session.commit()
        handover_id = handover.id

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Anlage RCA 9 meldet RC900 Hydraulikleck und Druckverlust"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    evidence = data["root_cause_analysis"]["evidence"]
    history = evidence["history"]
    assert data["diagnostics"]["history_source_count"] == 2
    assert data["root_cause_analysis"]["confidence"]["uncertainty"] in {
        "low",
        "medium",
        "high",
    }
    assert evidence["history_source_count"] == 2
    assert history["uses_only_visible_sources"] is True
    assert history["tasks"][0]["id"] == task_id
    assert history["shift_handovers"][0]["id"] == handover_id
    assert {"task", "shift_handover"} <= set(history["source_types"])
    step_sources = {step["source"] for step in data["root_cause_analysis"]["next_steps"]}
    assert "visible_task_history" in step_sources
    assert "visible_shift_handover_history" in step_sources
    task_step = next(
        step
        for step in data["root_cause_analysis"]["next_steps"]
        if step["source"] == "visible_task_history"
    )
    handover_step = next(
        step
        for step in data["root_cause_analysis"]["next_steps"]
        if step["source"] == "visible_shift_handover_history"
    )
    assert task_step["source_id"] == task_id
    assert task_step["title"]
    assert handover_step["source_id"] == handover_id
    assert handover_step["due_date"] == date.today().isoformat()


def test_error_assistant_does_not_leak_history_without_dashboard_permissions(
    app,
    client,
    make_user,
    make_error_entry,
    make_machine,
    make_task,
    auth_headers,
    set_dashboard_permission,
):
    """RCA history evidence must stay empty without task and handover permissions."""
    user = make_user(
        username="ea_history_no_leak_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    set_dashboard_permission(user["username"], "errors", can_view=True)
    set_dashboard_permission(user["username"], "tasks", can_view=False)
    set_dashboard_permission(user["username"], "shiftplans", can_view=False)
    machine_id = make_machine(name="Anlage RCA 10")
    make_task(
        "Anlage RCA 10 Hydraulikleck pruefen",
        user["username"],
        department_name="Instandhaltung",
        description="Diese Task-Historie darf ohne Recht nicht in RCA erscheinen.",
    )
    make_error_entry(
        machine="Anlage RCA 10",
        error_code="RC901",
        title="Hydraulikleck",
        department_name="Instandhaltung",
        possible_causes="Dichtung am Ventilblock undicht",
        solution="Ventilblock pruefen und Dichtung ersetzen",
    )

    with app.app_context():
        db_user = db.session.get(User, user["id"])
        db.session.add(
            ShiftHandover(
                department="Instandhaltung",
                area="RCA",
                machine_id=machine_id,
                shift_date=date.today(),
                shift_type="Spaet",
                status="open",
                handed_over_by=db_user.id,
                content="Diese Uebergabe darf ohne Recht nicht in RCA erscheinen.",
                open_tasks="Hydraulikleck pruefen.",
            )
        )
        db.session.commit()

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Anlage RCA 10 meldet RC901 Hydraulikleck"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    history = data["root_cause_analysis"]["evidence"]["history"]
    assert data["diagnostics"]["history_source_count"] == 0
    assert history["source_count"] == 0
    assert history["tasks"] == []
    assert history["shift_handovers"] == []


def test_error_assistant_extracts_error_code(client, make_user, make_error_entry, auth_headers):
    """Error codes like F007 must be extracted and reflected in diagnostics."""
    user = make_user(
        username="ea_code_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    make_error_entry(
        machine="Presse",
        error_code="F007",
        title="Druckabfall",
        department_name="Produktion",
        possible_causes="Leckage an der Hydraulik",
        solution="Dichtungen pruefen und ersetzen",
    )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Presse zeigt Fehlercode F007"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["diagnostics"]["extracted_error_code"] == "F007"
    assert data["diagnostics"]["match_count"] > 0


def test_error_assistant_extracts_machine_name(client, make_user, make_error_entry, auth_headers):
    """Machine references like 'Anlage 7' must be extracted and used in search."""
    user = make_user(username="ea_machine_user")
    make_error_entry(
        machine="Anlage 7",
        error_code="X01",
        title="Motorstillstand",
        possible_causes="Motorueberhitzung",
        solution="Kuehlkoerper pruefen",
    )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Anlage 7 steht still"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["diagnostics"]["extracted_machine"] is not None
    assert "Anlage" in data["diagnostics"]["extracted_machine"]


# ---------------------------------------------------------------------------
# Limit parameter
# ---------------------------------------------------------------------------


def test_error_assistant_respects_limit(client, make_user, make_error_entry, auth_headers):
    """The limit parameter must cap the number of returned matches."""
    user = make_user(
        username="ea_limit_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    for i in range(4):
        make_error_entry(
            machine=f"Anlage {i}",
            error_code=f"L{i:02d}",
            title=f"Lager Fehler {i}",
            department_name="Instandhaltung",
            possible_causes="Lager verschlissen",
            solution="Lager tauschen",
        )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Lager macht Geraeusche", "limit": 2},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    assert len(data["matches"]) <= 2


# ---------------------------------------------------------------------------
# Department scoping
# ---------------------------------------------------------------------------


def test_error_assistant_scopes_to_department(client, make_user, make_error_entry, auth_headers):
    """Users must not see error catalog entries from another department."""
    # Create the IT department by registering an IT user first
    make_user(username="ea_it_owner", role=Role.IT, department_name="IT")
    prod_user = make_user(
        username="ea_prod_user",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    make_error_entry(
        machine="IT Server",
        error_code="IT99",
        title="Netzwerkausfall",
        department_name="IT",
        possible_causes="Switch defekt",
        solution="Switch tauschen",
    )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(prod_user["username"]),
        json={"query": "Fehlercode IT99 Netzwerkausfall"},
    )

    assert response.status_code == 200
    assert response.get_json()["data"]["diagnostics"]["match_count"] == 0


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_error_assistant_deduplicates_causes_and_fixes(
    client, make_user, make_error_entry, auth_headers
):
    """Identical causes or fixes from multiple entries must appear only once."""
    user = make_user(
        username="ea_dedup_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    shared_cause = "Sensor verschmutzt"
    shared_fix = "Sensor reinigen"
    for i in range(3):
        make_error_entry(
            machine=f"Maschine {i}",
            error_code=f"S{i:02d}",
            title=f"Sensorfehler {i}",
            department_name="Instandhaltung",
            possible_causes=shared_cause,
            solution=shared_fix,
        )

    response = client.post(
        "/api/v1/ai/error-assistant",
        headers=auth_headers(user["username"]),
        json={"query": "Sensor meldet kein Signal"},
    )

    assert response.status_code == 200
    data = response.get_json()["data"]
    causes = data["causes"]
    fixes = data["fixes"]
    assert len(causes) == len(set(causes))
    assert len(fixes) == len(set(fixes))
