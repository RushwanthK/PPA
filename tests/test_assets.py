from app.models import (
    Asset,
    AssetTransaction,
)


VALID_CATEGORIES = [
    "ETF",
    "FD",
    "Mutual Funds",
    "Other",
    "Provident Fund",
    "Stocks",
]


# ============================================================
# GET /assets
# ============================================================

def test_get_assets_returns_user_assets(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.get(
        "/assets"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    asset = data[0]

    assert asset["id"] == test_asset.id
    assert asset["name"] == test_asset.name
    assert asset["user_id"] == test_asset.user_id
    assert asset["platform"] == test_asset.platform
    assert asset["category"] == test_asset.category
    assert asset["balance"] == test_asset.balance


def test_get_assets_returns_empty_list_when_user_has_no_assets(
    authenticated_client,
):
    response = authenticated_client.get(
        "/assets"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data == []


def test_get_assets_requires_authentication(
    client,
):
    response = client.get(
        "/assets"
    )

    assert response.status_code == 401


def test_get_assets_does_not_return_other_users_assets(
    authenticated_client,
    other_user,
    db_session,
):
    other_asset = Asset(
        name="Other User Asset",
        user_id=other_user.id,
        platform="Other Platform",
        category="Stocks",
        balance=5000,
    )

    db_session.add(other_asset)
    db_session.commit()

    try:
        response = authenticated_client.get(
            "/assets"
        )

        assert response.status_code == 200

        data = response.get_json()

        assert data == []

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        if existing_asset is not None:
            db_session.delete(
                existing_asset
            )

            db_session.commit()


# ============================================================
# CREATE /assets
# ============================================================

def test_create_asset_success(
    authenticated_client,
    test_user,
    db_session,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "New Test Asset",
            "platform": "Groww",
            "category": "Mutual Funds",
            "balance": 5000,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Asset created!"
    )

    assert "asset" in data

    asset_data = data["asset"]

    assert asset_data["id"] is not None
    assert asset_data["name"] == (
        "New Test Asset"
    )
    assert asset_data["user_id"] == (
        test_user.id
    )
    assert asset_data["platform"] == "Groww"
    assert asset_data["category"] == (
        "Mutual Funds"
    )
    assert asset_data["balance"] == 5000

    created_asset = db_session.get(
        Asset,
        asset_data["id"],
    )

    assert created_asset is not None
    assert created_asset.name == (
        "New Test Asset"
    )
    assert created_asset.user_id == (
        test_user.id
    )
    assert created_asset.platform == "Groww"
    assert created_asset.category == (
        "Mutual Funds"
    )
    assert created_asset.balance == 5000

    db_session.delete(
        created_asset
    )
    db_session.commit()


def test_create_asset_uses_default_zero_balance(
    authenticated_client,
    db_session,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Zero Balance Asset",
            "category": "Stocks",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["asset"]["balance"] == 0

    created_asset = db_session.get(
        Asset,
        data["asset"]["id"],
    )

    assert created_asset.balance == 0

    db_session.delete(
        created_asset
    )
    db_session.commit()


def test_create_asset_allows_zero_balance(
    authenticated_client,
    db_session,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Explicit Zero Asset",
            "category": "ETF",
            "balance": 0,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["asset"]["balance"] == 0

    created_asset = db_session.get(
        Asset,
        data["asset"]["id"],
    )

    assert created_asset is not None

    db_session.delete(
        created_asset
    )
    db_session.commit()


def test_create_asset_requires_authentication(
    client,
):
    response = client.post(
        "/assets",
        json={
            "name": "Unauthorized Asset",
            "category": "Stocks",
            "balance": 1000,
        },
    )

    assert response.status_code == 401


def test_create_asset_requires_name(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "category": "Stocks",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name is required"
    )


def test_create_asset_rejects_blank_name(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "   ",
            "category": "Stocks",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name is required"
    )


def test_create_asset_rejects_empty_name(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "",
            "category": "Stocks",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name is required"
    )


def test_create_asset_rejects_missing_json_body(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name is required"
    )


def test_create_asset_strips_name_whitespace(
    authenticated_client,
    db_session,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "   Retirement Fund   ",
            "category": "Provident Fund",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["asset"]["name"] == (
        "Retirement Fund"
    )

    created_asset = db_session.get(
        Asset,
        data["asset"]["id"],
    )

    assert created_asset.name == (
        "Retirement Fund"
    )

    db_session.delete(
        created_asset
    )
    db_session.commit()


def test_create_asset_requires_category(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "No Category Asset",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Category is required"
    )


def test_create_asset_rejects_null_category(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Null Category Asset",
            "category": None,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Category is required"
    )


def test_create_asset_rejects_invalid_category(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Invalid Category Asset",
            "category": "Crypto",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Invalid category. "
        "Allowed values: "
        "ETF, FD, Mutual Funds, Other, "
        "Provident Fund, Stocks"
    )


def test_create_asset_accepts_all_valid_categories(
    authenticated_client,
    db_session,
):
    for index, category in enumerate(
        VALID_CATEGORIES
    ):
        response = authenticated_client.post(
            "/assets",
            json={
                "name": (
                    f"Category Asset {index}"
                ),
                "category": category,
            },
        )

        assert response.status_code == 201

        data = response.get_json()

        assert data["asset"]["category"] == (
            category
        )

        created_asset = db_session.get(
            Asset,
            data["asset"]["id"],
        )

        assert created_asset.category == (
            category
        )

        db_session.delete(
            created_asset
        )

        db_session.commit()


def test_create_asset_rejects_invalid_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Invalid Balance Asset",
            "category": "Stocks",
            "balance": "abc",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset balance must be a valid number"
    )


def test_create_asset_rejects_negative_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Negative Balance Asset",
            "category": "Stocks",
            "balance": -100,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset balance cannot be negative"
    )


def test_create_asset_rejects_nan_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "NaN Balance Asset",
            "category": "Stocks",
            "balance": "NaN",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset balance must be a valid number"
    )


def test_create_asset_rejects_infinite_balance(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": "Infinite Balance Asset",
            "category": "Stocks",
            "balance": "Infinity",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset balance must be a valid number"
    )


def test_create_asset_rejects_duplicate_name(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        "/assets",
        json={
            "name": test_asset.name,
            "category": "Stocks",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name already exists"
    )


# ============================================================
# UPDATE /assets/<id>
# ============================================================

def test_update_asset_success(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "name": "Updated Asset",
            "platform": "Updated Platform",
            "category": "Stocks",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "Asset updated successfully"
    )

    assert data["asset"]["id"] == (
        test_asset.id
    )

    assert data["asset"]["name"] == (
        "Updated Asset"
    )

    assert data["asset"]["platform"] == (
        "Updated Platform"
    )

    assert data["asset"]["category"] == (
        "Stocks"
    )

    assert data["asset"]["balance"] == 10000


def test_update_asset_requires_authentication(
    client,
    test_asset,
):
    response = client.put(
        f"/assets/{test_asset.id}",
        json={
            "name": "Unauthorized Update",
        },
    )

    assert response.status_code == 401


def test_update_nonexistent_asset(
    authenticated_client,
):
    response = authenticated_client.put(
        "/assets/999999",
        json={
            "name": "Updated Asset",
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == (
        "Asset not found"
    )


def test_update_asset_rejects_other_users_asset(
    authenticated_client,
    other_user,
    db_session,
):
    other_asset = Asset(
        name="Other User Update Asset",
        user_id=other_user.id,
        category="Stocks",
        balance=5000,
    )

    db_session.add(other_asset)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/assets/{other_asset.id}",
            json={
                "name": "Unauthorized Update",
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == (
            "Asset not found"
        )

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        assert existing_asset.name == (
            "Other User Update Asset"
        )

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        if existing_asset is not None:
            db_session.delete(
                existing_asset
            )

            db_session.commit()


def test_update_asset_rejects_blank_name(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "name": "   ",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name is required"
    )


def test_update_asset_rejects_empty_name(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "name": "",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset name is required"
    )


def test_update_asset_strips_name_whitespace(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "name": "   Updated Asset   ",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["asset"]["name"] == (
        "Updated Asset"
    )


def test_update_asset_rejects_invalid_category(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "category": "Crypto",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Invalid category. "
        "Allowed values: "
        "ETF, FD, Mutual Funds, Other, "
        "Provident Fund, Stocks"
    )


def test_update_asset_rejects_missing_category_value(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "category": None,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Category is required"
    )


def test_update_asset_rejects_balance_change(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "balance": 50000,
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Balance cannot be updated directly. "
        "Use transactions instead."
    )


def test_update_asset_balance_rejection_does_not_change_asset(
    authenticated_client,
    test_asset,
    db_session,
):
    response = authenticated_client.put(
        f"/assets/{test_asset.id}",
        json={
            "name": "Should Not Persist",
            "balance": 50000,
        },
    )

    assert response.status_code == 400

    db_session.expire_all()

    asset = db_session.get(
        Asset,
        test_asset.id,
    )

    assert asset.name == "Test Asset"
    assert asset.balance == 10000


def test_update_asset_rejects_duplicate_name(
    authenticated_client,
    test_asset,
    db_session,
):
    second_asset = Asset(
        name="Second Asset",
        user_id=test_asset.user_id,
        category="Stocks",
        balance=0,
    )

    db_session.add(second_asset)
    db_session.commit()

    try:
        response = authenticated_client.put(
            f"/assets/{test_asset.id}",
            json={
                "name": second_asset.name,
            },
        )

        assert response.status_code == 400

        data = response.get_json()

        assert data["error"] == (
            "Asset name already exists"
        )

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            second_asset.id,
        )

        if existing_asset is not None:
            db_session.delete(
                existing_asset
            )

            db_session.commit()


# ============================================================
# POST /assets/<id>/transactions
# ============================================================

def test_add_asset_deposit_success(
    authenticated_client,
    test_asset,
    db_session,
):
    starting_balance = test_asset.balance

    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
            "description": "Investment",
            "category": "Mutual Funds",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Transaction added"
    )

    assert data["balance"] == (
        starting_balance + 1000
    )

    db_session.expire_all()

    asset = db_session.get(
        Asset,
        test_asset.id,
    )

    assert asset.balance == (
        starting_balance + 1000
    )

    transaction = (
        db_session.query(
            AssetTransaction
        )
        .filter_by(
            asset_id=test_asset.id
        )
        .one()
    )

    assert transaction.user_id == (
        test_asset.user_id
    )

    assert transaction.amount == 1000
    assert transaction.transaction_type == (
        "deposit"
    )

    assert transaction.description == (
        "Investment"
    )

    assert transaction.category == (
        "Mutual Funds"
    )

    assert transaction.asset_balance_after == (
        starting_balance + 1000
    )


def test_add_asset_withdrawal_success(
    authenticated_client,
    test_asset,
    db_session,
):
    starting_balance = test_asset.balance

    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 2500,
            "type": "withdraw",
            "description": "Partial Withdrawal",
            "category": "Other",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Transaction added"
    )

    assert data["balance"] == (
        starting_balance - 2500
    )

    db_session.expire_all()

    asset = db_session.get(
        Asset,
        test_asset.id,
    )

    assert asset.balance == (
        starting_balance - 2500
    )

    transaction = (
        db_session.query(
            AssetTransaction
        )
        .filter_by(
            asset_id=test_asset.id
        )
        .one()
    )

    assert transaction.transaction_type == (
        "withdraw"
    )

    assert transaction.asset_balance_after == (
        starting_balance - 2500
    )


def test_add_asset_transaction_defaults_to_deposit(
    authenticated_client,
    test_asset,
    db_session,
):
    starting_balance = test_asset.balance

    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 500,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Transaction added"
    )

    assert data["balance"] == (
        starting_balance + 500
    )

    transaction = (
        db_session.query(
            AssetTransaction
        )
        .filter_by(
            asset_id=test_asset.id
        )
        .one()
    )

    assert transaction.transaction_type == (
        "deposit"
    )


def test_add_asset_transaction_exact_withdrawal_balance(
    authenticated_client,
    test_asset,
):
    amount = test_asset.balance

    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": amount,
            "type": "withdraw",
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == (
        "Transaction added"
    )

    assert data["balance"] == 0


def test_add_asset_transaction_requires_authentication(
    client,
    test_asset,
):
    response = client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
        },
    )

    assert response.status_code == 401


def test_add_asset_transaction_nonexistent_asset(
    authenticated_client,
):
    response = authenticated_client.post(
        "/assets/999999/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
        },
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == (
        "Asset not found"
    )


def test_other_user_cannot_add_asset_transaction(
    authenticated_client,
    other_user,
    db_session,
):
    other_asset = Asset(
        name="Other User Transaction Asset",
        user_id=other_user.id,
        category="Stocks",
        balance=5000,
    )

    db_session.add(other_asset)
    db_session.commit()

    try:
        response = authenticated_client.post(
            f"/assets/{other_asset.id}/transactions",
            json={
                "amount": 1000,
                "type": "deposit",
            },
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == (
            "Asset not found"
        )

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        if existing_asset is not None:
            db_session.delete(
                existing_asset
            )

            db_session.commit()


def test_add_asset_transaction_requires_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount is required"
    )


def test_add_asset_transaction_rejects_null_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": None,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be a valid number"
    )


def test_add_asset_transaction_rejects_invalid_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": "abc",
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be a valid number"
    )


def test_add_asset_transaction_rejects_zero_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 0,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be greater than 0"
    )


def test_add_asset_transaction_rejects_negative_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": -100,
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be greater than 0"
    )


def test_add_asset_transaction_rejects_nan_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": "NaN",
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be a valid number"
    )


def test_add_asset_transaction_rejects_infinite_amount(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": "Infinity",
            "type": "deposit",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Amount must be a valid number"
    )


def test_add_asset_transaction_rejects_invalid_type(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 1000,
            "type": "transfer",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Invalid transaction type"
    )


def test_add_asset_withdrawal_rejects_insufficient_balance(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": test_asset.balance + 1,
            "type": "withdraw",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Insufficient balance"
    )


def test_failed_asset_withdrawal_does_not_change_balance(
    authenticated_client,
    test_asset,
    db_session,
):
    starting_balance = test_asset.balance

    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": starting_balance + 1,
            "type": "withdraw",
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Insufficient balance"
    )

    db_session.expire_all()

    asset = db_session.get(
        Asset,
        test_asset.id,
    )

    assert asset.balance == (
        starting_balance
    )

    transaction_count = (
        db_session.query(
            AssetTransaction
        )
        .filter_by(
            asset_id=test_asset.id
        )
        .count()
    )

    assert transaction_count == 0


def test_invalid_asset_transaction_does_not_change_balance(
    authenticated_client,
    test_asset,
    db_session,
):
    starting_balance = test_asset.balance

    response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 1000,
            "type": "invalid",
        },
    )

    assert response.status_code == 400

    db_session.expire_all()

    asset = db_session.get(
        Asset,
        test_asset.id,
    )

    assert asset.balance == (
        starting_balance
    )

    transaction_count = (
        db_session.query(
            AssetTransaction
        )
        .filter_by(
            asset_id=test_asset.id
        )
        .count()
    )

    assert transaction_count == 0


# ============================================================
# GET /assets/<id>/transactions
# ============================================================

def test_get_asset_transactions_empty(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.get(
        f"/assets/{test_asset.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data == []


def test_get_asset_transactions_returns_history(
    authenticated_client,
    test_asset,
):
    create_response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
            "description": "Monthly Investment",
            "category": "Mutual Funds",
        },
    )

    assert create_response.status_code == 201

    response = authenticated_client.get(
        f"/assets/{test_asset.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    transaction = data[0]

    assert transaction["amount"] == 1000

    assert transaction["description"] == (
        "Monthly Investment"
    )

    assert transaction["category"] == (
        "Mutual Funds"
    )

    assert transaction["transaction_type"] == (
        "deposit"
    )

    assert transaction["asset_balance_after"] == (
        11000
    )

    assert transaction["id"] is not None
    assert transaction["date"] is not None


def test_get_asset_transactions_uses_empty_strings_for_missing_optional_fields(
    authenticated_client,
    test_asset,
):
    create_response = authenticated_client.post(
        f"/assets/{test_asset.id}/transactions",
        json={
            "amount": 1000,
            "type": "deposit",
        },
    )

    assert create_response.status_code == 201

    response = authenticated_client.get(
        f"/assets/{test_asset.id}/transactions"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert len(data) == 1

    transaction = data[0]

    assert transaction["description"] == ""
    assert transaction["category"] == ""


def test_get_asset_transactions_requires_authentication(
    client,
    test_asset,
):
    response = client.get(
        f"/assets/{test_asset.id}/transactions"
    )

    assert response.status_code == 401


def test_get_asset_transactions_nonexistent_asset(
    authenticated_client,
):
    response = authenticated_client.get(
        "/assets/999999/transactions"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == (
        "Asset not found"
    )


def test_other_user_cannot_get_asset_transactions(
    authenticated_client,
    other_user,
    db_session,
):
    other_asset = Asset(
        name="Other User History Asset",
        user_id=other_user.id,
        category="Stocks",
        balance=5000,
    )

    db_session.add(other_asset)
    db_session.commit()

    try:
        response = authenticated_client.get(
            f"/assets/{other_asset.id}/transactions"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == (
            "Asset not found"
        )

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        if existing_asset is not None:
            db_session.delete(
                existing_asset
            )

            db_session.commit()


# ============================================================
# DELETE /assets/<id>
# ============================================================

def test_delete_asset_requires_authentication(
    client,
    test_asset,
):
    response = client.delete(
        f"/assets/{test_asset.id}"
    )

    assert response.status_code == 401


def test_delete_nonexistent_asset(
    authenticated_client,
):
    response = authenticated_client.delete(
        "/assets/999999"
    )

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == (
        "Asset not found"
    )


def test_delete_asset_rejects_non_zero_balance(
    authenticated_client,
    test_asset,
):
    response = authenticated_client.delete(
        f"/assets/{test_asset.id}"
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Asset cannot be deleted because "
        "its balance is not zero."
    )


def test_delete_asset_does_not_delete_non_zero_balance(
    authenticated_client,
    test_asset,
    db_session,
):
    response = authenticated_client.delete(
        f"/assets/{test_asset.id}"
    )

    assert response.status_code == 400

    asset = db_session.get(
        Asset,
        test_asset.id,
    )

    assert asset is not None
    assert asset.balance == 10000


def test_delete_asset_success(
    authenticated_client,
    test_user,
    db_session,
):
    asset = Asset(
        name="Delete Me Asset",
        user_id=test_user.id,
        platform="Delete Platform",
        category="Other",
        balance=0,
    )

    db_session.add(asset)
    db_session.commit()

    asset_id = asset.id

    response = authenticated_client.delete(
        f"/assets/{asset_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "Asset deleted successfully"
    )

    deleted_asset = db_session.get(
        Asset,
        asset_id,
    )

    assert deleted_asset is None


def test_other_user_cannot_delete_asset(
    authenticated_client,
    other_user,
    db_session,
):
    other_asset = Asset(
        name="Other User Delete Asset",
        user_id=other_user.id,
        category="Stocks",
        balance=0,
    )

    db_session.add(other_asset)
    db_session.commit()

    try:
        response = authenticated_client.delete(
            f"/assets/{other_asset.id}"
        )

        assert response.status_code == 404

        data = response.get_json()

        assert data["error"] == (
            "Asset not found"
        )

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        assert existing_asset is not None

    finally:
        db_session.rollback()

        existing_asset = db_session.get(
            Asset,
            other_asset.id,
        )

        if existing_asset is not None:
            db_session.delete(
                existing_asset
            )

            db_session.commit()


def test_delete_zero_balance_asset_with_transaction_history(
    authenticated_client,
    test_user,
    db_session,
):
    asset = Asset(
        name="History Delete Asset",
        user_id=test_user.id,
        category="Stocks",
        balance=0,
    )

    db_session.add(asset)
    db_session.commit()

    transaction = AssetTransaction(
        asset_id=asset.id,
        user_id=test_user.id,
        amount=100,
        description="Historical transaction",
        category="Stocks",
        transaction_type="withdraw",
        asset_balance_after=0,
    )

    db_session.add(transaction)
    db_session.commit()

    asset_id = asset.id
    transaction_id = transaction.id

    response = authenticated_client.delete(
        f"/assets/{asset_id}"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["message"] == (
        "Asset deleted successfully"
    )

    deleted_asset = db_session.get(
        Asset,
        asset_id,
    )

    deleted_transaction = db_session.get(
        AssetTransaction,
        transaction_id,
    )

    assert deleted_asset is None
    assert deleted_transaction is None


def test_delete_non_zero_asset_preserves_transaction_history(
    authenticated_client,
    test_asset,
    db_session,
):
    transaction = AssetTransaction(
        asset_id=test_asset.id,
        user_id=test_asset.user_id,
        amount=1000,
        description="Existing history",
        category="Stocks",
        transaction_type="deposit",
        asset_balance_after=11000,
    )

    db_session.add(transaction)
    db_session.commit()

    response = authenticated_client.delete(
        f"/assets/{test_asset.id}"
    )

    assert response.status_code == 400

    existing_asset = db_session.get(
        Asset,
        test_asset.id,
    )

    existing_transaction = db_session.get(
        AssetTransaction,
        transaction.id,
    )

    assert existing_asset is not None
    assert existing_asset.balance == 10000
    assert existing_transaction is not None