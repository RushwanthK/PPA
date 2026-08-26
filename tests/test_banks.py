def test_get_banks_returns_user_banks(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get("/banks")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    bank = data[0]

    assert bank["id"] == test_bank.id
    assert bank["name"] == test_bank.name
    assert bank["balance"] == test_bank.balance


def test_get_banks_requires_authentication(client):
    response = client.get("/banks")

    assert response.status_code == 401


def test_create_bank_success(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "name": "New Test Bank",
            "balance": 5000,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert "message" in data

    assert data["bank"]["name"] == "New Test Bank"
    assert data["bank"]["balance"] == 5000


def test_create_bank_requires_authentication(client):
    response = client.post(
        "/banks",
        json={
            "name": "Unauthorized Bank",
            "balance": 1000,
        },
    )

    assert response.status_code == 401


def test_update_bank_success(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.put(
        f"/banks/{test_bank.id}",
        json={
            "name": "Updated Bank",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert "message" in data

    assert data["bank"]["name"] == "Updated Bank"


def test_update_nonexistent_bank(
    authenticated_client,
):
    response = authenticated_client.put(
        "/banks/999999",
        json={
            "name": "Updated Bank",
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert "error" in data or "message" in data


def test_delete_bank_requires_authentication(
    client,
    test_bank,
):
    response = client.delete(
        f"/banks/{test_bank.id}"
    )

    assert response.status_code == 401


def test_delete_nonexistent_bank(
    authenticated_client,
):
    response = authenticated_client.delete(
        "/banks/999999"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert "error" in data or "message" in data


def test_other_user_cannot_modify_bank(
    authenticated_client,
    other_user,
    db_session,
):
    from app.models import Bank

    other_bank = Bank(
        name="Other User Bank",
        balance=2000,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/banks/{other_bank.id}",
            json={
                "name": "Unauthorized Update",
            },
        )

        assert response.status_code in (403, 404)

    finally:
        existing_bank = db_session.get(Bank, other_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()

def test_add_bank_transaction_success(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 1000,
            "type": "income",
            "description": "Salary",
            "date": "2026-08-24",
        },
    )

    assert response.status_code in (200, 201)

    data = response.get_json()

    assert "message" in data


def test_get_bank_transactions(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)


def test_bank_transactions_require_authentication(
    client,
    test_bank,
):
    response = client.get(
        f"/banks/{test_bank.id}/transactions"
    )

    assert response.status_code == 401


def test_bank_balance_endpoint(
    authenticated_client,
):
    response = authenticated_client.get("/bank_balance")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, dict)

def test_bank_balance_requires_authentication(client):
    response = client.get("/bank_balance")

    assert response.status_code == 401