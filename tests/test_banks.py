from app.models import Bank, BankTransaction, Saving


# ============================================================
# GET /banks
# ============================================================

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
    assert bank["user_id"] == test_bank.user_id


def test_get_banks_requires_authentication(client):
    response = client.get("/banks")

    assert response.status_code == 401


def test_get_banks_does_not_return_other_users_banks(
    authenticated_client,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other User Bank",
        balance=2500,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.get("/banks")

        assert response.status_code == 200

        data = response.get_json()

        assert data == []

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, other_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


# ============================================================
# CREATE BANK
# ============================================================

def test_create_bank_success(
    authenticated_client,
    db_session,
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

    assert data["message"] == "Bank created successfully"

    assert data["bank"]["name"] == "New Test Bank"
    assert data["bank"]["balance"] == 5000
    assert data["bank"]["user_id"] is not None


def test_create_bank_uses_default_zero_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "name": "Zero Balance Bank",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["bank"]["balance"] == 0


def test_create_bank_requires_authentication(client):
    response = client.post(
        "/banks",
        json={
            "name": "Unauthorized Bank",
            "balance": 1000,
        },
    )

    assert response.status_code == 401


def test_create_bank_requires_name(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "balance": 1000,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Bank name is required"


def test_create_bank_rejects_blank_name(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "name": "   ",
            "balance": 1000,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Bank name is required"


def test_create_bank_rejects_invalid_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "name": "Invalid Balance Bank",
            "balance": "abc",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Balance must be a valid number"


def test_create_bank_rejects_negative_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "name": "Negative Bank",
            "balance": -100,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Bank balance cannot be negative"


def test_create_bank_rejects_duplicate_name(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        "/banks",
        json={
            "name": test_bank.name,
            "balance": 5000,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Bank name already exists"


# ============================================================
# UPDATE BANK
# ============================================================

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

    assert data["message"] == "Bank updated successfully"

    assert data["bank"]["id"] == test_bank.id
    assert data["bank"]["name"] == "Updated Bank"
    assert data["bank"]["balance"] == 10000


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

    assert data["error"] == "Bank not found"


def test_update_bank_requires_authentication(
    client,
    test_bank,
):
    response = client.put(
        f"/banks/{test_bank.id}",
        json={
            "name": "Unauthorized Update",
        },
    )

    assert response.status_code == 401


def test_update_bank_requires_name(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.put(
        f"/banks/{test_bank.id}",
        json={},
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Bank name is required"


def test_update_bank_rejects_blank_name(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.put(
        f"/banks/{test_bank.id}",
        json={
            "name": "   ",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Bank name is required"


def test_update_bank_rejects_duplicate_name(
    authenticated_client,
    test_bank,
    db_session,
):
    second_bank = Bank(
        name="Second Test Bank",
        balance=0,
        user_id=test_bank.user_id,
    )

    db_session.add(second_bank)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/banks/{test_bank.id}",
            json={
                "name": second_bank.name,
            },
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == "Bank name already exists"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, second_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


def test_other_user_cannot_update_bank(
    authenticated_client,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other User Update Bank",
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

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, other_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


# ============================================================
# DELETE BANK
# ============================================================

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

    assert data["error"] == "Bank not found"


def test_delete_bank_rejects_non_zero_balance(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.delete(
        f"/banks/{test_bank.id}"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Cannot delete bank with non-zero balance"
    )


def test_delete_bank_success(
    authenticated_client,
    test_user,
    db_session,
):
    bank = Bank(
        name="Delete Me Bank",
        user_id=test_user.id,
        balance=0,
    )

    db_session.add(bank)
    db_session.commit()

    bank_id = bank.id

    response = authenticated_client.delete(
        f"/banks/{bank_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == "Bank deleted successfully"

    deleted_bank = db_session.get(Bank, bank_id)

    assert deleted_bank is None


def test_other_user_cannot_delete_bank(
    authenticated_client,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other User Delete Bank",
        balance=0,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.delete(
            f"/banks/{other_bank.id}"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, other_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


def test_delete_bank_rejects_linked_savings(
    authenticated_client,
    test_bank,
    test_user,
    db_session,
):
    saving = Saving(
        name="Linked Saving",
        bank_id=test_bank.id,
        user_id=test_user.id,
        balance=0,
    )

    # Temporarily zero the bank so the linked-saving rule
    # becomes the rule being tested.
    test_bank.balance = 0

    db_session.add(saving)
    db_session.commit()

    try:
        response = authenticated_client.delete(
            f"/banks/{test_bank.id}"
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == (
            "Cannot delete bank because it has linked savings accounts"
        )

        assert data["linked_savings_count"] == 1

    finally:
        db_session.rollback()

        existing_saving = db_session.get(Saving, saving.id)

        if existing_saving is not None:
            db_session.delete(existing_saving)

        existing_bank = db_session.get(Bank, test_bank.id)

        if existing_bank is not None:
            existing_bank.balance = 10000

        db_session.commit()


# ============================================================
# BANK TRANSACTIONS - CREATE
# ============================================================

def test_add_bank_income_transaction_success(
    authenticated_client,
    test_bank,
    db_session,
):
    starting_balance = test_bank.balance

    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 1000,
            "type": "income",
            "description": "Salary",
            "category": "Income",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added successfully"
    assert data["balance"] == starting_balance + 1000

    transaction = (
        BankTransaction.query
        .filter_by(bank_id=test_bank.id)
        .order_by(BankTransaction.id.desc())
        .first()
    )

    assert transaction is not None
    assert transaction.user_id == test_bank.user_id
    assert transaction.amount == 1000
    assert transaction.transaction_type == "income"
    assert transaction.bank_balance_after == starting_balance + 1000


def test_add_bank_expense_transaction_success(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 1500,
            "type": "expense",
            "description": "Rent",
            "category": "Expense",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added successfully"
    assert data["balance"] == 8500


def test_add_bank_transaction_requires_authentication(
    client,
    test_bank,
):
    response = client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 1000,
            "type": "income",
        },
    )

    assert response.status_code == 401


def test_add_bank_transaction_requires_amount(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "type": "income",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Amount is required"


def test_add_bank_transaction_rejects_invalid_amount(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": "abc",
            "type": "income",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Amount must be a valid number"


def test_add_bank_transaction_rejects_zero_amount(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 0,
            "type": "income",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Amount must be greater than 0"


def test_add_bank_transaction_rejects_negative_amount(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": -100,
            "type": "income",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Amount must be greater than 0"


def test_add_bank_transaction_rejects_invalid_type(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 100,
            "type": "transfer",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Invalid transaction type"


def test_add_bank_transaction_rejects_insufficient_balance(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 20000,
            "type": "expense",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Insufficient balance"


def test_add_bank_transaction_nonexistent_bank(
    authenticated_client,
):
    response = authenticated_client.post(
        "/banks/999999/transactions",
        json={
            "amount": 1000,
            "type": "income",
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Bank not found"


def test_other_user_cannot_add_bank_transaction(
    authenticated_client,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other Transaction Bank",
        balance=5000,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.post(
            f"/banks/{other_bank.id}/transactions",
            json={
                "amount": 1000,
                "type": "income",
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, other_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


# ============================================================
# BANK TRANSACTIONS - GET
# ============================================================

def test_get_bank_transactions(
    authenticated_client,
    test_bank,
):
    authenticated_client.post(
        f"/banks/{test_bank.id}/transactions",
        json={
            "amount": 1000,
            "type": "income",
            "description": "Salary",
            "category": "Income",
        },
    )

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    transaction = data[0]

    assert transaction["amount"] == 1000
    assert transaction["transaction_type"] == "income"
    assert transaction["description"] == "Salary"
    assert transaction["category"] == "Income"
    assert transaction["bank_balance_after"] == 11000


def test_get_bank_transactions_empty_bank(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data == []


def test_get_bank_transactions_requires_authentication(
    client,
    test_bank,
):
    response = client.get(
        f"/banks/{test_bank.id}/transactions"
    )

    assert response.status_code == 401


def test_get_bank_transactions_nonexistent_bank(
    authenticated_client,
):
    response = authenticated_client.get(
        "/banks/999999/transactions"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Bank not found"


def test_other_user_cannot_get_bank_transactions(
    authenticated_client,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other Read Bank",
        balance=1000,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/banks/{other_bank.id}/transactions"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(Bank, other_bank.id)

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


# ============================================================
# BANK BALANCE
# ============================================================

def test_bank_balance_endpoint(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get(
        f"/bank_balance?bank_id={test_bank.id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == test_bank.id
    assert data["name"] == test_bank.name
    assert data["balance"] == test_bank.balance


def test_bank_balance_requires_authentication(
    client,
    test_bank,
):
    response = client.get(
        f"/bank_balance?bank_id={test_bank.id}"
    )

    assert response.status_code == 401


def test_bank_balance_returns_current_bank_balance(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get(
        f"/bank_balance?bank_id={test_bank.id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["id"] == test_bank.id
    assert data["name"] == test_bank.name
    assert data["balance"] == test_bank.balance


def test_bank_balance_requires_bank_id(
    authenticated_client,
):
    response = authenticated_client.get(
        "/bank_balance"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "bank_id parameter is required"


def test_bank_balance_rejects_nonexistent_bank(
    authenticated_client,
):
    response = authenticated_client.get(
        "/bank_balance?bank_id=999999"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Bank not found"


def test_bank_balance_rejects_other_users_bank(
    authenticated_client,
    other_user,
    db_session,
):
    from app.models import Bank

    other_bank = Bank(
        name="Other User Balance Bank",
        user_id=other_user.id,
        balance=2500,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/bank_balance?bank_id={other_bank.id}"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(
            Bank,
            other_bank.id
        )

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()