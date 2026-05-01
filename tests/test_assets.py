from app.models import Role


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
