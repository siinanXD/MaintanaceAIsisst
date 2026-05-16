"""Tests for POST /api/v1/ai/error-assistant.

Covers: auth guard, input validation, response shape, local search,
error-code extraction, department scoping, limit parameter, and
empty-catalog behaviour.
"""

from app.models import Role

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
    assert set(data.keys()) >= {"query", "matches", "causes", "fixes", "diagnostics"}

    diag = data["diagnostics"]
    assert set(diag.keys()) >= {
        "status",
        "provider",
        "match_count",
        "extracted_error_code",
        "extracted_machine",
        "ai_enhanced",
    }
    # In test mode the mock provider never enhances results
    assert diag["ai_enhanced"] is False


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
    assert data["action_preview"]["type"] == "task_draft"
    assert data["action_preview"]["payload"]["status"] == "open"


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
