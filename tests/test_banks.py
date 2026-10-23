from datetime import datetime

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

    assert data["total"] == 1
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total_pages"] == 1
    assert len(data["transactions"]) == 1

    transaction = data["transactions"][0]

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

    assert data["transactions"] == []
    assert data["page"] == 1
    assert data["page_size"] == 25
    assert data["total"] == 0
    assert data["total_pages"] == 0


def test_get_bank_transactions_supports_pagination_and_search(
    authenticated_client,
    test_bank,
):
    for index in range(30):
        response = authenticated_client.post(
            f"/banks/{test_bank.id}/transactions",
            json={
                "amount": 100 + index,
                "type": "expense" if index % 2 else "income",
                "description": f"Transaction {index}",
                "category": "Groceries" if index == 23 else "Other",
            },
        )
        assert response.status_code == 201

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?page=2&page_size=10"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["page"] == 2
    assert data["page_size"] == 10
    assert data["total"] == 30
    assert data["total_pages"] == 3
    assert len(data["transactions"]) == 10

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?search=Groceries&page_size=25"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert data["transactions"][0]["category"] == "Groceries"

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?type=income&page_size=100"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 15
    assert all(
        transaction["transaction_type"] == "income"
        for transaction in data["transactions"]
    )


def test_bank_transaction_text_search_only_matches_description_and_category(
    authenticated_client,
    test_bank,
    db_session,
):
    db_session.add_all([
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=42.5,
            date=datetime(2026, 10, 10, 12, 0, 0),
            description="Lunch purchase",
            category="Dining",
            transaction_type="expense",
            bank_balance_after=9957.5,
        ),
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=500,
            date=datetime(2026, 10, 11, 12, 0, 0),
            description="Monthly deposit",
            category="Salary",
            transaction_type="income",
            bank_balance_after=10500,
        ),
    ])
    db_session.commit()

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?search=lUnCh"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 1
    assert data["transactions"][0]["description"] == "Lunch purchase"

    # The search box no longer searches transaction_type, amount, date, or
    # balance-after text. Those are handled by dedicated filters or are not
    # part of the text-search contract.
    for term in ("expense", "42.5", "2026-10-10", "9957.5"):
        response = authenticated_client.get(
            f"/banks/{test_bank.id}/transactions?search={term}"
        )
        assert response.status_code == 200
        assert response.get_json()["total"] == 0


def test_bank_transaction_amount_ranges_use_non_overlapping_boundaries(
    authenticated_client,
    test_bank,
    db_session,
):
    amounts = [
        100,
        499.99,
        500,
        999.99,
        1000,
        4999.99,
        5000,
        9999.99,
        10000,
        15000,
    ]
    db_session.add_all([
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=amount,
            date=datetime(2026, 10, 1, 12, 0, index),
            description=f"Amount test {amount}",
            category="Test",
            transaction_type="income",
            bank_balance_after=10000 + amount,
        )
        for index, amount in enumerate(amounts)
    ])
    db_session.commit()

    expected_by_range = {
        "under_500": [100, 499.99],
        "500_1000": [500, 999.99],
        "1000_5000": [1000, 4999.99],
        "5000_10000": [5000, 9999.99],
        "10000_plus": [10000, 15000],
    }

    for amount_range, expected_amounts in expected_by_range.items():
        response = authenticated_client.get(
            f"/banks/{test_bank.id}/transactions?amount_range={amount_range}"
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["total"] == len(expected_amounts)
        assert sorted(tx["amount"] for tx in data["transactions"]) == expected_amounts


def test_bank_transaction_ist_date_range_uses_inclusive_calendar_dates(
    authenticated_client,
    test_bank,
    db_session,
):
    # Stored timestamps are naive UTC by application convention. On IST,
    # these represent Sep 30 23:59:59.999999, Oct 1 00:00, Oct 31
    # 23:59:59.999999 and Nov 1 00:00 respectively.
    transaction_rows = [
        ("before start", datetime(2026, 9, 30, 18, 29, 59, 999999)),
        ("start boundary", datetime(2026, 9, 30, 18, 30, 0)),
        ("end boundary", datetime(2026, 10, 31, 18, 29, 59, 999999)),
        ("after end", datetime(2026, 10, 31, 18, 30, 0)),
    ]
    db_session.add_all([
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=100 + index,
            date=stored_utc,
            description=description,
            category="Date test",
            transaction_type="income",
            bank_balance_after=10100 + index,
        )
        for index, (description, stored_utc) in enumerate(transaction_rows)
    ])
    db_session.commit()

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions"
        "?start_date=2026-10-01&end_date=2026-10-31"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["total"] == 2
    assert {tx["description"] for tx in data["transactions"]} == {
        "start boundary",
        "end boundary",
    }


def test_bank_transaction_filters_reject_invalid_date_and_amount_values(
    authenticated_client,
    test_bank,
):
    invalid_date = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?start_date=2026-02-30"
    )
    assert invalid_date.status_code == 400
    assert invalid_date.get_json()["error"] == "Dates must use YYYY-MM-DD format"

    reversed_dates = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions"
        "?start_date=2026-10-31&end_date=2026-10-01"
    )
    assert reversed_dates.status_code == 400
    assert reversed_dates.get_json()["error"] == "Start date must be on or before end date"

    invalid_amount_range = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?amount_range=unknown"
    )
    assert invalid_amount_range.status_code == 400
    assert invalid_amount_range.get_json()["error"] == "Invalid amount range filter"


def test_get_bank_transactions_rejects_invalid_type_filter(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?type=transfer"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Invalid transaction type filter"


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