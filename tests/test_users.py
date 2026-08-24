def test_get_users_returns_current_user(authenticated_client, test_user):
    response = authenticated_client.get("/users")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    user = data[0]

    assert user["id"] == test_user.id
    assert user["name"] == test_user.name
    assert user["place"] == test_user.place
    assert user["dob"] == "1996-01-01"


def test_get_users_requires_authentication(client):
    response = client.get("/users")

    assert response.status_code == 401


def test_get_current_user(authenticated_client, test_user):
    response = authenticated_client.get("/me")

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == test_user.id
    assert data["name"] == test_user.name
    assert data["dob"] == "1996-01-01"
    assert data["place"] == test_user.place


def test_update_user_success(authenticated_client, test_user):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "name": "updateduser",
            "dob": "1994-10-20",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == test_user.id
    assert data["name"] == "updateduser"
    assert data["dob"] == "1994-10-20"
    assert data["place"] == "Bengaluru"

    assert data["age"] > 0


def test_update_user_rejects_manual_age(authenticated_client, test_user):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "name": "updateduser",
            "age": 31,
            "dob": "1994-10-20",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "Age should not be provided manually" in data["error"]


def test_update_user_rejects_invalid_date(authenticated_client, test_user):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "name": "updateduser",
            "dob": "20-10-1994",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Invalid date format. Use 'YYYY-MM-DD'."


def test_update_user_rejects_other_user(
    authenticated_client,
    other_user,
):
    response = authenticated_client.put(
        f"/users/{other_user.id}",
        json={
            "name": "hackerupdate",
            "dob": "1994-10-20",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 403

    data = response.get_json()

    assert data["error"] == "Unauthorized"


def test_delete_user_requires_authentication(client, test_user):
    response = client.delete(f"/users/{test_user.id}")

    assert response.status_code == 401


def test_can_delete_user_with_no_balances(
    authenticated_client,
    test_user,
):
    response = authenticated_client.get(
        f"/users/{test_user.id}/can_delete"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["can_delete"] is True
    assert data["details"]["has_bank_balances"] is False
    assert data["details"]["has_asset_balances"] is False
    assert data["details"]["has_saving_balances"] is False
    assert data["details"]["has_credit_balances"] is False


def test_can_delete_user_rejects_other_user(
    authenticated_client,
    other_user,
):
    response = authenticated_client.get(
        f"/users/{other_user.id}/can_delete"
    )

    assert response.status_code == 403

    data = response.get_json()

    assert data["error"] == "Unauthorized"


def test_delete_user_success(authenticated_client, test_user, db_session):
    response = authenticated_client.delete(
        f"/users/{test_user.id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == "User deleted successfully"

    deleted_user = db_session.get(type(test_user), test_user.id)

    assert deleted_user is None


def test_can_delete_user_rejects_existing_bank_balance(
    authenticated_client,
    test_user,
    db_session,
):
    from app.models import Bank

    bank = Bank(
        name="testbank",
        user_id=test_user.id,
        balance=1000,
    )

    db_session.add(bank)
    db_session.commit()

    response = authenticated_client.get(
        f"/users/{test_user.id}/can_delete"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["can_delete"] is False
    assert data["details"]["has_bank_balances"] is True
    assert data["message"] == (
        "Cannot delete user account. "
        "Please clear all balances from: bank accounts and try again."
    )

    db_session.delete(bank)
    db_session.commit()


