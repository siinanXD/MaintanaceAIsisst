from datetime import date, timedelta
from app.models import Role


def test_drag_drop_move_to_empty_cell(client, make_user, make_employee, make_machine, auth_headers):
    """Moving an entry to an empty cell updates work_date and shift."""
    admin = make_user(username="dd_move_admin", role=Role.MASTER_ADMIN, department_name=None)
    make_employee(personnel_number="P-701", name="DD Move Emp A", department="Produktion")
    make_employee(personnel_number="P-702", name="DD Move Emp B", department="Produktion")
    make_machine(name="DD Move Anlage", required_employees=1)
    headers = auth_headers(admin["username"])

    # Use a 1-day plan so there are no date conflicts on the target
    plan_resp = client.post("/api/v1/shiftplans/generate", headers=headers, json={
        "title": "DD Move Plan", "start_date": "2026-07-01", "days": 1,
        "rhythm": "2-Schicht", "department": "Produktion",
    })
    assert plan_resp.status_code == 201
    plan = plan_resp.get_json()
    frueh_entries = [e for e in plan["entries"] if e["shift"] == "Frueh"]
    if not frueh_entries:
        return  # Skip if plan didn't produce a Frueh entry
    entry = frueh_entries[0]
    entry_id = entry["id"]
    emp_id = entry["employee"]["id"]

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


def test_drag_drop_swap_occupied_cell(client, make_user, make_employee, make_machine, auth_headers):
    """Moving an entry onto an occupied cell swaps the two employee_ids."""
    admin = make_user(username="dd_swap_admin", role=Role.MASTER_ADMIN, department_name=None)
    make_employee(personnel_number="P-711", name="Swap Emp A", department="Produktion")
    make_employee(personnel_number="P-712", name="Swap Emp B", department="Produktion")
    make_machine(name="DD Swap Anlage", required_employees=1)
    headers = auth_headers(admin["username"])

    plan_resp = client.post("/api/v1/shiftplans/generate", headers=headers, json={
        "title": "DD Swap Plan", "start_date": "2026-07-06", "days": 1,
        "rhythm": "2-Schicht", "department": "Produktion",
    })
    assert plan_resp.status_code == 201
    entries = plan_resp.get_json()["entries"]
    frueh = [e for e in entries if e["shift"] == "Frueh"]
    spaet = [e for e in entries if e["shift"] == "Spaet"]
    if not frueh or not spaet:
        return  # Skip if plan didn't produce both shifts
    entry_a = frueh[0]
    entry_b = spaet[0]
    emp_a = entry_a["employee"]["id"]
    emp_b = entry_b["employee"]["id"]

    move_resp = client.patch(
        f"/api/v1/shiftplans/entries/{entry_a['id']}/move",
        headers=headers,
        json={"target_date": entry_b["work_date"], "target_shift": entry_b["shift"]},
    )
    assert move_resp.status_code == 200
    updated = move_resp.get_json()["data"]["entries"]
    # After slot-swap: entry_a moves to entry_b's slot (Spaet), entry_b moves to entry_a's slot (Frueh)
    new_a = next(e for e in updated if e["id"] == entry_a["id"])
    new_b = next(e for e in updated if e["id"] == entry_b["id"])
    # entry_a now occupies Spaet slot, entry_b now occupies Frueh slot
    assert new_a["shift"] == entry_b["shift"]
    assert new_b["shift"] == entry_a["shift"]
    # The visual result: Frueh cell now shows emp_a (via entry_b), Spaet shows emp_b (via entry_a)
    assert new_a["employee"]["id"] == emp_a
    assert new_b["employee"]["id"] == emp_b


def test_handover_create_and_complete(client, make_user, auth_headers):
    """Creating and completing a handover changes status to completed."""
    admin = make_user(username="ho_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    create_resp = client.post("/api/v1/handover", headers=headers, json={
        "department": "Produktion", "shift_date": "2026-07-01",
        "shift_type": "Frueh", "content": "Alles erledigt.",
        "open_tasks": "", "machine_notes": "", "next_notes": "Maschine läuft gut.",
    })
    assert create_resp.status_code == 201
    ho_id = create_resp.get_json()["data"]["id"]

    complete_resp = client.post(f"/api/v1/handover/{ho_id}/complete", headers=headers)
    assert complete_resp.status_code == 200
    assert complete_resp.get_json()["data"]["status"] == "completed"


def test_handover_edit_blocked_after_complete(client, make_user, auth_headers):
    """Editing a completed handover returns 403."""
    admin = make_user(username="ho_edit_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    create_resp = client.post("/api/v1/handover", headers=headers, json={
        "department": "IT", "shift_date": "2026-07-02",
        "shift_type": "Spaet", "content": "Test.",
    })
    ho_id = create_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/handover/{ho_id}/complete", headers=headers)

    edit_resp = client.patch(f"/api/v1/handover/{ho_id}", headers=headers,
                             json={"content": "Geändert"})
    assert edit_resp.status_code == 403


def test_handover_list_filters_by_department(client, make_user, auth_headers):
    """GET /handover?department= returns only matching records."""
    admin = make_user(username="ho_filter_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers(admin["username"])

    client.post("/api/v1/handover", headers=headers, json={
        "department": "Produktion", "shift_date": "2026-07-03", "shift_type": "Frueh",
    })
    client.post("/api/v1/handover", headers=headers, json={
        "department": "IT", "shift_date": "2026-07-03", "shift_type": "Frueh",
    })

    resp = client.get("/api/v1/handover?department=Produktion", headers=headers)
    assert resp.status_code == 200
    data = resp.get_json()["data"]
    assert all(h["department"] == "Produktion" for h in data)


def test_vacation_request_pending_flow(client, make_user, make_employee, auth_headers):
    """Submitting a vacation request creates a pending entry."""
    admin = make_user(username="vac_pending_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-801", name="Vac Pending Emp", department="Produktion")
    headers = auth_headers(admin["username"])

    resp = client.post("/api/v1/vacations", headers=headers, json={
        "employee_id": emp_id, "start_date": "2026-08-01", "end_date": "2026-08-07",
    })
    assert resp.status_code == 201
    data = resp.get_json()["data"]
    assert data["status"] == "pending"
    assert data["days_used"] == 5  # Mon 4 Aug – Fri 8 Aug = 5 workdays


def test_vacation_approve_updates_balance(client, make_user, make_employee, auth_headers):
    """Approving a request reduces the remaining balance."""
    admin = make_user(username="vac_approve_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-802", name="Vac Approve Emp", department="Produktion")
    headers = auth_headers(admin["username"])

    create_resp = client.post("/api/v1/vacations", headers=headers, json={
        "employee_id": emp_id, "start_date": "2026-08-10", "end_date": "2026-08-14",
    })
    vac_id   = create_resp.get_json()["data"]["id"]
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

    create_resp = client.post("/api/v1/vacations", headers=headers, json={
        "employee_id": emp_id, "start_date": "2026-09-01", "end_date": "2026-09-05",
    })
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
    resp = client.post("/api/v1/vacations", headers=headers, json={
        "employee_id": emp_id, "start_date": "2026-08-03", "end_date": "2026-08-09",
    })
    assert resp.status_code == 201
    assert resp.get_json()["data"]["days_used"] == 5


def test_vacation_auto_imported_in_shiftplan(client, make_user, make_employee, make_machine, auth_headers):
    """Approved vacation requests are automatically included when generating a shift plan."""
    admin = make_user(username="vac_auto_admin", role=Role.MASTER_ADMIN, department_name=None)
    emp_id = make_employee(personnel_number="P-810", name="Vac Auto Emp", department="Produktion")
    make_machine(name="Auto Vac Anlage", required_employees=1)
    headers = auth_headers(admin["username"])

    # Create and approve a vacation for the plan period
    vac_resp = client.post("/api/v1/vacations", headers=headers, json={
        "employee_id": emp_id, "start_date": "2026-10-05", "end_date": "2026-10-05",
    })
    vac_id = vac_resp.get_json()["data"]["id"]
    client.post(f"/api/v1/vacations/{vac_id}/approve", headers=headers)

    plan_resp = client.post("/api/v1/shiftplans/generate", headers=headers, json={
        "title": "Auto Vac Plan", "start_date": "2026-10-05", "days": 1,
        "rhythm": "2-Schicht", "department": "Produktion",
    })
    assert plan_resp.status_code == 201
    entries = plan_resp.get_json()["entries"]
    vacation_entries = [e for e in entries if e["shift"] == "Urlaub" and e["employee"]["id"] == emp_id]
    assert vacation_entries, "Approved vacation should be auto-imported as Urlaub entry"
