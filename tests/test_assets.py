from datetime import date, timedelta

from app.models import Priority, Role


def test_machine_create_rejects_duplicates_and_invalid_staffing(
    client,
    make_user,
    auth_headers,
):
    """Verify machine creation validates names and employee requirements."""
    admin = make_user(
        username="asset_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    headers = auth_headers(admin["username"])

    create_response = client.post(
        "/api/machines",
        headers=headers,
        json={
            "name": "Anlage 4",
            "produced_item": "Gehaeuse",
            "required_employees": 2,
        },
    )
    duplicate_response = client.post(
        "/api/machines",
        headers=headers,
        json={"name": "Anlage 4"},
    )
    invalid_response = client.post(
        "/api/machines",
        headers=headers,
        json={"name": "Anlage 5", "required_employees": 0},
    )

    assert create_response.status_code == 201
    assert create_response.get_json()["required_employees"] == 2
    assert duplicate_response.status_code == 409
    assert invalid_response.status_code == 400


def test_non_admin_without_machine_write_permission_is_forbidden(
    client,
    make_user,
    auth_headers,
):
    """Verify write permissions are enforced for machine endpoints."""
    user = make_user(
        username="machine_view_only",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )

    response = client.post(
        "/api/machines",
        headers=auth_headers(user["username"]),
        json={"name": "Anlage ohne Recht"},
    )

    assert response.status_code == 403


def test_inventory_create_and_summary_calculates_totals(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify inventory material creation and summary totals."""
    admin = make_user(
        username="inventory_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Anlage Lager")
    headers = auth_headers(admin["username"])

    create_response = client.post(
        "/api/inventory",
        headers=headers,
        json={
            "name": "Schraube M6",
            "unit_cost": 0.12,
            "quantity": 500,
            "machine_id": machine_id,
            "manufacturer": "ACME",
        },
    )
    summary_response = client.get("/api/inventory/summary", headers=headers)

    assert create_response.status_code == 201
    assert create_response.get_json()["total_value"] == 60.0
    assert summary_response.status_code == 200
    assert summary_response.get_json()["material_count"] == 1
    assert summary_response.get_json()["total_quantity"] == 500
    assert summary_response.get_json()["total_value"] == 60.0


def test_inventory_rejects_negative_or_non_numeric_values(
    client,
    make_user,
    auth_headers,
):
    """Verify inventory parser edgecases return explicit 400 errors."""
    admin = make_user(
        username="inventory_validation_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    headers = auth_headers(admin["username"])

    negative_response = client.post(
        "/api/inventory",
        headers=headers,
        json={"name": "Oel", "quantity": -1},
    )
    invalid_float_response = client.post(
        "/api/inventory",
        headers=headers,
        json={"name": "Oel 2", "unit_cost": "abc"},
    )

    assert negative_response.status_code == 400
    assert invalid_float_response.status_code == 400


def test_inventory_update_rejects_invalid_numbers(
    client,
    make_user,
    make_material,
    auth_headers,
):
    """Verify inventory updates return 400 for invalid numeric fields."""
    admin = make_user(
        username="inventory_update_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    material_id = make_material("Lager Update", 1.5, 3)
    headers = auth_headers(admin["username"])

    negative_response = client.put(
        f"/api/inventory/{material_id}",
        headers=headers,
        json={"quantity": -5},
    )
    invalid_response = client.put(
        f"/api/inventory/{material_id}",
        headers=headers,
        json={"unit_cost": "teuer"},
    )

    assert negative_response.status_code == 400
    assert invalid_response.status_code == 400


def test_delete_machine_detaches_inventory_material(
    client,
    make_user,
    make_machine,
    make_material,
    auth_headers,
):
    """Verify deleting a machine keeps inventory materials but clears the link."""
    admin = make_user(
        username="machine_delete_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Anlage Loeschen")
    make_material("Material", 2.5, 4, machine_id=machine_id)
    headers = auth_headers(admin["username"])

    delete_response = client.delete(f"/api/machines/{machine_id}", headers=headers)
    materials_response = client.get("/api/inventory", headers=headers)

    assert delete_response.status_code == 204
    assert materials_response.get_json()[0]["machine_id"] is None


def test_inventory_forecast_respects_task_department_visibility(
    client,
    make_user,
    make_machine,
    make_material,
    make_task,
    auth_headers,
):
    """Verify inventory forecasts only use tasks visible to the user."""
    requester = make_user(
        username="forecast_requester",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    other_user = make_user(
        username="forecast_other",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    visible_machine_id = make_machine(name="Anlage Sichtbar")
    hidden_machine_id = make_machine(name="Anlage Fremd")
    make_material("Sichtbares Lager", 4.0, 1, machine_id=visible_machine_id)
    make_material("Fremdes Lager", 4.0, 0, machine_id=hidden_machine_id)
    make_task(
        "Stillstand Anlage Sichtbar",
        creator_username=requester["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
        description="Anlage Sichtbar steht mit Sensorfehler",
    )
    make_task(
        "Stillstand Anlage Fremd",
        creator_username=other_user["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
        description="Anlage Fremd steht",
    )

    response = client.post(
        "/api/inventory/forecast",
        headers=auth_headers(requester["username"]),
        json={"status": "open", "low_stock_threshold": 5},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert [item["material"]["name"] for item in payload["items"]] == [
        "Sichtbares Lager",
    ]


def test_inventory_forecast_requires_inventory_and_task_view(
    client,
    make_user,
    set_dashboard_permission,
    auth_headers,
):
    """Verify inventory forecasts require both inventory and task view rights."""
    tasks_only = make_user(
        username="forecast_tasks_only",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    inventory_only = make_user(
        username="forecast_inventory_only",
        role=Role.VERWALTUNG,
        department_name="Verwaltung",
    )
    set_dashboard_permission(
        inventory_only["username"],
        "tasks",
        can_view=False,
        can_write=False,
    )

    missing_inventory = client.post(
        "/api/inventory/forecast",
        headers=auth_headers(tasks_only["username"]),
        json={},
    )
    missing_tasks = client.post(
        "/api/inventory/forecast",
        headers=auth_headers(inventory_only["username"]),
        json={},
    )

    assert missing_inventory.status_code == 403
    assert missing_tasks.status_code == 403


def test_inventory_forecast_flags_low_stock_for_critical_task(
    client,
    make_user,
    make_machine,
    make_material,
    make_task,
    auth_headers,
):
    """Verify low inventory linked to a critical task creates a warning."""
    user = make_user(
        username="forecast_low_stock",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    machine_id = make_machine(name="Anlage Kritisch")
    make_material("Sensor S1", 12.5, 1, machine_id=machine_id)
    make_task(
        "Stillstand Anlage Kritisch",
        creator_username=user["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
        due_date_value=date.today() - timedelta(days=1),
        description="Anlage Kritisch steht mit Sensorfehler",
    )

    response = client.post(
        "/api/inventory/forecast",
        headers=auth_headers(user["username"]),
        json={"status": "open", "low_stock_threshold": 5},
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["summary"]["high"] == 1
    assert payload["items"][0]["material"]["name"] == "Sensor S1"
    assert payload["items"][0]["risk_level"] == "high"
    assert payload["items"][0]["score"] >= 65


def test_inventory_forecast_rejects_invalid_payloads(
    client,
    make_user,
    auth_headers,
):
    """Verify inventory forecasts reject malformed filters."""
    user = make_user(
        username="forecast_validation",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    headers = auth_headers(user["username"])

    bad_threshold = client.post(
        "/api/inventory/forecast",
        headers=headers,
        json={"low_stock_threshold": -1},
    )
    bad_limit = client.post(
        "/api/inventory/forecast",
        headers=headers,
        json={"limit": 0},
    )
    bad_status = client.post(
        "/api/inventory/forecast",
        headers=headers,
        json={"status": "unknown"},
    )

    assert bad_threshold.status_code == 400
    assert bad_limit.status_code == 400
    assert bad_status.status_code == 400


def test_inventory_page_contains_forecast_ui(client):
    """Verify the inventory page exposes the forecast controls."""
    response = client.get("/inventory")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-inventory-forecast-form' in html
    assert 'data-inventory-forecast-list' in html
    assert "Ersatzteil-Prognose" in html


def test_machine_history_only_uses_permitted_sources(
    client,
    make_user,
    set_dashboard_permission,
    make_machine,
    make_task,
    make_error_entry,
    make_document,
    auth_headers,
):
    """Verify machine history only includes sources allowed by dashboard rights."""
    user = make_user(
        username="history_source_rights",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "machines", can_view=True)
    set_dashboard_permission(user["username"], "errors", can_view=False)
    set_dashboard_permission(user["username"], "documents", can_view=False)
    machine_id = make_machine(name="Anlage Historie")
    task_id = make_task(
        "Task Anlage Historie",
        creator_username=user["username"],
        department_name="Produktion",
        description="Anlage Historie pruefen",
    )
    make_error_entry(
        "Anlage Historie",
        "E900",
        "Fehler Anlage Historie",
        department_name="Produktion",
    )
    make_document(
        task_id,
        user["id"],
        department="Produktion",
        machine="Anlage Historie",
    )

    response = client.get(
        f"/api/machines/{machine_id}/history",
        headers=auth_headers(user["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["source_counts"] == {
        "tasks": 1,
        "errors": 0,
        "documents": 0,
        "total": 1,
    }
    assert [item["type"] for item in payload["timeline"]] == ["task"]


def test_machine_history_respects_non_admin_department_scope(
    client,
    make_user,
    make_machine,
    make_task,
    make_error_entry,
    make_document,
    auth_headers,
):
    """Verify non-admin machine history excludes other departments."""
    requester = make_user(
        username="history_department_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    other_user = make_user(
        username="history_other_department",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    machine_id = make_machine(name="Anlage Bereich")
    visible_task_id = make_task(
        "Task Anlage Bereich sichtbar",
        creator_username=requester["username"],
        department_name="Instandhaltung",
        description="Anlage Bereich pruefen",
    )
    make_task(
        "Task Anlage Bereich fremd",
        creator_username=other_user["username"],
        department_name="Produktion",
        description="Anlage Bereich pruefen",
    )
    make_error_entry(
        "Anlage Bereich",
        "E901",
        "Sichtbarer Fehler",
        department_name="Instandhaltung",
    )
    make_error_entry(
        "Anlage Bereich",
        "E902",
        "Fremder Fehler",
        department_name="Produktion",
    )
    make_document(
        visible_task_id,
        requester["id"],
        department="Instandhaltung",
        machine="Anlage Bereich",
    )
    make_document(
        visible_task_id,
        requester["id"],
        relative_path="2026/05/task_2/maintenance_report.html",
        department="Produktion",
        machine="Anlage Bereich",
    )

    response = client.get(
        f"/api/machines/{machine_id}/history",
        headers=auth_headers(requester["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["source_counts"]["tasks"] == 1
    assert payload["source_counts"]["errors"] == 1
    assert payload["source_counts"]["documents"] == 1
    assert all("fremd" not in item["title"].lower() for item in payload["timeline"])


def test_machine_history_unknown_machine_returns_404(client, make_user, auth_headers):
    """Verify unknown machines return 404 for history requests."""
    admin = make_user(
        username="history_missing_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )

    response = client.get(
        "/api/machines/999/history",
        headers=auth_headers(admin["username"]),
    )

    assert response.status_code == 404


def test_machine_history_uses_local_summary_without_openai_key(
    client,
    make_user,
    make_machine,
    auth_headers,
):
    """Verify machine history returns a local summary with mock AI settings."""
    admin = make_user(
        username="history_summary_admin",
        role=Role.MASTER_ADMIN,
        department_name=None,
    )
    machine_id = make_machine(name="Anlage Zusammenfassung")

    response = client.get(
        f"/api/machines/{machine_id}/history",
        headers=auth_headers(admin["username"]),
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["summary"]["diagnostics"]["status"] == "local_answer"
    assert "Anlage Zusammenfassung" in payload["summary"]["text"]


def test_machine_page_contains_history_ui(client):
    """Verify the machine page exposes the history target container."""
    response = client.get("/machines")
    html = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'data-machine-history-panel' in html
    assert 'data-machine-history-list' in html
    assert 'data-machine-assistant-form' in html
    assert "Anlagenakte" in html


def test_machine_assistant_uses_local_context_and_requires_question(
    client,
    make_user,
    make_machine,
    make_task,
    auth_headers,
):
    """Verify the machine assistant answers locally and validates questions."""
    user = make_user(
        username="machine_assistant_user",
        role=Role.INSTANDHALTUNG,
        department_name="Instandhaltung",
    )
    machine_id = make_machine(name="Anlage Assistent")
    make_task(
        "Task Anlage Assistent",
        creator_username=user["username"],
        department_name="Instandhaltung",
        priority=Priority.URGENT,
        description="Anlage Assistent pruefen",
    )
    headers = auth_headers(user["username"])

    empty_response = client.post(
        f"/api/machines/{machine_id}/assistant",
        headers=headers,
        json={},
    )
    valid_response = client.post(
        f"/api/machines/{machine_id}/assistant",
        headers=headers,
        json={"question": "Was ist wichtig?"},
    )

    payload = valid_response.get_json()
    assert empty_response.status_code == 400
    assert valid_response.status_code == 200
    assert payload["diagnostics"]["status"] == "local_answer"
    assert payload["context"]["source_counts"]["tasks"] == 1
