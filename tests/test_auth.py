from app.models import Role


def test_register_validates_missing_fields_and_department(client, make_user, auth_headers):
    """Verify registration rejects incomplete payloads and non-admins without departments."""
    make_user(username="bootstrap_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers("bootstrap_admin")

    missing_response = client.post("/api/v1/auth/register", json={}, headers=headers)

    assert missing_response.status_code == 400
    assert missing_response.get_json()["error"] == "missing_fields_username_email_password"
    assert "Missing fields" in missing_response.get_json()["message"]

    no_department_response = client.post(
        "/api/v1/auth/register",
        json={
            "username": "tech",
            "email": "tech@example.test",
            "password": "password",
            "role": Role.INSTANDHALTUNG.value,
        },
        headers=headers,
    )

    assert no_department_response.status_code == 400
    assert no_department_response.get_json()["message"] == (
        "department_id or department is required"
    )


def test_register_master_admin_and_reject_duplicate(client, make_user, auth_headers):
    """Verify master admins can register without a department and duplicates fail."""
    make_user(username="bootstrap_admin", role=Role.MASTER_ADMIN, department_name=None)
    headers = auth_headers("bootstrap_admin")

    payload = {
        "username": "admin",
        "email": "admin@example.test",
        "password": "password",
        "role": Role.MASTER_ADMIN.value,
    }

    response = client.post("/api/v1/auth/register", json=payload, headers=headers)
    duplicate_response = client.post("/api/v1/auth/register", json=payload, headers=headers)

    assert response.status_code == 201
    assert response.get_json()["role"] == Role.MASTER_ADMIN.value
    assert duplicate_response.status_code == 409


def test_login_with_username_email_and_me(client, make_user):
    """Verify successful login by username and email plus the current-user endpoint."""
    user = make_user(username="operator")

    username_response = client.post(
        "/api/v1/auth/login",
        json={"login": user["username"], "password": user["password"]},
    )
    email_response = client.post(
        "/api/v1/auth/login",
        json={"login": user["email"], "password": user["password"]},
    )

    token = username_response.get_json()["access_token"]
    me_response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert username_response.status_code == 200
    assert email_response.status_code == 200
    assert me_response.status_code == 200
    assert me_response.get_json()["username"] == user["username"]


def test_login_rejects_invalid_credentials_and_locked_users(client, make_user):
    """Verify login error handling for bad passwords and inactive accounts."""
    user = make_user(username="locked", is_active=False)

    bad_password_response = client.post(
        "/api/v1/auth/login",
        json={"login": user["username"], "password": "wrong"},
    )
    locked_response = client.post(
        "/api/v1/auth/login",
        json={"login": user["username"], "password": user["password"]},
    )
    missing_response = client.post("/api/v1/auth/login", json={"login": user["username"]})

    assert bad_password_response.status_code == 401
    assert locked_response.status_code == 403
    assert locked_response.get_json()["error"] == "user_is_locked"
    assert locked_response.get_json()["message"] == "User is locked"
    assert missing_response.status_code == 400
