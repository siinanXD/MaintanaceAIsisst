"""Tests for handover and vacation workflows."""

from datetime import date

from app.extensions import db
from app.models import (
    Department,
    Employee,
    EmployeeMachineQualification,
    MaintenancePlan,
    Priority,
    Role,
)


def _add_machine_qualifications(app, employee_ids, machine_ids, level="trained"):
    """Create structured qualifications for drag-and-drop shift plan tests."""
    with app.app_context():
        for employee_id in employee_ids:
            for machine_id in machine_ids:
                db.session.add(
                    EmployeeMachineQualification(
                        employee_id=employee_id,
                        machine_id=machine_id,
                        level=level,
                    )
                )
        db.session.commit()


def test_drag_drop_move_to_empty_cell(
    client,
    app,
    make_user,
    make_employee,
    make_machine,
    auth_headers,
):
    """Moving an entry to an empty cell updates work_date and shift."""
    admin = make_user(username="dd_move_admin", role=Role.MASTER_ADMIN, department_name=None)
    employee_ids = [
        make_employee(personnel_number="P-701", name="DD Move Emp A", department="Produktion"),
        make_employee(personnel_number="P-702", name="DD Move Emp B", department="Produktion"),
    ]
    machine_id = make_machine(name="DD Move Anlage", required_employees=1)
    _add_machine_qualifications(app, employee_ids, [machine_id])
    headers = auth_headers(admin["username"])

    # Use a 1-day plan so there are no date conflicts on the target
    plan_resp = client.post(
        "/api/v1/shiftplans/generate",
        headers=headers,
        json={
            "title": "DD Move Plan",
            "start_date": "2026-07-01",
            "days": 1,
            "rhythm": "2-Schicht",
            "department": "Produktion",
        },
    )
    assert plan_resp.status_code == 201
    plan = plan_resp.get_json()
    frueh_entries = [e for e in plan["entries"] if e["shift"] == "Frueh"]
    if not frueh_entries:
        return  # Skip if plan didn't produce a Frueh entry
    entry = frueh_entries[0]
    entry_id = entry["id"]

    # Move to Nachtschicht — which is an empty cell (2-Schicht doesn't generate Nacht)
    move_resp = client.patch(
        f"/api/v1/shiftplans/entries/{entry_id}/move",
        headers=headers,
        json={"target_date": "2026-07-01", "target_shift": "Nacht"},
    )
    assert move_resp.status_code == 200
    updated_plan = move_resp.get_json()["data"]
    moved = next((e for e in updated_plan["entries"] if e["id"] == entry_id), None)
    assert moved is not None
    assert moved["work_date"] == "2026-07-01"
    assert moved["shift"] == "Nacht"


def test_drag_drop_move_to_full_occupied_cell_is_blocked(
    client,
    app,
    make_user,
    make_employee,
    make_machine,
    auth_headers,
):
    """Moving onto a full occupied cell is blocked instead of swapping entries."""
    admin = make_user(username="dd_swap_admin", role=Role.MASTER_ADMIN, department_name=None)
    employee_ids = [
        make_employee(personnel_number="P-711", name="Swap Emp A", department="Produktion"),
        make_employee(personnel_number="P-712", name="Swap Emp B", department="Produktion"),
    ]
    machine_id = make_machine(name="DD Swap Anlage", required_employees=1)
    _add_machine_qualifications(app, employee_ids, [machine_id])
    headers = auth_headers(admin["username"])

    plan_resp = client.post(
        "/api/v1/shiftplans/generate",
        headers=headers,
        json={
            "title": "DD Swap Plan",
            "start_date": "2026-07-06",
            "days": 1,
            "rhythm": "2-Schicht",
            "department": "Produktion",
        },
    )
    assert plan_resp.status_code == 201
    entries = plan_resp.get_json()["entries"]
    frueh = [e for e in entries if e["shift"] == "Frueh"]
    spaet = [e for e in entries if e["shift"] == "Spaet"]
    if not frueh or not spaet:
        return  # Skip if plan didn't produce both shifts
    entry_a = frueh[0]
    entry_b = spaet[0]

    move_resp = client.patch(
        f"/api/v1/shiftplans/entries/{entry_a['id']}/move",
        headers=headers,
        json={"target_date": entry_b["work_date"], "target_shift": entry_b["shift"]},
    )
    assert move_resp.status_code == 409
    assert "voll besetzt" in move_resp.get_json()["message"]


def test_handover_create_and_complete(client, make_user, auth_headers):
    """Creating and completing a handover changes status to completed."""
    admin = make_user(username="ho_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "Produktion",
            "shift_date": "2026-07-01",
            "shift_type": "Frueh",
            "content": "Alles erledigt.",
            "open_tasks": "",
            "machine_notes": "",
            "area": "Linie 2",
            "production_status": "running",
            "machine_status": "ok",
            "safety_notes": "Schutzeinhausung geprüft.",
            "material_notes": "Reservefilter liegt bereit.",
            "responsible_employee": "Max Mustermann",
            "problem_category": "Organisation",
            "cause": "Regelbetrieb",
            "action_taken": "Rundgang dokumentiert.",
            "duration_minutes": 15,
            "follow_up_task": "Filter nach Spätschicht prüfen.",
            "involved_employees": "Team A",
            "next_notes": "Maschine läuft gut.",
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.get_json()["data"]
    ho_id = created["id"]
    assert created["previous_shift"] == "Nacht"
    assert created["next_shift"] == "Spaet"
    assert created["production_status"] == "running"
    assert created["machine_status"] == "ok"
    assert created["confirmed"] is False

    complete_resp = client.post(f"/api/v1/handover/{ho_id}/complete", headers=headers)
    assert complete_resp.status_code == 200
    assert complete_resp.get_json()["data"]["status"] == "completed"
    assert complete_resp.get_json()["data"]["confirmed"] is True


def test_handover_edit_blocked_after_complete(client, make_user, auth_headers):
    """Editing a completed handover returns 403."""
    admin = make_user(username="ho_edit_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "IT",
            "shift_date": "2026-07-02",
            "shift_type": "Spaet",
            "content": "Test.",
        },
    )
    ho_id = create_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/handover/{ho_id}/complete", headers=headers)

    edit_resp = client.patch(
        f"/api/v1/handover/{ho_id}", headers=headers, json={"content": "Geändert"}
    )
    assert edit_resp.status_code == 403


def test_handover_list_filters_by_department(client, make_user, auth_headers):
    """GET /handover?department= returns only matching records."""
    admin = make_user(username="ho_filter_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "Produktion",
            "shift_date": "2026-07-03",
            "shift_type": "Frueh",
        },
    )
    client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "IT",
            "shift_date": "2026-07-03",
            "shift_type": "Frueh",
        },
    )

    resp = client.get("/api/v1/handover?department=Produktion", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert all(h["department"] == "Produktion" for h in data)


def test_handover_summary_combines_tasks_errors_and_next_actions(
    app,
    client,
    make_user,
    make_machine,
    make_task,
    make_error_entry,
    auth_headers,
):
    """Handover summaries combine the logbook with visible tasks and disruptions."""
    admin = make_user(username="ho_summary_admin", role=Role.MASTER_ADMIN, department_name=None)
    machine_id = make_machine(name="Handover Presse", produced_item="Gehaeuse")
    make_task(
        "Hydraulikdruck Handover Presse pruefen",
        creator_username=admin["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
        description="Druck schwankt seit der Fruehschicht.",
    )
    make_error_entry(
        machine="Handover Presse",
        error_code="HO-77",
        title="Druck schwankt",
        department_name="Produktion",
        possible_causes="Hydraulikfilter verschmutzt",
        solution="Filter pruefen und Druckmessung wiederholen",
    )
    with app.app_context():
        department = Department.query.filter_by(name="Produktion").one()
        db.session.add(
            MaintenancePlan(
                title="Handover Presse Hydraulik Wartung",
                description="Druckschwankung und Filtereinsatz nach Schicht pruefen.",
                interval_days=14,
                next_due_date=date.today(),
                priority=Priority.URGENT,
                is_active=True,
                machine_id=machine_id,
                department=department,
                created_by=admin["id"],
            )
        )
        db.session.commit()
    headers = auth_headers(admin["username"])
    create_resp = client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "Produktion",
            "machine_id": machine_id,
            "shift_date": "2026-07-04",
            "shift_type": "Spaet",
            "production_status": "reduced",
            "machine_status": "warning",
            "problem_category": "Hydraulik",
            "machine_notes": "Druckabfall bei Lastwechsel beobachtet.",
            "next_notes": "Druck im ersten Auftrag beobachten.",
            "follow_up_task": "Filtereinsatz vor Nachtschicht pruefen.",
        },
    )
    handover_id = create_resp.get_json()["data"]["id"]

    response = client.get(f"/api/v1/handover/{handover_id}/summary", headers=headers)

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["handover"]["machine_id"] == machine_id
    assert payload["diagnostics"]["status"] == "local_handover_summary"
    assert payload["diagnostics"]["open_task_count"] >= 1
    assert payload["diagnostics"]["disruption_count"] >= 1
    assert payload["diagnostics"]["maintenance_plan_count"] >= 1
    assert "tasks" in payload["diagnostics"]["scopes"]
    assert "errors" in payload["diagnostics"]["scopes"]
    assert "machines" in payload["diagnostics"]["scopes"]
    assert payload["confidence"]["score"] >= 50
    assert payload["confidence"]["uncertainty"] in {"low", "medium", "high"}
    assert payload["source_counts"]["handover_fields"] >= 2
    assert payload["source_counts"]["open_tasks"] >= 1
    assert payload["source_counts"]["disruptions"] >= 1
    assert payload["source_counts"]["maintenance_plans"] >= 1
    assert payload["source_counts"]["uses_only_visible_sources"] is True
    evidence_summary = payload["evidence_summary"]
    assert evidence_summary["workflow"] == "shift_handover_summary"
    assert evidence_summary["provider"] == "local_rules"
    assert evidence_summary["uses_only_visible_sources"] is True
    assert evidence_summary["llm_call"] is False
    assert evidence_summary["has_open_task_context"] is True
    assert evidence_summary["has_disruption_context"] is True
    assert evidence_summary["has_maintenance_plan_context"] is True
    assert {"shift_handover", "task", "error", "maintenance_plan"} <= set(
        evidence_summary["source_types"]
    )
    assert evidence_summary["direct_source_count"] >= 4
    assert evidence_summary["latest_signal_at"]
    source_references = evidence_summary["source_references"]
    assert {source["type"] for source in source_references} >= {
        "shift_handover",
        "task",
        "error",
        "maintenance_plan",
    }
    task_reference = next(source for source in source_references if source["type"] == "task")
    error_reference = next(source for source in source_references if source["type"] == "error")
    plan_reference = next(
        source for source in source_references if source["type"] == "maintenance_plan"
    )
    assert task_reference["title"]
    assert task_reference["role_visibility"] == "department:Produktion"
    assert task_reference["created_at"]
    assert error_reference["error_code"] == "HO-77"
    assert error_reference["machine"] == "Handover Presse"
    assert any(source["machine_id"] == machine_id for source in source_references)
    assert plan_reference["due_date"] == date.today().isoformat()
    assert all("solution" not in source for source in source_references)
    assert any("Druckabfall" in point["text"] for point in payload["critical_points"])
    assert any("Hydraulikdruck" in task["title"] for task in payload["open_tasks"])
    assert any(item["error_code"] == "HO-77" for item in payload["disruptions"])
    assert payload["maintenance_plans"][0]["title"] == "Handover Presse Hydraulik Wartung"
    assert any("Filter" in action["text"] for action in payload["next_actions"])
    assert any(action["source"] == "maintenance_plan" for action in payload["next_actions"])
    task_action = next(action for action in payload["next_actions"] if action["source"] == "task")
    error_action = next(
        action for action in payload["next_actions"] if action["source"] == "error_solution"
    )
    plan_action = next(
        action for action in payload["next_actions"] if action["source"] == "maintenance_plan"
    )
    assert task_action["source_id"]
    assert task_action["title"]
    assert task_action["due_date"]
    assert error_action["error_code"] == "HO-77"
    assert error_action["source_id"]
    assert plan_action["source_id"]
    assert plan_action["due_date"]


def test_handover_summary_respects_task_and_error_permissions(
    client,
    make_user,
    make_task,
    make_error_entry,
    auth_headers,
    set_dashboard_permission,
):
    """Summary context does not include task or error data without those scopes."""
    user = make_user(
        username="ho_summary_limited",
        role=Role.PRODUKTION,
        department_name="Produktion",
    )
    set_dashboard_permission(user["username"], "shiftplans", can_view=True, can_write=True)
    set_dashboard_permission(user["username"], "tasks", can_view=False)
    set_dashboard_permission(user["username"], "errors", can_view=False)
    set_dashboard_permission(user["username"], "machines", can_view=False)
    make_task(
        "Nicht sichtbarer Task",
        creator_username=user["username"],
        department_name="Produktion",
        priority=Priority.URGENT,
    )
    make_error_entry(
        machine="Nicht sichtbare Anlage",
        error_code="NO-1",
        title="Nicht sichtbarer Fehler",
        department_name="Produktion",
    )
    headers = auth_headers(user["username"])
    create_resp = client.post(
        "/api/v1/handover",
        headers=headers,
        json={
            "department": "Produktion",
            "shift_date": "2026-07-05",
            "shift_type": "Nacht",
            "content": "Nur Uebergabetext sichtbar.",
        },
    )
    handover_id = create_resp.get_json()["data"]["id"]

    response = client.get(f"/api/v1/handover/{handover_id}/summary", headers=headers)

    payload = response.get_json()["data"]
    assert response.status_code == 200
    assert payload["open_tasks"] == []
    assert payload["disruptions"] == []
    assert payload["source_counts"]["open_tasks"] == 0
    assert payload["source_counts"]["disruptions"] == 0
    assert payload["source_counts"]["uses_only_visible_sources"] is True
    assert payload["confidence"]["uncertainty"] == "high"
    assert payload["evidence_summary"]["source_types"] == ["shift_handover"]
    assert [
        source["type"] for source in payload["evidence_summary"]["source_references"]
    ] == ["shift_handover"]
    assert payload["evidence_summary"]["has_open_task_context"] is False
    assert payload["evidence_summary"]["has_disruption_context"] is False
    assert payload["evidence_summary"]["llm_call"] is False
    assert payload["diagnostics"]["scopes"] == ["handover"]


def test_vacation_request_pending_flow(client, make_user, make_employee, auth_headers):
    """Submitting a vacation request creates a pending entry."""
    admin = make_user(username="vac_pending_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(
        personnel_number="P-801", name="Vac Pending Emp", department="Produktion"
    )
    headers = auth_headers(admin["username"])

    resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-08-01",
            "end_date": "2026-08-07",
        },
    )
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["status"] == "pending"
    assert data["days_used"] == 5  # Mon 4 Aug – Fri 8 Aug = 5 workdays


def test_vacation_approve_updates_balance(client, make_user, make_employee, auth_headers):
    """Approving a request reduces the remaining balance."""
    admin = make_user(username="vac_approve_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(
        personnel_number="P-802", name="Vac Approve Emp", department="Produktion"
    )
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-08-10",
            "end_date": "2026-08-14",
        },
    )
    vac_id = create_resp.get_json()["data"]["id"]
    days_used = create_resp.get_json()["data"]["days_used"]

    client.post(f"/api/v1/vacations/{vac_id}/approve", headers=headers)

    summary = client.get("/api/v1/vacations/summary?year=2026", headers=headers).get_json()["data"]
    emp_bal = next(s for s in summary if s["employee_id"] == emp_id)
    assert emp_bal["used"] == days_used
    assert emp_bal["remaining"] == emp_bal["total"] - days_used


def test_vacation_reject_keeps_balance(client, make_user, make_employee, auth_headers):
    """Rejecting a request does not change the balance."""
    admin = make_user(username="vac_reject_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-803", name="Vac Reject Emp", department="Produktion")
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-09-01",
            "end_date": "2026-09-05",
        },
    )
    vac_id = create_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/vacations/{vac_id}/reject", headers=headers)

    summary = client.get("/api/v1/vacations/summary?year=2026", headers=headers).get_json()["data"]
    emp_bal = next(s for s in summary if s["employee_id"] == emp_id)
    assert emp_bal["used"] == 0


def test_vacation_balance_counts_workdays(client, make_user, make_employee, auth_headers):
    """Vacation spanning a weekend counts only 5 workdays, not 7."""
    admin = make_user(username="vac_days_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-804", name="Vac Days Emp", department="Produktion")
    headers = auth_headers(admin["username"])

    # 2026-08-03 (Mon) to 2026-08-09 (Sun) = 5 workdays
    resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-08-03",
            "end_date": "2026-08-09",
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["data"]["days_used"] == 5


def test_vacation_list_filters_by_status(client, make_user, make_employee, auth_headers):
    """GET /vacations?status= returns only requests with the requested status."""
    admin = make_user(username="vac_status_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-805", name="Vac Status Emp", department="Produktion")
    headers = auth_headers(admin["username"])

    approved_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-11-02",
            "end_date": "2026-11-02",
        },
    )
    pending_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-11-03",
            "end_date": "2026-11-03",
        },
    )
    approved_id = approved_resp.get_json()["data"]["id"]
    pending_id = pending_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/vacations/{approved_id}/approve", headers=headers)

    resp = client.get("/api/v1/vacations?status=approved", headers=headers)

    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert [item["id"] for item in data] == [approved_id]
    assert pending_id not in [item["id"] for item in data]
    assert all(item["status"] == "approved" for item in data)


def test_vacation_overlap_is_blocked(client, make_user, make_employee, auth_headers):
    """An active vacation request cannot overlap an existing pending request."""
    admin = make_user(username="vac_overlap_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(
        personnel_number="P-806", name="Vac Overlap Emp", department="Produktion"
    )
    headers = auth_headers(admin["username"])

    first_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-11-09",
            "end_date": "2026-11-13",
        },
    )
    overlap_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-11-11",
            "end_date": "2026-11-12",
        },
    )

    assert first_resp.status_code == 201
    assert overlap_resp.status_code == 409


def test_vacation_request_over_available_balance_is_blocked(
    app,
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """A request above the employee's available balance returns 409."""
    admin = make_user(
        username="vac_balance_block_admin", role=Role.MASTER_ADMIN, department_name=None
    )
    emp_id = make_employee(
        personnel_number="P-807", name="Vac Balance Block Emp", department="Produktion"
    )
    headers = auth_headers(admin["username"])
    with app.app_context():
        employee = db.session.get(Employee, emp_id)
        employee.vacation_days_per_year = 3
        db.session.commit()

    resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-12-07",
            "end_date": "2026-12-11",
        },
    )

    assert resp.status_code == 409


def test_vacation_summary_reserves_pending_days(client, make_user, make_employee, auth_headers):
    """Pending requests reduce available days without changing used days."""
    admin = make_user(
        username="vac_pending_summary_admin", role=Role.MASTER_ADMIN, department_name=None
    )
    emp_id = make_employee(
        personnel_number="P-808", name="Vac Pending Summary Emp", department="Produktion"
    )
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-12-14",
            "end_date": "2026-12-15",
        },
    )
    days_used = create_resp.get_json()["data"]["days_used"]

    summary = client.get("/api/v1/vacations/summary?year=2026", headers=headers).get_json()["data"]
    emp_bal = next(s for s in summary if s["employee_id"] == emp_id)
    assert emp_bal["used"] == 0
    assert emp_bal["pending"] == days_used
    assert emp_bal["remaining"] == emp_bal["total"]
    assert emp_bal["available"] == emp_bal["total"] - days_used


def test_vacation_request_stores_shift_representative_and_impact(
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Vacation requests store operational planning fields."""
    admin = make_user(username="vac_impact_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(
        personnel_number="P-813",
        name="Vac Impact Emp",
        department="Produktion",
    )
    rep_id = make_employee(
        personnel_number="P-814",
        name="Vac Rep Emp",
        department="Produktion",
    )
    headers = auth_headers(admin["username"])

    impact_resp = client.get(
        (
            "/api/v1/vacations/impact?"
            f"employee_id={emp_id}&start_date=2026-12-21&end_date=2026-12-23"
        ),
        headers=headers,
    )
    assert impact_resp.status_code == 200
    assert impact_resp.get_json()["impact"]["representative_ok"] is False

    create_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-12-21",
            "end_date": "2026-12-23",
            "shift_type": "Frueh",
            "representative_employee_id": rep_id,
            "reason": "Erholungsurlaub",
            "notes": "Vertretung eingewiesen",
        },
    )
    assert create_resp.status_code == 201
    data = create_resp.get_json()["data"]
    assert data["shift_type"] == "Frueh"
    assert data["representative"]["id"] == rep_id
    assert data["reason"] == "Erholungsurlaub"
    assert data["impact_summary"]


def test_vacation_cancel_keeps_history_and_restores_balance(
    client,
    make_user,
    make_employee,
    auth_headers,
):
    """Cancelling an approved request keeps history but removes used balance."""
    admin = make_user(username="vac_cancel_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(
        personnel_number="P-815",
        name="Vac Cancel Emp",
        department="Produktion",
    )
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-12-28",
            "end_date": "2026-12-30",
        },
    )
    vac_id = create_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/vacations/{vac_id}/approve", headers=headers)

    cancel_resp = client.post(f"/api/v1/vacations/{vac_id}/cancel", headers=headers)
    assert cancel_resp.status_code == 200
    assert cancel_resp.get_json()["data"]["status"] == "cancelled"

    summary = client.get("/api/v1/vacations/summary?year=2026", headers=headers).get_json()["data"]
    emp_bal = next(s for s in summary if s["employee_id"] == emp_id)
    assert emp_bal["used"] == 0


def test_department_lead_can_decide_own_department_only(
    client,
    make_user,
    make_employee,
    auth_headers,
    set_dashboard_permission,
):
    """Employees write permission allows deciding only same-department requests."""
    admin = make_user(username="vac_lead_admin", role=Role.MASTER_ADMIN, department_name=None)
    lead = make_user(username="vac_prod_lead", role=Role.PRODUKTION, department_name="Produktion")
    set_dashboard_permission(
        lead["username"],
        "employees",
        can_view=True,
        can_write=True,
        employee_access_level="basic",
    )
    prod_emp_id = make_employee(
        personnel_number="P-809", name="Vac Prod Emp", department="Produktion"
    )
    it_emp_id = make_employee(personnel_number="P-811", name="Vac IT Emp", department="IT")
    admin_headers = auth_headers(admin["username"])
    lead_headers = auth_headers(lead["username"])

    prod_resp = client.post(
        "/api/v1/vacations",
        headers=admin_headers,
        json={
            "employee_id": prod_emp_id,
            "start_date": "2026-12-16",
            "end_date": "2026-12-16",
        },
    )
    it_resp = client.post(
        "/api/v1/vacations",
        headers=admin_headers,
        json={
            "employee_id": it_emp_id,
            "start_date": "2026-12-17",
            "end_date": "2026-12-17",
        },
    )

    approve_prod = client.post(
        f"/api/v1/vacations/{prod_resp.get_json()['data']['id']}/approve",
        headers=lead_headers,
    )
    approve_it = client.post(
        f"/api/v1/vacations/{it_resp.get_json()['data']['id']}/approve",
        headers=lead_headers,
    )

    assert approve_prod.status_code == 200
    assert approve_it.status_code == 403


def test_master_admin_can_decide_any_department(client, make_user, make_employee, auth_headers):
    """Master admins can still decide vacation requests from every department."""
    admin = make_user(username="vac_master_any_admin", role=Role.MASTER_ADMIN, department_name=None)
    it_emp_id = make_employee(personnel_number="P-812", name="Vac Master IT Emp", department="IT")
    headers = auth_headers(admin["username"])

    create_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": it_emp_id,
            "start_date": "2026-12-18",
            "end_date": "2026-12-18",
        },
    )
    approve_resp = client.post(
        f"/api/v1/vacations/{create_resp.get_json()['data']['id']}/approve",
        headers=headers,
    )

    assert approve_resp.status_code == 200
    assert approve_resp.get_json()["data"]["status"] == "approved"


def test_vacation_auto_imported_in_shiftplan(
    client, make_user, make_employee, make_machine, auth_headers
):
    """Approved vacation requests are automatically included when generating a shift plan."""
    admin = make_user(username="vac_auto_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-810", name="Vac Auto Emp", department="Produktion")
    make_employee(personnel_number="P-811", name="Vac Cover Emp", department="Produktion")
    make_machine(name="Auto Vac Anlage", required_employees=1)
    headers = auth_headers(admin["username"])

    # Create and approve a vacation for the plan period
    vac_resp = client.post(
        "/api/v1/vacations",
        headers=headers,
        json={
            "employee_id": emp_id,
            "start_date": "2026-10-05",
            "end_date": "2026-10-05",
        },
    )
    vac_id = vac_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/vacations/{vac_id}/approve", headers=headers)

    plan_resp = client.post(
        "/api/v1/shiftplans/generate",
        headers=headers,
        json={
            "title": "Auto Vac Plan",
            "start_date": "2026-10-05",
            "days": 1,
            "rhythm": "2-Schicht",
            "department": "Produktion",
        },
    )
    assert plan_resp.status_code == 201
    entries = plan_resp.get_json()["entries"]
    vacation_entries = [
        e for e in entries if e["shift"] == "Urlaub" and e["employee"]["id"] == emp_id
    ]
    assert vacation_entries, "Approved vacation should be auto-imported as Urlaub entry"
