from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    Asset,
    AssetTransaction,
    BankTransaction,
    CreditCardTransaction,
    SavingTransaction,
)


# ============================================================
# GET /dashboard/summary
# ============================================================


def test_dashboard_summary_requires_authentication(client):
    response = client.get("/dashboard/summary")

    assert response.status_code == 401


def test_dashboard_summary_returns_zero_values_for_new_user(
    authenticated_client,
):
    response = authenticated_client.get("/dashboard/summary")

    assert response.status_code == 200

    data = response.get_json()

    assert data == {
        "total_assets": 0.0,
        "total_bank_balance": 0.0,
        "total_savings": 0.0,
        "total_credit_card_debt": 0.0,
        "net_worth": 0.0,
    }


def test_dashboard_summary_returns_correct_financial_totals(
    authenticated_client,
    test_bank,
    test_saving,
    test_asset,
    test_credit_card,
):
    test_credit_card.used = 2500

    response = authenticated_client.get("/dashboard/summary")

    assert response.status_code == 200

    data = response.get_json()

    assert data["total_assets"] == 10000.0
    assert data["total_bank_balance"] == 10000.0
    assert data["total_savings"] == 5000.0
    assert data["total_credit_card_debt"] == 2500.0
    assert data["net_worth"] == 22500.0


def test_dashboard_summary_aggregates_multiple_accounts(
    authenticated_client,
    test_bank,
    test_saving,
    test_asset,
    test_credit_card,
    db_session,
):
    second_bank = type(test_bank)(
        name="Dashboard Second Bank",
        user_id=test_bank.user_id,
        balance=3500,
    )

    second_asset = type(test_asset)(
        name="Dashboard Second Asset",
        user_id=test_asset.user_id,
        platform="Dashboard Test Platform",
        category="Stocks",
        balance=7500,
    )

    test_credit_card.used = 1500

    db_session.add_all([second_bank, second_asset])
    db_session.commit()

    try:
        response = authenticated_client.get("/dashboard/summary")

        assert response.status_code == 200

        data = response.get_json()

        assert data["total_bank_balance"] == 13500.0
        assert data["total_assets"] == 17500.0
        assert data["total_savings"] == 5000.0
        assert data["total_credit_card_debt"] == 1500.0
        assert data["net_worth"] == 34500.0
    finally:
        db_session.rollback()

        for model, object_id in [
            (type(second_asset), second_asset.id),
            (type(second_bank), second_bank.id),
        ]:
            existing = db_session.get(model, object_id)
            if existing is not None:
                db_session.delete(existing)

        db_session.commit()


def test_dashboard_summary_does_not_include_other_users_data(
    authenticated_client,
    other_user,
    test_bank,
    db_session,
):
    other_bank = type(test_bank)(
        name="Dashboard Other User Bank",
        user_id=other_user.id,
        balance=90000,
    )

    db_session.add(other_bank)
    db_session.commit()

    try:
        response = authenticated_client.get("/dashboard/summary")

        assert response.status_code == 200

        data = response.get_json()

        assert data["total_bank_balance"] == 10000.0
        assert data["total_assets"] == 0.0
        assert data["total_savings"] == 0.0
        assert data["total_credit_card_debt"] == 0.0
        assert data["net_worth"] == 10000.0
    finally:
        db_session.rollback()
        existing = db_session.get(type(test_bank), other_bank.id)
        if existing is not None:
            db_session.delete(existing)
            db_session.commit()


# ============================================================
# GET /dashboard/spending
# ============================================================


def test_dashboard_spending_requires_authentication(client):
    response = client.get("/dashboard/spending")

    assert response.status_code == 401


def test_dashboard_spending_returns_empty_list_for_new_user(
    authenticated_client,
):
    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == []


def test_dashboard_spending_uses_30d_as_default_range(
    authenticated_client,
    test_bank,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    recent = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-400,
        date=now - timedelta(days=5),
        description="Recent expense",
        category="Food",
        transaction_type="expense",
        bank_balance_after=9600,
    )

    old = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-900,
        date=now - timedelta(days=45),
        description="Old expense",
        category="Travel",
        transaction_type="expense",
        bank_balance_after=8700,
    )

    db_session.add_all([recent, old])
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "Food", "value": 400.0}
    ]


def test_dashboard_spending_accepts_all_valid_ranges(
    authenticated_client,
):
    for range_key in ("30d", "3m", "6m", "1y", "all"):
        response = authenticated_client.get(
            "/dashboard/spending",
            query_string={"range": range_key},
        )

        assert response.status_code == 200
        assert isinstance(response.get_json(), list)


def test_dashboard_spending_rejects_invalid_range(
    authenticated_client,
):
    response = authenticated_client.get(
        "/dashboard/spending",
        query_string={"range": "7d"},
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == (
        "Invalid range. Allowed values: "
        "30d, 3m, 6m, 1y, all"
    )


def test_dashboard_spending_filters_by_selected_time_range(
    authenticated_client,
    test_bank,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    recent = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-100,
        date=now - timedelta(days=10),
        description="Recent",
        category="Recent",
        transaction_type="expense",
        bank_balance_after=9900,
    )

    two_months = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-200,
        date=now - timedelta(days=60),
        description="Two months",
        category="Two Months",
        transaction_type="expense",
        bank_balance_after=9700,
    )

    seven_months = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-300,
        date=now - timedelta(days=210),
        description="Seven months",
        category="Seven Months",
        transaction_type="expense",
        bank_balance_after=9400,
    )

    two_years = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-400,
        date=now - timedelta(days=730),
        description="Two years",
        category="Two Years",
        transaction_type="expense",
        bank_balance_after=9000,
    )

    db_session.add_all([
        recent,
        two_months,
        seven_months,
        two_years,
    ])
    db_session.commit()

    expected = {
        "30d": {"Recent"},
        "3m": {"Recent", "Two Months"},
        "6m": {"Recent", "Two Months"},
        "1y": {"Recent", "Two Months", "Seven Months"},
        "all": {
            "Recent",
            "Two Months",
            "Seven Months",
            "Two Years",
        },
    }

    for range_key, expected_names in expected.items():
        response = authenticated_client.get(
            "/dashboard/spending",
            query_string={"range": range_key},
        )

        assert response.status_code == 200

        data = response.get_json()
        assert {item["name"] for item in data} == expected_names


def test_dashboard_spending_includes_bank_and_credit_card_expenses(
    authenticated_client,
    test_bank,
    test_credit_card,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    bank_expense = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-250,
        date=now - timedelta(days=3),
        description="Bank food",
        category="Food",
        transaction_type="expense",
        bank_balance_after=9750,
    )

    card_expense = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_user.id,
        amount=-150,
        date=now - timedelta(days=2),
        description="Card food",
        category="Food",
        transaction_type="expense",
        card_balance_after=150,
        is_payment=False,
        is_billed=False,
    )

    db_session.add_all([bank_expense, card_expense])
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "Food", "value": 400.0}
    ]


def test_dashboard_spending_excludes_non_expense_transactions(
    authenticated_client,
    test_bank,
    test_saving,
    test_asset,
    test_credit_card,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    expense = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-500,
        date=now - timedelta(days=3),
        description="Expense",
        category="Food",
        transaction_type="expense",
        bank_balance_after=9500,
    )

    income = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=2000,
        date=now - timedelta(days=3),
        description="Salary",
        category="Income",
        transaction_type="income",
        bank_balance_after=11500,
    )

    payment = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_user.id,
        amount=300,
        date=now - timedelta(days=2),
        description="Card payment",
        category="Payment",
        transaction_type="payment",
        card_balance_after=200,
        is_payment=True,
        is_billed=True,
    )

    saving_deposit = SavingTransaction(
        saving_id=test_saving.id,
        user_id=test_user.id,
        amount=1000,
        date=now - timedelta(days=2),
        description="Savings deposit",
        category="Savings",
        transaction_type="deposit",
        saving_balance_after=6000,
    )

    asset_deposit = AssetTransaction(
        asset_id=test_asset.id,
        user_id=test_user.id,
        amount=750,
        date=now - timedelta(days=1),
        description="Investment",
        category="Investment",
        transaction_type="deposit",
        asset_balance_after=10750,
    )

    db_session.add_all([
        expense,
        income,
        payment,
        saving_deposit,
        asset_deposit,
    ])
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "Food", "value": 500.0}
    ]


def test_dashboard_spending_normalizes_category_names_and_nulls(
    authenticated_client,
    test_bank,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    transactions = [
        BankTransaction(
            bank_id=test_bank.id,
            user_id=test_user.id,
            amount=-100,
            date=now - timedelta(days=2),
            description="Food 1",
            category=" Food ",
            transaction_type="expense",
            bank_balance_after=9900,
        ),
        BankTransaction(
            bank_id=test_bank.id,
            user_id=test_user.id,
            amount=-50,
            date=now - timedelta(days=2),
            description="Food 2",
            category="food",
            transaction_type="expense",
            bank_balance_after=9850,
        ),
        BankTransaction(
            bank_id=test_bank.id,
            user_id=test_user.id,
            amount=-75,
            date=now - timedelta(days=2),
            description="No category",
            category=None,
            transaction_type="expense",
            bank_balance_after=9775,
        ),
    ]

    db_session.add_all(transactions)
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "Food", "value": 150.0},
        {"name": "Uncategorized", "value": 75.0},
    ]


def test_dashboard_spending_sorts_by_total_descending(
    authenticated_client,
    test_bank,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    transactions = [
        BankTransaction(
            bank_id=test_bank.id,
            user_id=test_user.id,
            amount=-100,
            date=now - timedelta(days=2),
            description="A",
            category="A",
            transaction_type="expense",
            bank_balance_after=9900,
        ),
        BankTransaction(
            bank_id=test_bank.id,
            user_id=test_user.id,
            amount=-300,
            date=now - timedelta(days=2),
            description="B",
            category="B",
            transaction_type="expense",
            bank_balance_after=9600,
        ),
        BankTransaction(
            bank_id=test_bank.id,
            user_id=test_user.id,
            amount=-200,
            date=now - timedelta(days=2),
            description="C",
            category="C",
            transaction_type="expense",
            bank_balance_after=9400,
        ),
    ]

    db_session.add_all(transactions)
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "B", "value": 300.0},
        {"name": "C", "value": 200.0},
        {"name": "A", "value": 100.0},
    ]


def test_dashboard_spending_returns_only_top_12_categories(
    authenticated_client,
    test_bank,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    transactions = []

    for index in range(1, 14):
        transactions.append(
            BankTransaction(
                bank_id=test_bank.id,
                user_id=test_user.id,
                amount=-index * 100,
                date=now - timedelta(days=1),
                description=f"Category {index}",
                category=f"Category {index}",
                transaction_type="expense",
                bank_balance_after=10000 - index * 100,
            )
        )

    db_session.add_all(transactions)
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200

    data = response.get_json()

    assert len(data) == 12
    assert data[0] == {
        "name": "Category 13",
        "value": 1300.0,
    }
    assert data[-1] == {
        "name": "Category 2",
        "value": 200.0,
    }
    assert {item["name"] for item in data} == {
        f"Category {index}" for index in range(2, 14)
    }


def test_dashboard_spending_does_not_include_other_users_transactions(
    authenticated_client,
    other_user,
    test_bank,
    test_user,
    db_session,
):
    now = datetime.now(timezone.utc)

    own = BankTransaction(
        bank_id=test_bank.id,
        user_id=test_user.id,
        amount=-100,
        date=now - timedelta(days=2),
        description="Own",
        category="Own",
        transaction_type="expense",
        bank_balance_after=9900,
    )

    other = BankTransaction(
        bank_id=None,
        user_id=other_user.id,
        amount=-10000,
        date=now - timedelta(days=2),
        description="Other",
        category="Other",
        transaction_type="expense",
        bank_balance_after=0,
    )

    db_session.add_all([own, other])
    db_session.commit()

    response = authenticated_client.get("/dashboard/spending")

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "Own", "value": 100.0}
    ]


# ============================================================
# GET /dashboard/asset-allocation
# ============================================================


def test_dashboard_asset_allocation_requires_authentication(client):
    response = client.get("/dashboard/asset-allocation")

    assert response.status_code == 401


def test_dashboard_asset_allocation_returns_empty_list_for_new_user(
    authenticated_client,
):
    response = authenticated_client.get("/dashboard/asset-allocation")

    assert response.status_code == 200
    assert response.get_json() == []


def test_dashboard_asset_allocation_groups_and_sorts_assets(
    authenticated_client,
    test_asset,
    test_user,
    db_session,
):
    second_stocks = Asset(
        name="Dashboard Stocks 2",
        user_id=test_user.id,
        platform="Broker 2",
        category="Stocks",
        balance=7000,
    )

    first_stocks = Asset(
        name="Dashboard Stocks 1",
        user_id=test_user.id,
        platform="Broker 1",
        category="Stocks",
        balance=3000,
    )

    fixed_deposit = Asset(
        name="Dashboard FD",
        user_id=test_user.id,
        platform="Bank",
        category="FD",
        balance=15000,
    )

    db_session.add_all([
        second_stocks,
        first_stocks,
        fixed_deposit,
    ])
    db_session.commit()

    response = authenticated_client.get(
        "/dashboard/asset-allocation"
    )

    assert response.status_code == 200

    data = response.get_json()

    assert len(data) == 3

    assert data[0] == {
        "name": "FD",
        "value": 15000.0,
    }

    assert {item["name"] for item in data[1:]} == {
        "Stocks",
        "Mutual Funds",
    }

    assert {item["value"] for item in data[1:]} == {
        10000.0,
    }

    db_session.rollback()

    for asset in [
        second_stocks,
        first_stocks,
        fixed_deposit,
    ]:
        existing = db_session.get(Asset, asset.id)
        if existing is not None:
            db_session.delete(existing)

    db_session.commit()


def test_dashboard_asset_allocation_treats_null_category_as_uncategorized(
    authenticated_client,
    test_user,
    db_session,
):
    uncategorized = Asset(
        name="Dashboard Uncategorized",
        user_id=test_user.id,
        platform="Unknown",
        category=None,
        balance=2500,
    )

    db_session.add(uncategorized)
    db_session.commit()

    response = authenticated_client.get(
        "/dashboard/asset-allocation"
    )

    assert response.status_code == 200
    assert response.get_json() == [
        {"name": "Uncategorized", "value": 2500.0}
    ]

    db_session.delete(uncategorized)
    db_session.commit()


def test_dashboard_asset_allocation_does_not_include_other_users_assets(
    authenticated_client,
    other_user,
    test_user,
    db_session,
):
    other_asset = Asset(
        name="Dashboard Other User Asset",
        user_id=other_user.id,
        platform="Other",
        category="Stocks",
        balance=50000,
    )

    own_asset = Asset(
        name="Dashboard Own Asset",
        user_id=test_user.id,
        platform="Own",
        category="Stocks",
        balance=5000,
    )

    db_session.add_all([other_asset, own_asset])
    db_session.commit()

    try:
        response = authenticated_client.get(
            "/dashboard/asset-allocation"
        )

        assert response.status_code == 200
        assert response.get_json() == [
            {"name": "Stocks", "value": 5000.0}
        ]
    finally:
        db_session.rollback()

        for asset in [other_asset, own_asset]:
            existing = db_session.get(Asset, asset.id)
            if existing is not None:
                db_session.delete(existing)

        db_session.commit()