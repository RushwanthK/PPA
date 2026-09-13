from datetime import datetime, timezone
from app.models import (
    User,
    Bank,    
    Transaction,
    TransferTransaction,
    Asset,
    Saving,
    CreditCard,
)


# ============================================================
# REGISTRATION
# ============================================================

def test_register_user_success(client):
    response = client.post(
        "/register",
        json={
            "name": "newregisteruser",
            "password": "Password123!",
            "dob": "1995-05-10",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "User registered successfully"


def test_register_user_requires_name(client):
    response = client.post(
        "/register",
        json={
            "password": "Password123!",
            "dob": "1995-05-10",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Missing required fields"


def test_register_user_requires_password(client):
    response = client.post(
        "/register",
        json={
            "name": "missingpassword",
            "dob": "1995-05-10",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Missing required fields"


def test_register_user_requires_dob(client):
    response = client.post(
        "/register",
        json={
            "name": "missingdob",
            "password": "Password123!",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Missing required fields"


def test_register_user_requires_place(client):
    response = client.post(
        "/register",
        json={
            "name": "missingplace",
            "password": "Password123!",
            "dob": "1995-05-10",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Missing required fields"


def test_register_user_rejects_duplicate_username(
    client,
    test_user,
):
    response = client.post(
        "/register",
        json={
            "name": test_user.name,
            "password": "Password123!",
            "dob": "1995-05-10",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Username already taken"


def test_register_user_rejects_invalid_date(client):
    response = client.post(
        "/register",
        json={
            "name": "invaliddateuser",
            "password": "Password123!",
            "dob": "10-05-1995",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert "Invalid" in data["error"]


# ============================================================
# LOGIN
# ============================================================

def test_login_success(
    client,
    test_user,
):
    response = client.post(
        "/login",
        json={
            "name": test_user.name,
            "password": "TestPassword123!",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert "token" in data
    assert "user" in data
    assert data["user"]["id"] == test_user.id
    assert data["user"]["name"] == test_user.name


def test_login_requires_name(client):
    response = client.post(
        "/login",
        json={
            "password": "Password123!",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Name and password required"


def test_login_requires_password(
    client,
    test_user,
):
    response = client.post(
        "/login",
        json={
            "name": test_user.name,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Name and password required"


def test_login_rejects_unknown_user(client):
    response = client.post(
        "/login",
        json={
            "name": "doesnotexist",
            "password": "Password123!",
        },
    )

    assert response.status_code == 401

    data = response.get_json()

    assert data["error"] == "Invalid credentials"


def test_login_rejects_wrong_password(
    client,
    test_user,
):
    response = client.post(
        "/login",
        json={
            "name": test_user.name,
            "password": "WrongPassword!",
        },
    )

    assert response.status_code == 401

    data = response.get_json()

    assert data["error"] == "Invalid credentials"


# ============================================================
# GET /users
# ============================================================

def test_get_users_returns_current_user(
    authenticated_client,
    test_user,
):
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


# ============================================================
# GET /me
# ============================================================

def test_get_current_user(
    authenticated_client,
    test_user,
):
    response = authenticated_client.get("/me")

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == test_user.id
    assert data["name"] == test_user.name
    assert data["dob"] == "1996-01-01"
    assert data["place"] == test_user.place


def test_get_current_user_requires_authentication(client):
    response = client.get("/me")

    assert response.status_code == 401


# ============================================================
# UPDATE USER
# ============================================================

def test_update_user_success(
    authenticated_client,
    test_user,
):
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


def test_update_user_requires_authentication(
    client,
    test_user,
):
    response = client.put(
        f"/users/{test_user.id}",
        json={
            "name": "updateduser",
            "dob": "1994-10-20",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 401


def test_update_user_rejects_manual_age(
    authenticated_client,
    test_user,
):
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


def test_update_user_rejects_invalid_date(
    authenticated_client,
    test_user,
):
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

    assert data["error"] == (
        "Invalid date format. Use 'YYYY-MM-DD'."
    )


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


def test_update_user_rejects_duplicate_username(
    authenticated_client,
    test_user,
    other_user,
):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "name": other_user.name,
            "dob": "1994-10-20",
            "place": "Bengaluru",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Username already exists"


def test_update_user_missing_name(
    authenticated_client,
    test_user,
):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "dob": "1994-10-20",
            "place": "Bengaluru",
        },
    )

    assert response.status_code in (400, 500)

    data = response.get_json()

    assert data is not None
    assert "error" in data


def test_update_user_missing_dob(
    authenticated_client,
    test_user,
):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "name": "updateduser",
            "place": "Bengaluru",
        },
    )

    assert response.status_code in (400, 500)

    data = response.get_json()

    assert data is not None
    assert "error" in data


def test_update_user_missing_place(
    authenticated_client,
    test_user,
):
    response = authenticated_client.put(
        f"/users/{test_user.id}",
        json={
            "name": "updateduser",
            "dob": "1994-10-20",
        },
    )

    assert response.status_code in (400, 500)

    data = response.get_json()

    assert data is not None
    assert "error" in data


# ============================================================
# DELETE USER
# ============================================================

def test_delete_user_requires_authentication(
    client,
    test_user,
):
    response = client.delete(
        f"/users/{test_user.id}"
    )

    assert response.status_code == 401


def test_delete_user_rejects_other_user(
    authenticated_client,
    other_user,
):
    response = authenticated_client.delete(
        f"/users/{other_user.id}"
    )

    assert response.status_code == 403

    data = response.get_json()

    assert data["error"] == "Unauthorized"


def test_delete_nonexistent_user(
    authenticated_client,
    test_user,
):
    response = authenticated_client.delete(
        "/users/999999"
    )

    assert response.status_code in (403, 404)

    data = response.get_json()

    assert data is not None
    assert "error" in data or "message" in data


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

    assert "message" in data


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


def test_can_delete_nonexistent_user(
    authenticated_client,
):
    response = authenticated_client.get(
        "/users/999999/can_delete"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "User not found"


def test_can_delete_user_rejects_existing_bank_balance(
    authenticated_client,
    test_user,
    db_session,
):
    bank = Bank(
        name="User Delete Bank",
        user_id=test_user.id,
        balance=1000,
    )

    db_session.add(bank)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/users/{test_user.id}/can_delete"
        )

        assert response.status_code == 200

        data = response.get_json()

        assert data["can_delete"] is False
        assert data["details"]["has_bank_balances"] is True

        assert "bank accounts" in data["message"]

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


def test_can_delete_user_rejects_existing_asset_balance(
    authenticated_client,
    test_user,
    db_session,
):
    asset = Asset(
        name="User Delete Asset",
        user_id=test_user.id,
        balance=1000,
    )

    db_session.add(asset)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/users/{test_user.id}/can_delete"
        )

        assert response.status_code == 200

        data = response.get_json()

        assert data["can_delete"] is False
        assert data["details"]["has_asset_balances"] is True

        assert "assets" in data["message"]

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            asset.id,
        )

        if existing_asset is not None:
            db_session.delete(existing_asset)
            db_session.commit()


def test_can_delete_user_rejects_existing_saving_balance(
    authenticated_client,
    test_user,
    db_session,
):
    saving = Saving(
        name="User Delete Saving",
        user_id=test_user.id,
        balance=1000,
    )

    db_session.add(saving)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/users/{test_user.id}/can_delete"
        )

        assert response.status_code == 200

        data = response.get_json()

        assert data["can_delete"] is False
        assert data["details"]["has_saving_balances"] is True

        assert "savings" in data["message"]

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


def test_can_delete_user_rejects_existing_credit_balance(
    authenticated_client,
    test_user,
    db_session,
):
    credit_card = CreditCard(
        name="User Delete Credit Card",
        user_id=test_user.id,
        limit=50000,
        used=1000,
        billing_cycle_start=1,
    )

    db_session.add(credit_card)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/users/{test_user.id}/can_delete"
        )

        assert response.status_code == 200

        data = response.get_json()

        assert data["can_delete"] is False
        assert data["details"]["has_credit_balances"] is True

        assert "credit cards" in data["message"]

    finally:
        db_session.rollback()

        existing_card = db_session.get(
            CreditCard,
            credit_card.id,
        )

        if existing_card is not None:
            db_session.delete(existing_card)
            db_session.commit()


def test_delete_user_rejects_existing_bank_balance(
    authenticated_client,
    test_user,
    db_session,
):
    bank = Bank(
        name="Delete Blocked Bank",
        user_id=test_user.id,
        balance=1000,
    )

    db_session.add(bank)
    db_session.commit()

    try:
        response = authenticated_client.delete(
            f"/users/{test_user.id}"
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == (
            "Cannot delete user with existing balances"
        )

        assert data["details"]["has_bank_balances"] is True
        assert data["details"]["has_asset_balances"] is False
        assert data["details"]["has_saving_balances"] is False
        assert data["details"]["has_credit_balances"] is False

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


def test_delete_user_success(
    authenticated_client,
    test_user,
    db_session,
):
    user_id = test_user.id

    response = authenticated_client.delete(
        f"/users/{user_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == "User deleted successfully"

    deleted_user = db_session.get(
        User,
        user_id,
    )

    assert deleted_user is None


# ============================================================
# ACCOUNT DELETION + TRANSACTION HISTORY
# ============================================================

def test_can_delete_user_with_transaction_history(
    authenticated_client,
    test_user,
    test_bank,
):
    """
    Transaction history must not prevent account deletion
    when all active balances are zero.
    """

    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 10000,
            "type": "expense",
            "description": "Clear bank balance",
            "category": "Test",
        },
    )

    assert response.status_code == 201

    balance_response = authenticated_client.get(
        f"/bank_balance?bank_id={test_bank.id}"
    )

    assert balance_response.status_code == 200

    balance_data = balance_response.get_json()

    assert balance_data["balance"] == 0

    response = authenticated_client.get(
        f"/users/{test_user.id}/can_delete"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["can_delete"] is True
    assert data["has_transaction_history"] is True
    assert data["transaction_count"] == 1

    assert data["details"]["has_bank_balances"] is False


def test_delete_user_with_transaction_history(
    authenticated_client,
    test_user,
    test_bank,
    db_session,
):
    user_id = test_user.id
    bank_id = test_bank.id

    # Create transaction history.
    response = authenticated_client.post(
        f"/banks/{bank_id}/transactions",
        json={
            "amount": 10000,
            "type": "expense",
            "description": "Clear balance before deletion",
            "category": "Test",
        },
    )

    assert response.status_code == 201

    # Verify the bank balance is zero.
    db_session.expire_all()

    bank = db_session.get(
        Bank,
        bank_id,
    )

    assert bank is not None
    assert bank.balance == 0

    transaction_count = (
        db_session.query(Transaction)
        .filter(
            Transaction.user_id == user_id
        )
        .count()
    )

    assert transaction_count == 1

    # Delete the account.
    response = authenticated_client.delete(
        f"/users/{user_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "User deleted successfully"
    )

    assert data["deleted_transaction_count"] == 1

    # User must be gone.
    deleted_user = db_session.get(
        User,
        user_id,
    )

    assert deleted_user is None

    # Transaction history must be gone.
    remaining_transactions = (
        db_session.query(Transaction)
        .filter(
            Transaction.user_id == user_id
        )
        .count()
    )

    assert remaining_transactions == 0

    # Bank should also have disappeared with the account.
    deleted_bank = db_session.get(
        Bank,
        bank_id,
    )

    assert deleted_bank is None

def test_delete_user_with_transfer_history(
    authenticated_client,
    test_user,
    db_session,
):
    transfer = TransferTransaction(
        user_id=test_user.id,
        amount=500,
        date=datetime.now(timezone.utc),
        from_account_type="Bank",
        from_account_id=1,
        to_account_type="Saving",
        to_account_id=1,
        description="Test transfer",
        fee=0,
    )

    db_session.add(transfer)
    db_session.commit()

    transfer_id = transfer.id
    user_id = test_user.id

    transfer_exists = db_session.get(
        TransferTransaction,
        transfer_id,
    )

    assert transfer_exists is not None

    response = authenticated_client.delete(
        f"/users/{user_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["deleted_transfer_count"] == 1

    deleted_transfer = db_session.get(
        TransferTransaction,
        transfer_id,
    )

    assert deleted_transfer is None

    deleted_user = db_session.get(
        User,
        user_id,
    )

    assert deleted_user is None

def test_can_delete_user_with_transaction_history_but_nonzero_balance(
    authenticated_client,
    test_bank,
    test_user,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 1000,
            "type": "income",
            "description": "Additional balance",
            "category": "Test",
        },
    )

    assert response.status_code == 201

    response = authenticated_client.get(
        f"/users/{test_user.id}/can_delete"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["can_delete"] is False

    assert data["has_transaction_history"] is True
    assert data["transaction_count"] == 1

    assert data["details"]["has_bank_balances"] is True

