from app.models import (
    Bank,
    Saving,
    SavingTransaction,
)


# ============================================================
# GET /savings
# ============================================================

def test_get_savings_returns_user_savings(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.get("/savings")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    saving = data[0]

    assert saving["id"] == test_saving.id
    assert saving["name"] == test_saving.name
    assert saving["user_id"] == test_saving.user_id
    assert saving["bank_id"] == test_saving.bank_id
    assert saving["bank_name"] == "Test Bank"
    assert saving["balance"] == test_saving.balance


def test_get_savings_requires_authentication(client):
    response = client.get("/savings")

    assert response.status_code == 401


def test_get_savings_does_not_return_other_users_savings(
    authenticated_client,
    other_user,
    db_session,
    test_bank,
):
    other_saving = Saving(
        name="Other User Saving",
        user_id=other_user.id,
        bank_id=test_bank.id,
        balance=3000,
    )

    db_session.add(other_saving)
    db_session.commit()

    try:
        response = authenticated_client.get("/savings")

        assert response.status_code == 200

        data = response.get_json()

        assert len(data) == 0

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            other_saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


# ============================================================
# CREATE /savings
# ============================================================

def test_create_saving_success(
    authenticated_client,
    test_user,
    test_bank,
    db_session,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "New Test Saving",
            "bank_id": test_bank.id,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Saving account created!"
    assert "saving" in data

    saving = data["saving"]

    assert saving["id"] is not None
    assert saving["name"] == "New Test Saving"
    assert saving["user_id"] == test_user.id
    assert saving["bank_id"] == test_bank.id
    assert saving["balance"] == 0

    created_saving = db_session.get(
        Saving,
        saving["id"],
    )

    assert created_saving is not None
    assert created_saving.name == "New Test Saving"
    assert created_saving.user_id == test_user.id
    assert created_saving.bank_id == test_bank.id
    assert created_saving.balance == 0

    db_session.delete(created_saving)
    db_session.commit()


def test_create_saving_requires_authentication(client):
    response = client.post(
        "/savings",
        json={
            "name": "Unauthorized Saving",
            "bank_id": 1,
        },
    )

    assert response.status_code == 401


def test_create_saving_requires_name(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "bank_id": test_bank.id,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Saving account name is required"


def test_create_saving_rejects_blank_name(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "   ",
            "bank_id": test_bank.id,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Saving account name is required"


def test_create_saving_rejects_empty_name(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "",
            "bank_id": test_bank.id,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Saving account name is required"


def test_create_saving_rejects_missing_json_body(
    authenticated_client,
):
    response = authenticated_client.post(
        "/savings",
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Saving account name is required"


def test_create_saving_requires_bank(
    authenticated_client,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "No Bank Saving",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Savings account must be linked to a bank"
    )


def test_create_saving_rejects_null_bank(
    authenticated_client,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "Null Bank Saving",
            "bank_id": None,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Savings account must be linked to a bank"
    )


def test_create_saving_rejects_zero_bank_id(
    authenticated_client,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "Zero Bank Saving",
            "bank_id": 0,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Savings account must be linked to a bank"
    )


def test_create_saving_rejects_nonexistent_bank(
    authenticated_client,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "Invalid Bank Saving",
            "bank_id": 999999,
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Bank not found"


def test_create_saving_rejects_other_users_bank(
    authenticated_client,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other User Saving Bank",
        balance=10000,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.post(
            "/savings",
            json={
                "name": "Cross User Saving",
                "bank_id": other_bank.id,
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(
            Bank,
            other_bank.id,
        )

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


def test_create_saving_rejects_balance(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "Manual Balance Saving",
            "bank_id": test_bank.id,
            "balance": 5000,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Balance cannot be set during savings creation. "
        "Use transactions instead."
    )


def test_create_saving_rejects_duplicate_name(
    authenticated_client,
    test_saving,
    test_bank,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": test_saving.name,
            "bank_id": test_bank.id,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Saving account name already exists"
    )


def test_create_saving_strips_name_whitespace(
    authenticated_client,
    test_bank,
    db_session,
):
    response = authenticated_client.post(
        "/savings",
        json={
            "name": "   Emergency Fund   ",
            "bank_id": test_bank.id,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Saving account created!"
    assert data["saving"]["name"] == "Emergency Fund"

    created_saving = db_session.get(
        Saving,
        data["saving"]["id"],
    )

    assert created_saving.name == "Emergency Fund"

    db_session.delete(created_saving)
    db_session.commit()


# ============================================================
# UPDATE /savings/<id>
# ============================================================

def test_update_saving_name_success(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "name": "Updated Saving",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "Saving account updated successfully"
    )

    assert data["saving"]["id"] == test_saving.id
    assert data["saving"]["name"] == "Updated Saving"
    assert data["saving"]["user_id"] == test_saving.user_id
    assert data["saving"]["bank_id"] == test_saving.bank_id
    assert data["saving"]["balance"] == 5000


def test_update_saving_requires_authentication(
    client,
    test_saving,
):
    response = client.put(
        f"/savings/{test_saving.id}",
        json={
            "name": "Unauthorized Update",
        },
    )

    assert response.status_code == 401


def test_update_nonexistent_saving(
    authenticated_client,
):
    response = authenticated_client.put(
        "/savings/999999",
        json={
            "name": "Updated Saving",
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Saving account not found"


def test_update_saving_rejects_other_users_saving(
    authenticated_client,
    other_user,
    db_session,
    test_bank,
):
    other_saving = Saving(
        name="Other User Update Saving",
        user_id=other_user.id,
        bank_id=test_bank.id,
        balance=5000,
    )

    db_session.add(other_saving)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/savings/{other_saving.id}",
            json={
                "name": "Unauthorized Update",
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Saving account not found"

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            other_saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


def test_update_saving_rejects_balance(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "balance": 10000,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Balance cannot be updated directly. "
        "Use transactions instead."
    )


def test_update_saving_does_not_change_balance_when_balance_rejected(
    authenticated_client,
    test_saving,
    db_session,
):
    starting_balance = test_saving.balance

    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "name": "Should Not Persist",
            "balance": 10000,
        },
    )

    assert response.status_code == 400

    db_session.expire_all()

    saving = db_session.get(
        Saving,
        test_saving.id,
    )

    assert saving.name == "Test Saving"
    assert saving.balance == starting_balance


def test_update_saving_rejects_removing_bank(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "bank_id": None,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Savings account must remain linked to a bank"
    )


def test_update_saving_rejects_zero_bank_id(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "bank_id": 0,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Savings account must remain linked to a bank"
    )


def test_update_saving_rejects_nonexistent_bank(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "bank_id": 999999,
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "New bank not found"


def test_update_saving_rejects_other_users_bank(
    authenticated_client,
    test_saving,
    other_user,
    db_session,
):
    other_bank = Bank(
        name="Other User Update Bank",
        balance=10000,
        user_id=other_user.id,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/savings/{test_saving.id}",
            json={
                "bank_id": other_bank.id,
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "New bank not found"

    finally:
        db_session.rollback()

        existing_bank = db_session.get(
            Bank,
            other_bank.id,
        )

        if existing_bank is not None:
            db_session.delete(existing_bank)
            db_session.commit()


def test_update_saving_rejects_blank_name(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "name": "   ",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Saving account name is required"


def test_update_saving_rejects_empty_name(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "name": "",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Saving account name is required"


def test_update_saving_rejects_duplicate_name(
    authenticated_client,
    test_saving,
    test_bank,
    db_session,
):
    second_saving = Saving(
        name="Second Saving",
        user_id=test_saving.user_id,
        bank_id=test_bank.id,
        balance=0,
    )

    db_session.add(second_saving)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/savings/{test_saving.id}",
            json={
                "name": second_saving.name,
            },
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == (
            "Saving account name already exists"
        )

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            second_saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


def test_update_saving_strips_name_whitespace(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.put(
        f"/savings/{test_saving.id}",
        json={
            "name": "   Updated Saving   ",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["saving"]["name"] == "Updated Saving"


# ============================================================
# UPDATE SAVING - BANK TRANSFER BUSINESS RULES
# ============================================================

def test_update_saving_moves_balance_between_banks(
    authenticated_client,
    test_saving,
    test_bank,
    test_user,
    db_session,
):
    new_bank = Bank(
        name="New Saving Bank",
        balance=20000,
        user_id=test_user.id,
    )

    db_session.add(new_bank)
    db_session.commit()

    old_bank_start = test_bank.balance
    new_bank_start = new_bank.balance
    saving_balance = test_saving.balance

    try:
        response = authenticated_client.put(
            f"/savings/{test_saving.id}",
            json={
                "bank_id": new_bank.id,
            },
        )

        assert response.status_code == 200

        data = response.get_json()

        assert data["message"] == (
            "Saving account updated successfully"
        )

        db_session.expire_all()

        old_bank = db_session.get(
            Bank,
            test_bank.id,
        )

        updated_new_bank = db_session.get(
            Bank,
            new_bank.id,
        )

        updated_saving = db_session.get(
            Saving,
            test_saving.id,
        )

        assert old_bank.balance == (
            old_bank_start + saving_balance
        )

        assert updated_new_bank.balance == (
            new_bank_start - saving_balance
        )

        assert updated_saving.bank_id == new_bank.id
        assert updated_saving.balance == saving_balance

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            test_saving.id,
        )

        if existing_saving is not None:
            existing_saving.bank_id = test_bank.id
            db_session.commit()

        existing_new_bank = db_session.get(
            Bank,
            new_bank.id,
        )

        if existing_new_bank is not None:
            db_session.delete(existing_new_bank)
            db_session.commit()


def test_update_saving_rejects_insufficient_new_bank_balance(
    authenticated_client,
    test_saving,
    test_bank,
    test_user,
    db_session,
):
    new_bank = Bank(
        name="Insufficient Funds New Bank",
        balance=100,
        user_id=test_user.id,
    )

    db_session.add(new_bank)
    db_session.commit()

    old_bank_start = test_bank.balance
    new_bank_start = new_bank.balance
    saving_start = test_saving.balance
    saving_bank_start = test_saving.bank_id

    try:
        response = authenticated_client.put(
            f"/savings/{test_saving.id}",
            json={
                "bank_id": new_bank.id,
            },
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == (
            "New bank has insufficient funds for this transfer"
        )

        db_session.expire_all()

        old_bank = db_session.get(
            Bank,
            test_bank.id,
        )

        updated_new_bank = db_session.get(
            Bank,
            new_bank.id,
        )

        updated_saving = db_session.get(
            Saving,
            test_saving.id,
        )

        # Failed operation must not partially modify balances.
        assert old_bank.balance == old_bank_start
        assert updated_new_bank.balance == new_bank_start
        assert updated_saving.balance == saving_start
        assert updated_saving.bank_id == saving_bank_start

    finally:
        db_session.rollback()

        existing_new_bank = db_session.get(
            Bank,
            new_bank.id,
        )

        if existing_new_bank is not None:
            db_session.delete(existing_new_bank)
            db_session.commit()


def test_update_saving_bank_change_with_balance_rejection_is_atomic(
    authenticated_client,
    test_saving,
    test_bank,
    test_user,
    db_session,
):
    new_bank = Bank(
        name="Atomicity Test Bank",
        balance=20000,
        user_id=test_user.id,
    )

    db_session.add(new_bank)
    db_session.commit()

    old_bank_start = test_bank.balance
    new_bank_start = new_bank.balance
    saving_start = test_saving.balance
    saving_bank_start = test_saving.bank_id

    try:
        response = authenticated_client.put(
            f"/savings/{test_saving.id}",
            json={
                "bank_id": new_bank.id,
                "balance": 12345,
            },
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == (
            "Balance cannot be updated directly. "
            "Use transactions instead."
        )

        db_session.expire_all()

        old_bank = db_session.get(
            Bank,
            test_bank.id,
        )

        updated_new_bank = db_session.get(
            Bank,
            new_bank.id,
        )

        updated_saving = db_session.get(
            Saving,
            test_saving.id,
        )

        assert old_bank.balance == old_bank_start
        assert updated_new_bank.balance == new_bank_start
        assert updated_saving.balance == saving_start
        assert updated_saving.bank_id == saving_bank_start

    finally:
        db_session.rollback()

        existing_new_bank = db_session.get(
            Bank,
            new_bank.id,
        )

        if existing_new_bank is not None:
            db_session.delete(existing_new_bank)
            db_session.commit()


# ============================================================
# POST /savings/<id>/transactions
# ============================================================

def test_add_saving_deposit_success(
    authenticated_client,
    test_saving,
    test_bank,
    db_session,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
            "description": "Monthly Saving",
            "category": "Savings",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added"
    assert data["saving_balance"] == saving_start + 1000
    assert data["bank_balance"] == bank_start - 1000

    db_session.expire_all()

    saving = db_session.get(
        Saving,
        test_saving.id,
    )

    bank = db_session.get(
        Bank,
        test_bank.id,
    )

    assert saving.balance == saving_start + 1000
    assert bank.balance == bank_start - 1000

    transactions = db_session.query(
        SavingTransaction
    ).filter_by(
        saving_id=test_saving.id,
    ).all()

    assert len(transactions) == 1

    transaction = transactions[0]

    assert transaction.user_id == test_saving.user_id
    assert transaction.saving_id == test_saving.id
    assert transaction.amount == 1000
    assert transaction.transaction_type == "deposit"
    assert transaction.description == "Monthly Saving"
    assert transaction.category == "Savings"
    assert transaction.saving_balance_after == saving_start + 1000


def test_add_saving_withdrawal_success(
    authenticated_client,
    test_saving,
    test_bank,
    db_session,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
            "type": "withdrawal",
            "description": "Emergency Withdrawal",
            "category": "Emergency",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added"
    assert data["saving_balance"] == saving_start - 1000
    assert data["bank_balance"] == bank_start + 1000

    db_session.expire_all()

    saving = db_session.get(
        Saving,
        test_saving.id,
    )

    bank = db_session.get(
        Bank,
        test_bank.id,
    )

    assert saving.balance == saving_start - 1000
    assert bank.balance == bank_start + 1000


def test_add_saving_deposit_exact_bank_balance(
    authenticated_client,
    test_saving,
    test_bank,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance
    amount = bank_start

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": amount,
            "type": "deposit",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added"
    assert data["saving_balance"] == (
        saving_start + amount
    )
    assert data["bank_balance"] == 0


def test_add_saving_withdrawal_exact_saving_balance(
    authenticated_client,
    test_saving,
    test_bank,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance
    amount = saving_start

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": amount,
            "type": "withdrawal",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added"
    assert data["saving_balance"] == 0
    assert data["bank_balance"] == (
        bank_start + amount
    )


def test_add_saving_transaction_requires_authentication(
    client,
    test_saving,
):
    response = client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
        },
    )

    assert response.status_code == 401


def test_add_saving_transaction_nonexistent_saving(
    authenticated_client,
):
    response = authenticated_client.post(
        "/savings/999999/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Saving account not found"


def test_add_saving_transaction_requires_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Amount is required"


def test_add_saving_transaction_rejects_null_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": None,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Invalid amount"


def test_add_saving_transaction_rejects_invalid_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": "abc",
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Invalid amount"


def test_add_saving_transaction_rejects_zero_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 0,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be greater than zero"
    )


def test_add_saving_transaction_rejects_negative_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": -100,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be greater than zero"
    )


def test_add_saving_transaction_rejects_invalid_type(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
            "type": "invalid",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Transaction type must be deposit or withdrawal"
    )


def test_add_saving_transaction_defaults_to_deposit(
    authenticated_client,
    test_saving,
    test_bank,
    db_session,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Transaction added"
    assert data["saving_balance"] == (
        saving_start + 1000
    )
    assert data["bank_balance"] == (
        bank_start - 1000
    )

    transaction = db_session.query(
        SavingTransaction
    ).filter_by(
        saving_id=test_saving.id,
    ).one()

    assert transaction.transaction_type == "deposit"


def test_add_saving_withdrawal_rejects_insufficient_balance(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": test_saving.balance + 1,
            "type": "withdrawal",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Insufficient balance"


def test_add_saving_deposit_rejects_insufficient_bank_balance(
    authenticated_client,
    test_saving,
    test_bank,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": test_bank.balance + 1,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Insufficient bank balance"


def test_failed_saving_deposit_does_not_change_balances(
    authenticated_client,
    test_saving,
    test_bank,
    db_session,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": test_bank.balance + 1,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Insufficient bank balance"

    db_session.expire_all()

    saving = db_session.get(
        Saving,
        test_saving.id,
    )

    bank = db_session.get(
        Bank,
        test_bank.id,
    )

    assert saving.balance == saving_start
    assert bank.balance == bank_start

    transaction_count = db_session.query(
        SavingTransaction
    ).filter_by(
        saving_id=test_saving.id,
    ).count()

    assert transaction_count == 0


def test_failed_saving_withdrawal_does_not_change_balances(
    authenticated_client,
    test_saving,
    test_bank,
    db_session,
):
    saving_start = test_saving.balance
    bank_start = test_bank.balance

    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": test_saving.balance + 1,
            "type": "withdrawal",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Insufficient balance"

    db_session.expire_all()

    saving = db_session.get(
        Saving,
        test_saving.id,
    )

    bank = db_session.get(
        Bank,
        test_bank.id,
    )

    assert saving.balance == saving_start
    assert bank.balance == bank_start

    transaction_count = db_session.query(
        SavingTransaction
    ).filter_by(
        saving_id=test_saving.id,
    ).count()

    assert transaction_count == 0


def test_other_user_cannot_add_saving_transaction(
    authenticated_client,
    other_user,
    db_session,
    test_bank,
):
    other_saving = Saving(
        name="Other User Transaction Saving",
        user_id=other_user.id,
        bank_id=test_bank.id,
        balance=5000,
    )

    db_session.add(other_saving)
    db_session.commit()

    try:
        response = authenticated_client.post(
            f"/savings/{other_saving.id}/transactions",
            json={
                "amount": 1000,
                "type": "deposit",
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Saving account not found"

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            other_saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


def test_add_saving_transaction_rejects_nan_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": "NaN",
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Invalid amount"


def test_add_saving_transaction_rejects_infinite_amount(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": "Infinity",
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "Invalid amount"


# ============================================================
# GET /savings/<id>/transactions
# ============================================================

def test_get_saving_transactions_empty(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.get(
        f"/savings/{test_saving.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data == []


def test_get_saving_transactions_returns_history(
    authenticated_client,
    test_saving,
):
    create_response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
            "description": "Monthly Saving",
            "category": "Savings",
        },
    )

    assert create_response.status_code == 201

    response = authenticated_client.get(
        f"/savings/{test_saving.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    transaction = data[0]

    assert transaction["amount"] == 1000
    assert transaction["description"] == "Monthly Saving"
    assert transaction["category"] == "Savings"
    assert transaction["transaction_type"] == "deposit"
    assert transaction["saving_balance_after"] == 6000
    assert transaction["id"] is not None
    assert transaction["date"] is not None


def test_get_saving_transactions_requires_authentication(
    client,
    test_saving,
):
    response = client.get(
        f"/savings/{test_saving.id}/transactions"
    )

    assert response.status_code == 401


def test_get_saving_transactions_nonexistent_saving(
    authenticated_client,
):
    response = authenticated_client.get(
        "/savings/999999/transactions"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Saving account not found"


def test_other_user_cannot_get_saving_transactions(
    authenticated_client,
    other_user,
    db_session,
    test_bank,
):
    other_saving = Saving(
        name="Other User History Saving",
        user_id=other_user.id,
        bank_id=test_bank.id,
        balance=5000,
    )

    db_session.add(other_saving)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/savings/{other_saving.id}/transactions"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == "Saving account not found"

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            other_saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


def test_get_saving_transactions_uses_empty_strings_for_missing_optional_fields(
    authenticated_client,
    test_saving,
):
    create_response = authenticated_client.post(
        f"/savings/{test_saving.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
        },
    )

    assert create_response.status_code == 201

    response = authenticated_client.get(
        f"/savings/{test_saving.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert len(data) == 1

    transaction = data[0]

    assert transaction["description"] == ""
    assert transaction["category"] == ""


# ============================================================
# DELETE /savings/<id>
# ============================================================

def test_delete_saving_requires_authentication(
    client,
    test_saving,
):
    response = client.delete(
        f"/savings/{test_saving.id}"
    )

    assert response.status_code == 401


def test_delete_nonexistent_saving(
    authenticated_client,
):
    response = authenticated_client.delete(
        "/savings/999999"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "Saving account not found"


def test_delete_saving_rejects_non_zero_balance(
    authenticated_client,
    test_saving,
):
    response = authenticated_client.delete(
        f"/savings/{test_saving.id}"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Saving account cannot be deleted because "
        "its balance is not zero."
    )


def test_delete_saving_does_not_delete_non_zero_balance(
    authenticated_client,
    test_saving,
    db_session,
):
    response = authenticated_client.delete(
        f"/savings/{test_saving.id}"
    )

    assert response.status_code == 400

    saving = db_session.get(
        Saving,
        test_saving.id,
    )

    assert saving is not None
    assert saving.balance == 5000


def test_delete_saving_success(
    authenticated_client,
    test_user,
    test_bank,
    db_session,
):
    saving = Saving(
        name="Delete Me Saving",
        user_id=test_user.id,
        bank_id=test_bank.id,
        balance=0,
    )

    db_session.add(saving)
    db_session.commit()

    saving_id = saving.id

    response = authenticated_client.delete(
        f"/savings/{saving_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "Saving account deleted successfully"
    )

    deleted_saving = db_session.get(
        Saving,
        saving_id,
    )

    assert deleted_saving is None


def test_other_user_cannot_delete_saving(
    authenticated_client,
    other_user,
    db_session,
    test_bank,
):
    other_saving = Saving(
        name="Other User Delete Saving",
        user_id=other_user.id,
        bank_id=test_bank.id,
        balance=0,
    )

    db_session.add(other_saving)
    db_session.commit()

    try:
        response = authenticated_client.delete(
            f"/savings/{other_saving.id}"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == (
            "Saving account not found"
        )

        existing_saving = db_session.get(
            Saving,
            other_saving.id,
        )

        assert existing_saving is not None

    finally:
        db_session.rollback()

        existing_saving = db_session.get(
            Saving,
            other_saving.id,
        )

        if existing_saving is not None:
            db_session.delete(existing_saving)
            db_session.commit()


def test_delete_zero_balance_saving_with_transaction_history(
    authenticated_client,
    test_user,
    test_bank,
    db_session,
):
    saving = Saving(
        name="History Delete Saving",
        user_id=test_user.id,
        bank_id=test_bank.id,
        balance=0,
    )

    db_session.add(saving)
    db_session.commit()

    transaction = SavingTransaction(
        saving_id=saving.id,
        user_id=test_user.id,
        amount=100,
        description="Historical transaction",
        category="Savings",
        transaction_type="withdrawal",
        saving_balance_after=0,
    )

    db_session.add(transaction)
    db_session.commit()

    saving_id = saving.id
    transaction_id = transaction.id

    response = authenticated_client.delete(
        f"/savings/{saving_id}"
    )

    # Desired behavior:
    # A zero-balance saving can be deleted, and its own
    # transaction history should not leave orphaned records.
    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "Saving account deleted successfully"
    )

    deleted_saving = db_session.get(
        Saving,
        saving_id,
    )

    deleted_transaction = db_session.get(
        SavingTransaction,
        transaction_id,
    )

    assert deleted_saving is None
    assert deleted_transaction is None