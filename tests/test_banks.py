from datetime import datetime, timedelta

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

    assert data["page_size"] == 25
    assert data["has_more"] is False
    assert data["next_cursor"] is None
    assert len(data["transactions"]) == 1
    assert "total" not in data
    assert "total_pages" not in data

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
    assert data["page_size"] == 25
    assert data["has_more"] is False
    assert data["next_cursor"] is None


def test_get_bank_transactions_supports_cursor_pagination_and_search(
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

    first_response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?page_size=10"
    )
    assert first_response.status_code == 200
    first_page = first_response.get_json()
    assert first_page["page_size"] == 10
    assert first_page["has_more"] is True
    assert first_page["next_cursor"]
    assert len(first_page["transactions"]) == 10

    second_response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions",
        query_string={
            "page_size": 10,
            "cursor": first_page["next_cursor"],
        },
    )
    assert second_response.status_code == 200
    second_page = second_response.get_json()
    assert second_page["has_more"] is True
    assert second_page["next_cursor"]
    assert len(second_page["transactions"]) == 10

    third_response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions",
        query_string={
            "page_size": 10,
            "cursor": second_page["next_cursor"],
        },
    )
    assert third_response.status_code == 200
    third_page = third_response.get_json()
    assert third_page["has_more"] is False
    assert third_page["next_cursor"] is None
    assert len(third_page["transactions"]) == 10

    all_ids = [
        tx["id"]
        for page in (first_page, second_page, third_page)
        for tx in page["transactions"]
    ]
    assert len(all_ids) == 30
    assert len(set(all_ids)) == 30

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?search=Groceries&page_size=25"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["transactions"]) == 1
    assert data["has_more"] is False
    assert data["transactions"][0]["category"] == "Groceries"

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?type=income&page_size=100"
    )
    assert response.status_code == 200
    data = response.get_json()
    assert len(data["transactions"]) == 15
    assert data["has_more"] is False
    assert all(
        transaction["transaction_type"] == "income"
        for transaction in data["transactions"]
    )


def test_bank_transaction_cursor_handles_identical_timestamps(
    authenticated_client,
    test_bank,
    db_session,
):
    same_timestamp = datetime(2026, 10, 20, 12, 0, 0, 123456)
    rows = [
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=100 + index,
            date=same_timestamp,
            description=f"Same timestamp {index}",
            category="Cursor test",
            transaction_type="income",
            bank_balance_after=10000 + index,
        )
        for index in range(5)
    ]
    db_session.add_all(rows)
    db_session.commit()
    expected_ids = sorted((row.id for row in rows), reverse=True)

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?page_size=2"
    )
    assert response.status_code == 200
    page_data = response.get_json()
    collected_ids = [tx["id"] for tx in page_data["transactions"]]
    assert collected_ids == expected_ids[:2]
    assert page_data["has_more"] is True

    while page_data["has_more"]:
        response = authenticated_client.get(
            f"/banks/{test_bank.id}/transactions",
            query_string={
                "page_size": 2,
                "cursor": page_data["next_cursor"],
            },
        )
        assert response.status_code == 200
        page_data = response.get_json()
        collected_ids.extend(tx["id"] for tx in page_data["transactions"])

    assert collected_ids == expected_ids
    assert len(collected_ids) == len(set(collected_ids))
    assert page_data["has_more"] is False
    assert page_data["next_cursor"] is None


def test_bank_transaction_cursor_is_bound_to_filters_and_page_size(
    authenticated_client,
    test_bank,
    db_session,
):
    rows = [
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=100 + index,
            date=datetime(2026, 10, 20, 12, index, 0),
            description=f"Food purchase {index}",
            category="Groceries",
            transaction_type="expense",
            bank_balance_after=9000 - index,
        )
        for index in range(3)
    ]
    db_session.add_all(rows)
    db_session.add(BankTransaction(
        user_id=test_bank.user_id,
        bank_id=test_bank.id,
        amount=250,
        date=datetime(2026, 10, 19, 12, 0, 0),
        description="Travel purchase",
        category="Travel",
        transaction_type="expense",
        bank_balance_after=8750,
    ))
    db_session.commit()

    first = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?search=Food&page_size=1"
    )
    assert first.status_code == 200
    cursor = first.get_json()["next_cursor"]
    assert cursor

    changed_filter_cases = [
        {"search": "Travel", "page_size": 1},
        {"search": "Food", "page_size": 2},
        {"search": "Food", "page_size": 1, "type": "income"},
        {"search": "Food", "page_size": 1, "start_date": "2026-10-21"},
        {"search": "Food", "page_size": 1, "end_date": "2026-10-19"},
        {"search": "Food", "page_size": 1, "amount_range": "under_500"},
    ]
    for changed_filters in changed_filter_cases:
        changed_filters["cursor"] = cursor
        response = authenticated_client.get(
            f"/banks/{test_bank.id}/transactions",
            query_string=changed_filters,
        )
        assert response.status_code == 400
        assert "current filters" in response.get_json()["error"]


def test_bank_transaction_cursor_excludes_newer_inserted_rows_from_next_page(
    authenticated_client,
    test_bank,
    db_session,
):
    base_time = datetime(2026, 10, 1, 12, 0, 0)
    db_session.add_all([
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=100 + index,
            date=base_time + timedelta(minutes=index),
            description=f"Existing transaction {index}",
            category="Cursor insert test",
            transaction_type="income",
            bank_balance_after=10000 + index,
        )
        for index in range(5)
    ])
    db_session.commit()

    first = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?page_size=2"
    )
    assert first.status_code == 200
    first_data = first.get_json()
    first_ids = [tx["id"] for tx in first_data["transactions"]]
    cursor = first_data["next_cursor"]
    assert cursor

    # A new row newer than the current cursor must not shift the next page.
    db_session.add(BankTransaction(
        user_id=test_bank.user_id,
        bank_id=test_bank.id,
        amount=999,
        date=base_time + timedelta(days=1),
        description="New transaction after first page",
        category="Cursor insert test",
        transaction_type="income",
        bank_balance_after=11000,
    ))
    db_session.commit()

    second = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions",
        query_string={"page_size": 2, "cursor": cursor},
    )
    assert second.status_code == 200
    second_data = second.get_json()
    second_ids = [tx["id"] for tx in second_data["transactions"]]

    assert not set(first_ids).intersection(second_ids)
    assert "New transaction after first page" not in {
        tx["description"] for tx in second_data["transactions"]
    }
    assert [tx["description"] for tx in second_data["transactions"]] == [
        "Existing transaction 2",
        "Existing transaction 1",
    ]
    assert second_data["has_more"] is True


def test_bank_transaction_cursor_preserves_combined_filters_across_pages(
    authenticated_client,
    test_bank,
    db_session,
):
    eligible_rows = [
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=600 + index,
            date=datetime(2026, 10, 10, 12, index, 0),
            description=f"Coffee purchase {index}",
            category="Groceries",
            transaction_type="expense",
            bank_balance_after=9000 - index,
        )
        for index in range(3)
    ]
    ineligible_rows = [
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=200,
            date=datetime(2026, 10, 10, 13, 0, 0),
            description="Coffee purchase low amount",
            category="Groceries",
            transaction_type="expense",
            bank_balance_after=8800,
        ),
        BankTransaction(
            user_id=test_bank.user_id,
            bank_id=test_bank.id,
            amount=700,
            date=datetime(2026, 10, 10, 14, 0, 0),
            description="Coffee income",
            category="Groceries",
            transaction_type="income",
            bank_balance_after=9500,
        ),
    ]
    db_session.add_all(eligible_rows + ineligible_rows)
    db_session.commit()

    filters = {
        "search": "Coffee",
        "type": "expense",
        "start_date": "2026-10-10",
        "end_date": "2026-10-10",
        "amount_range": "500_1000",
        "page_size": 1,
    }
    first = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions",
        query_string=filters,
    )
    assert first.status_code == 200
    first_data = first.get_json()
    assert len(first_data["transactions"]) == 1
    assert first_data["has_more"] is True

    second = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions",
        query_string={**filters, "cursor": first_data["next_cursor"]},
    )
    assert second.status_code == 200
    second_data = second.get_json()
    assert len(second_data["transactions"]) == 1
    assert second_data["transactions"][0]["transaction_type"] == "expense"
    assert 500 <= second_data["transactions"][0]["amount"] < 1000
    assert second_data["has_more"] is True


def test_bank_transaction_cursor_rejects_malformed_cursor(
    authenticated_client,
    test_bank,
):
    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?cursor=not-a-valid-cursor"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Invalid transaction cursor; restart from the first page"
    )


def test_bank_transaction_endpoint_keeps_legacy_page_api_during_rollout(
    authenticated_client,
    test_bank,
):
    for index in range(3):
        response = authenticated_client.post(
            f"/banks/{test_bank.id}/transactions",
            json={
                "amount": 100 + index,
                "type": "income",
                "description": f"Legacy page {index}",
                "category": "Compatibility",
            },
        )
        assert response.status_code == 201

    response = authenticated_client.get(
        f"/banks/{test_bank.id}/transactions?page=2&page_size=2"
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["page"] == 2
    assert data["page_size"] == 2
    assert data["total"] == 3
    assert data["total_pages"] == 2
    assert len(data["transactions"]) == 1


def test_bank_transaction_page_does_not_run_an_exact_count_query(
    authenticated_client,
    test_bank,
    app,
):
    from sqlalchemy import event
    from app import db

    captured_statements = []

    def capture_statement(connection, cursor, statement, parameters, context, executemany):
        captured_statements.append(statement.lower())

    # Resolve the fixture's bank ID before installing the SQL listener.
    # The fixture's ORM object may have expired after commit, and accessing
    # its ID can itself trigger a SELECT that is unrelated to the API request.
    bank_id = test_bank.id

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", capture_statement)
        try:
            response = authenticated_client.get(
                f"/banks/{bank_id}/transactions?page_size=25"
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", capture_statement)

    assert response.status_code == 200
    select_statements = [
        statement for statement in captured_statements
        if statement.lstrip().startswith("select")
    ]
    assert len(select_statements) == 2  # bank ownership + one page query
    assert not any("count(" in statement for statement in select_statements)


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
    assert len(data["transactions"]) == 1
    assert data["has_more"] is False
    assert data["transactions"][0]["description"] == "Lunch purchase"

    # The search box no longer searches transaction_type, amount, date, or
    # balance-after text. Those are handled by dedicated filters or are not
    # part of the text-search contract.
    for term in ("expense", "42.5", "2026-10-10", "9957.5"):
        response = authenticated_client.get(
            f"/banks/{test_bank.id}/transactions?search={term}"
        )
        assert response.status_code == 200
        assert response.get_json()["transactions"] == []
        assert response.get_json()["has_more"] is False


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
        assert len(data["transactions"]) == len(expected_amounts)
        assert data["has_more"] is False
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
    assert len(data["transactions"]) == 2
    assert data["has_more"] is False
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