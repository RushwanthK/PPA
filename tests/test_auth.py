def test_register_success(client):
    response = client.post(
        "/register",
        json={
            "name": "newuser",
            "password": "NewPassword123!",
            "dob": "1995-05-10",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "User registered successfully"


def test_register_missing_required_field(client):
    response = client.post(
        "/register",
        json={
            "name": "missinguser",
            "password": "Password123!",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Missing required fields"


def test_login_success(client, test_user):
    response = client.post(
        "/login",
        json={
            "name": "testuser",
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert "token" in data
    assert data["user"]["name"] == "testuser"


def test_login_invalid_password(client, test_user):
    response = client.post(
        "/login",
        json={
            "name": "testuser",
            "password": "WrongPassword123!",
        },
    )

    assert response.status_code == 401

    data = response.get_json()

    assert data["error"] == "Invalid credentials"


def test_me_requires_authentication(client):
    response = client.get("/me")

    assert response.status_code == 401


def test_me_returns_authenticated_user(authenticated_client, test_user):
    response = authenticated_client.get("/me")

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == test_user.id
    assert data["name"] == test_user.name
    assert data["place"] == test_user.place