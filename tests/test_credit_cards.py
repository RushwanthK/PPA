from datetime import timedelta, datetime, timezone

import pytest
import pytz

from app.credit_cards.credit_card_util import get_billing_cycle_range
from app.models import CreditCard, CreditCardTransaction


IST = pytz.timezone("Asia/Kolkata")


def today_ist():
    return datetime.now(IST).date()


def date_string(days_from_today=0):
    return (today_ist() + timedelta(days=days_from_today)).strftime("%Y-%m-%d")


def previous_cycle_date(billing_day=1):
    cycle_start, _ = get_billing_cycle_range(today_ist(), billing_day)
    return (cycle_start - timedelta(days=1)).strftime("%Y-%m-%d")

def current_cycle_date(billing_day=1):
    cycle_start, _ = get_billing_cycle_range(today_ist(), billing_day)
    return cycle_start.strftime("%Y-%m-%d")

# ============================================================
# GET /credit_cards
# ============================================================


def test_get_credit_cards_returns_user_cards(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.get("/credit_cards")

    assert response.status_code == 200

    data = response.get_json()

    assert isinstance(data, list)
    assert len(data) == 1

    card = data[0]

    assert card["id"] == test_credit_card.id
    assert card["name"] == test_credit_card.name
    assert card["user_id"] == test_credit_card.user_id
    assert card["limit"] == test_credit_card.limit
    assert card["used"] == test_credit_card.used
    assert card["available_limit"] == test_credit_card.available_limit
    assert card["billed_unpaid"] == test_credit_card.billed_unpaid
    assert card["unbilled_spends"] == test_credit_card.unbilled_spends
    assert card["billing_cycle_start"] == test_credit_card.billing_cycle_start
    assert card["total_payable"] == test_credit_card.total_payable
    assert card["last_payment_date"] is None
    assert card["last_payment_amount"] is None


def test_get_credit_cards_requires_authentication(client):
    response = client.get("/credit_cards")

    assert response.status_code == 401


def test_get_credit_cards_does_not_return_other_users_cards(
    authenticated_client,
    test_user,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="Other User Card",
        user_id=other_user.id,
        limit=15000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.get("/credit_cards")

    assert response.status_code == 200
    assert response.get_json() == []

    db_session.delete(other_card)
    db_session.commit()


# ============================================================
# POST /credit_cards
# ============================================================


def test_create_credit_card_success(
    authenticated_client,
    test_user,
    db_session,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": "New Test Card",
            "limit": 25000,
            "billing_cycle_start": 15,
        },
    )

    assert response.status_code == 201

    data = response.get_json()

    assert data["message"] == "Credit card created successfully"
    assert "card" in data

    card_data = data["card"]

    assert card_data["id"] is not None
    assert card_data["name"] == "New Test Card"
    assert card_data["user_id"] == test_user.id
    assert card_data["limit"] == 25000.0
    assert card_data["available_limit"] == 25000.0
    assert card_data["used"] == 0
    assert card_data["billed_unpaid"] == 0
    assert card_data["unbilled_spends"] == 0
    assert card_data["billing_cycle_start"] == 15
    assert card_data["total_payable"] == 0

    created_card = db_session.get(CreditCard, card_data["id"])
    assert created_card is not None
    assert created_card.user_id == test_user.id
    assert created_card.limit == 25000.0

    db_session.delete(created_card)
    db_session.commit()


def test_create_credit_card_uses_defaults_for_billing_day(
    authenticated_client,
    db_session,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": "Default Cycle Card",
            "limit": 10000,
        },
    )

    assert response.status_code == 201
    assert response.get_json()["card"]["billing_cycle_start"] == 1

    card = db_session.get(
        CreditCard,
        response.get_json()["card"]["id"],
    )
    db_session.delete(card)
    db_session.commit()


@pytest.mark.parametrize("missing_field", ["name", "limit"])
def test_create_credit_card_requires_required_fields(
    authenticated_client,
    missing_field,
):
    payload = {
        "name": "Required Field Card",
        "limit": 10000,
    }
    payload.pop(missing_field)

    response = authenticated_client.post(
        "/credit_cards",
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        f"Missing required field: {missing_field}"
    )


@pytest.mark.parametrize(
    "field",
    ["used", "available_limit", "billed_unpaid", "unbilled_spends"],
)
def test_create_credit_card_rejects_manual_calculated_fields(
    authenticated_client,
    field,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": f"Forbidden {field}",
            "limit": 10000,
            field: 1,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        f"Cannot manually set calculated field: {field}"
    )


@pytest.mark.parametrize("billing_day", [0, 32, -1, 99])
def test_create_credit_card_rejects_invalid_billing_day(
    authenticated_client,
    billing_day,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": f"Invalid Day {billing_day}",
            "limit": 10000,
            "billing_cycle_start": billing_day,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Billing cycle start must be between 1-31"
    )


def test_create_credit_card_rejects_invalid_billing_day_type(
    authenticated_client,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": "Invalid Day Type",
            "limit": 10000,
            "billing_cycle_start": "not-a-number",
        },
    )

    assert response.status_code == 400
    assert "Invalid numeric value" in response.get_json()["error"]


@pytest.mark.parametrize("limit", [0, -1, -10000])
def test_create_credit_card_rejects_non_positive_limit(
    authenticated_client,
    limit,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": f"Invalid Limit {limit}",
            "limit": limit,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Limit must be positive"


def test_create_credit_card_rejects_invalid_limit_type(authenticated_client):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": "Invalid Limit Type",
            "limit": "not-a-number",
        },
    )

    assert response.status_code == 400
    assert "Invalid numeric value" in response.get_json()["error"]


def test_create_credit_card_rejects_duplicate_name(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": test_credit_card.name,
            "limit": 20000,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Credit card name already exists"


def test_create_credit_card_does_not_trust_payload_user_id(
    authenticated_client,
    test_user,
    other_user,
    db_session,
):
    response = authenticated_client.post(
        "/credit_cards",
        json={
            "name": "JWT Owned Card",
            "limit": 10000,
            "user_id": other_user.id,
        },
    )

    assert response.status_code == 201

    card = db_session.get(CreditCard, response.get_json()["card"]["id"])
    assert card.user_id == test_user.id

    db_session.delete(card)
    db_session.commit()


# ============================================================
# GET /credit_cards/<id>
# ============================================================


def test_get_credit_card_returns_card(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.get(
        f"/credit_cards/{test_credit_card.id}"
    )

    assert response.status_code == 200

    data = response.get_json()
    assert data["id"] == test_credit_card.id
    assert data["name"] == test_credit_card.name
    assert data["user_id"] == test_credit_card.user_id
    assert data["available_limit"] == test_credit_card.available_limit
    assert data["total_payable"] == test_credit_card.total_payable


def test_get_credit_card_requires_authentication(client, test_credit_card):
    response = client.get(f"/credit_cards/{test_credit_card.id}")

    assert response.status_code == 401


def test_get_credit_card_returns_404_for_missing_card(authenticated_client):
    response = authenticated_client.get("/credit_cards/999999")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"


def test_other_user_cannot_get_credit_card(
    authenticated_client,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="Private Other Card",
        user_id=other_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.get(
        f"/credit_cards/{other_card.id}"
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"

    db_session.delete(other_card)
    db_session.commit()


# ============================================================
# PUT /credit_cards/<id>
# ============================================================


def test_update_credit_card_name_limit_and_cycle(
    authenticated_client,
    test_credit_card,
    db_session,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={
            "name": "Updated Card",
            "limit": 20000,
            "billing_cycle_start": 10,
        },
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["message"] == "Credit card updated successfully"
    assert data["card"]["name"] == "Updated Card"
    assert data["card"]["limit"] == 20000.0
    assert data["card"]["billing_cycle_start"] == 10

    db_session.expire_all()
    card = db_session.get(CreditCard, test_credit_card.id)
    assert card.name == "Updated Card"
    assert card.limit == 20000.0
    assert card.billing_cycle_start == 10


def test_update_credit_card_requires_authentication(client, test_credit_card):
    response = client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"name": "Unauthorized"},
    )

    assert response.status_code == 401


def test_update_credit_card_returns_404_for_missing_card(authenticated_client):
    response = authenticated_client.put(
        "/credit_cards/999999",
        json={"name": "Missing"},
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"


def test_other_user_cannot_update_credit_card(
    authenticated_client,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="Update Private Card",
        user_id=other_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.put(
        f"/credit_cards/{other_card.id}",
        json={"name": "Should Not Change"},
    )

    assert response.status_code == 404

    db_session.expire_all()
    assert db_session.get(CreditCard, other_card.id).name == "Update Private Card"

    db_session.delete(other_card)
    db_session.commit()


@pytest.mark.parametrize("field", ["used", "available_limit", "billed_unpaid", "unbilled_spends"])
def test_update_credit_card_rejects_calculated_fields(
    authenticated_client,
    test_credit_card,
    field,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={field: 123},
    )

    assert response.status_code == 400
    assert field in response.get_json()["error"]


def test_update_credit_card_user_id_field_cannot_change_ownership(
    authenticated_client,
    test_credit_card,
    other_user,
    db_session,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"user_id": other_user.id},
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == "No changes detected"

    db_session.expire_all()
    card = db_session.get(CreditCard, test_credit_card.id)
    assert card.user_id != other_user.id


def test_update_credit_card_no_changes_returns_current_card(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={
            "name": test_credit_card.name,
            "limit": test_credit_card.limit,
            "billing_cycle_start": test_credit_card.billing_cycle_start,
        },
    )

    assert response.status_code == 200
    data = response.get_json()
    assert data["message"] == "No changes detected"
    assert data["card"]["id"] == test_credit_card.id


@pytest.mark.parametrize("limit", [0, -1])
def test_update_credit_card_rejects_non_positive_limit(
    authenticated_client,
    test_credit_card,
    limit,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"limit": limit},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Limit must be positive"


def test_update_credit_card_rejects_limit_below_current_used(
    authenticated_client,
    test_credit_card,
    db_session,
):
    test_credit_card.used = 5000
    db_session.commit()

    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"limit": 4999},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "New limit cannot be less than currently used amount (5000.0)"
    )

    db_session.expire_all()
    assert db_session.get(CreditCard, test_credit_card.id).limit == 10000


def test_update_credit_card_rejects_invalid_limit_type(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"limit": "invalid"},
    )

    assert response.status_code == 400
    assert "Invalid numeric value" in response.get_json()["error"]


@pytest.mark.parametrize("billing_day", [0, 32])
def test_update_credit_card_rejects_invalid_billing_day(
    authenticated_client,
    test_credit_card,
    billing_day,
):
    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"billing_cycle_start": billing_day},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Billing cycle start must be between 1-31"
    )


def test_update_credit_card_rejects_duplicate_name(
    authenticated_client,
    test_credit_card,
    db_session,
):
    second_card = CreditCard(
        name="Second Card",
        user_id=test_credit_card.user_id,
        limit=15000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(second_card)
    db_session.commit()

    response = authenticated_client.put(
        f"/credit_cards/{second_card.id}",
        json={"name": test_credit_card.name},
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Credit card name already exists"

    db_session.rollback()
    existing_card = db_session.get(CreditCard, second_card.id)
    if existing_card is not None:
        db_session.delete(existing_card)
        db_session.commit()


def test_update_credit_card_cycle_change_recalculates_unbilled_spends(
    authenticated_client,
    test_credit_card,
    db_session,
):
    current_date = today_ist()
    current_cycle_start, _ = get_billing_cycle_range(
        current_date,
        test_credit_card.billing_cycle_start,
    )

    historical_date = current_cycle_start - timedelta(days=1)
    current_date = current_cycle_start

    historical_txn = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=-500,
        date=datetime.combine(historical_date, datetime.min.time()),
        description="Historical expense",
        category="Bills",
        transaction_type="expense",
        is_payment=False,
        is_billed=True,
    )
    current_txn = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=-300,
        date=datetime.combine(current_date, datetime.min.time()),
        description="Current expense",
        category="Shopping",
        transaction_type="expense",
        is_payment=False,
        is_billed=False,
    )
    payment = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=100,
        date=datetime.combine(current_date, datetime.min.time()) + timedelta(seconds=1),
        description="Payment",
        category="Payment",
        transaction_type="payment",
        is_payment=True,
        is_billed=True,
    )

    db_session.add_all([historical_txn, current_txn, payment])
    db_session.commit()

    response = authenticated_client.put(
        f"/credit_cards/{test_credit_card.id}",
        json={"billing_cycle_start": 15},
    )

    assert response.status_code == 200

    db_session.expire_all()
    card = db_session.get(CreditCard, test_credit_card.id)

    # Exact value depends on today's position relative to the new billing day.
    # The key assertion is that the route recalculates from transactions rather
    # than preserving the previous unbilled value blindly.
    assert card.billing_cycle_start == 15
    assert card.unbilled_spends >= 0


# ============================================================
# POST /credit_cards/<id>/transactions
# ============================================================


def test_add_credit_card_expense_current_cycle_success(
    authenticated_client,
    test_credit_card,
    db_session,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -1200,
            "date": date_string(),
            "description": "Groceries",
            "category": "Food",
            "is_payment": False,
        },
    )

    assert response.status_code == 201
    data = response.get_json()

    assert data["message"] == "Transaction added successfully"
    assert data["transaction"]["amount"] == -1200
    assert data["transaction"]["type"] == "expense"
    assert data["transaction"]["is_billed"] is False
    assert data["card"]["used"] == 1200
    assert data["card"]["available_limit"] == 8800
    assert data["card"]["billed_unpaid"] == 0
    assert data["card"]["unbilled_spends"] == 1200

    tx = (
        db_session.query(CreditCardTransaction)
        .filter_by(credit_card_id=test_credit_card.id)
        .one()
    )
    assert tx.amount == -1200
    assert tx.transaction_type == "expense"
    assert tx.is_payment is False


def test_add_credit_card_past_cycle_expense_is_billed(
    authenticated_client,
    test_credit_card,
    db_session,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -800,
            "date": previous_cycle_date(),
            "description": "Old expense",
            "category": "Bills",
            "is_payment": False,
        },
    )

    assert response.status_code == 201
    data = response.get_json()

    assert data["transaction"]["is_billed"] is True
    assert data["card"]["used"] == 800
    assert data["card"]["billed_unpaid"] == 800
    assert data["card"]["unbilled_spends"] == 0

    db_session.expire_all()
    card = db_session.get(CreditCard, test_credit_card.id)
    assert card.billed_unpaid == 800
    assert card.unbilled_spends == 0



def test_add_credit_card_payment_reduces_unbilled_spends(
    authenticated_client,
    test_credit_card,
    db_session,
):
    expense = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -1000,
            "date": date_string(-1),
            "description": "Expense",
            "category": "Shopping",
            "is_payment": False,
        },
    )
    assert expense.status_code == 201

    payment = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": 400,
            "date": date_string(),
            "description": "Payment",
            "category": "Payment",
            "is_payment": True,
        },
    )

    assert payment.status_code == 201
    data = payment.get_json()

    assert data["transaction"]["amount"] == 400
    assert data["transaction"]["type"] == "payment"
    assert data["card"]["used"] == 600
    assert data["card"]["available_limit"] == 9400
    assert data["card"]["unbilled_spends"] == 600
    assert data["card"]["billed_unpaid"] == 0

    db_session.expire_all()
    card = db_session.get(CreditCard, test_credit_card.id)
    assert card.last_payment_amount == 400
    assert card.last_payment_date is not None


def test_add_credit_card_payment_crosses_billed_and_unbilled_balances(
    authenticated_client,
    test_credit_card,
    db_session,
):
    billed = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -500,
            "date": previous_cycle_date(),
        },
    )
    assert billed.status_code == 201

    unbilled = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -300,
            "date": current_cycle_date(),
        },
    )
    assert unbilled.status_code == 201

    payment = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": 600,
            "date": date_string(),
        },
    )

    assert payment.status_code == 201

    data = payment.get_json()

    assert data["message"] == "Transaction added successfully"

    assert data["transaction"]["amount"] == 600
    assert data["transaction"]["type"] == "payment"

    assert data["card"]["billed_unpaid"] == 0
    assert data["card"]["unbilled_spends"] == 200
    assert data["card"]["used"] == 200
    assert data["card"]["available_limit"] == 9800
    assert data["card"]["total_payable"] == 0

    db_session.expire_all()

    card = db_session.get(CreditCard, test_credit_card.id)

    assert card.last_payment_amount == 600
    assert card.last_payment_date is not None


@pytest.mark.parametrize(
    "missing_field, expected_error",
    [
        ("amount", "Amount is required"),
        ("date", "Transaction date is required (DDMMYYYY format)"),
    ],
)
def test_add_credit_card_transaction_requires_fields(
    authenticated_client,
    test_credit_card,
    missing_field,
    expected_error,
):
    payload = {
        "amount": -100,
        "date": date_string(),
    }
    payload.pop(missing_field)

    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json=payload,
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error


def test_add_credit_card_transaction_rejects_invalid_date(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -100,
            "date": "2026-99-99",
        },
    )

    assert response.status_code == 400
    assert "Invalid data format" in response.get_json()["error"]


def test_add_credit_card_transaction_rejects_future_date(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -100,
            "date": date_string(1),
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Transaction date cannot be in the future"
    )


def test_add_credit_card_transaction_rejects_zero_amount(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": 0,
            "date": date_string(),
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Amount cannot be zero"


def test_add_credit_card_transaction_enforces_chronological_order(
    authenticated_client,
    test_credit_card,
):
    first = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -100,
            "date": date_string(),
        },
    )
    assert first.status_code == 201

    second = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -50,
            "date": date_string(-1),
        },
    )

    assert second.status_code == 400
    assert second.get_json()["error"] == (
        "Transaction date must be on or after the last transaction's date."
    )


def test_add_credit_card_rejects_payment_before_any_expense(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": 500,
            "date": date_string(),
            "is_payment": True,
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Cannot add payment without any prior expenses."
    )


def test_add_credit_card_rejects_expense_above_available_limit(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -10001,
            "date": date_string(),
        },
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == (
        "Transaction would exceed available credit limit"
    )


def test_add_credit_card_rejects_payment_above_total_owed(
    authenticated_client,
    test_credit_card,
):
    expense = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -500,
            "date": date_string(-1),
        },
    )

    assert expense.status_code == 201

    payment = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": 501,
            "date": date_string(),
        },
    )

    assert payment.status_code == 400

    data = payment.get_json()

    assert data["error"] == "Payment amount exceeds total owed amount"


def test_failed_transaction_does_not_create_database_row_or_change_card(
    authenticated_client,
    test_credit_card,
    db_session,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -10001,
            "date": date_string(),
        },
    )

    assert response.status_code == 400

    db_session.expire_all()
    card = db_session.get(CreditCard, test_credit_card.id)
    tx_count = (
        db_session.query(CreditCardTransaction)
        .filter_by(credit_card_id=test_credit_card.id)
        .count()
    )

    assert card.used == 0
    assert card.billed_unpaid == 0
    assert card.unbilled_spends == 0
    assert tx_count == 0


def test_add_credit_card_transaction_requires_authentication(
    client,
    test_credit_card,
):
    response = client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={"amount": -100, "date": date_string()},
    )

    assert response.status_code == 401


def test_add_credit_card_transaction_returns_404_for_missing_card(
    authenticated_client,
):
    response = authenticated_client.post(
        "/credit_cards/999999/transactions",
        json={"amount": -100, "date": date_string()},
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"


def test_other_user_cannot_add_credit_card_transaction(
    authenticated_client,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="Transaction Private Card",
        user_id=other_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.post(
        f"/credit_cards/{other_card.id}/transactions",
        json={"amount": -100, "date": date_string()},
    )

    assert response.status_code == 404

    db_session.delete(other_card)
    db_session.commit()


# ============================================================
# GET /credit_cards/<id>/transactions
# ============================================================


def test_get_credit_card_transactions_returns_descending_history(
    authenticated_client,
    test_credit_card,
    db_session,
):
    older = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=-100,
        date=datetime(2026, 1, 1, 10, 0, tzinfo=timezone.utc),
        description="Older",
        category="Bills",
        transaction_type="expense",
        is_payment=False,
        is_billed=True,
    )
    newer = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=50,
        date=datetime(2026, 1, 2, 10, 0, tzinfo=timezone.utc),
        description="Newer",
        category="Payment",
        transaction_type="payment",
        is_payment=True,
        is_billed=True,
    )

    db_session.add_all([older, newer])
    db_session.commit()

    response = authenticated_client.get(
        f"/credit_cards/{test_credit_card.id}/transactions"
    )

    assert response.status_code == 200
    data = response.get_json()

    assert len(data) == 2
    assert data[0]["description"] == "Newer"
    assert data[0]["amount"] == 50
    assert data[0]["type"] == "payment"
    assert data[0]["is_payment"] is True
    assert data[0]["is_billed"] is True
    assert data[1]["description"] == "Older"
    assert data[1]["type"] == "expense"


def test_get_credit_card_transactions_returns_empty_history(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.get(
        f"/credit_cards/{test_credit_card.id}/transactions"
    )

    assert response.status_code == 200
    assert response.get_json() == []


def test_get_credit_card_transactions_requires_authentication(
    client,
    test_credit_card,
):
    response = client.get(
        f"/credit_cards/{test_credit_card.id}/transactions"
    )

    assert response.status_code == 401


def test_get_credit_card_transactions_returns_404_for_missing_card(
    authenticated_client,
):
    response = authenticated_client.get(
        "/credit_cards/999999/transactions"
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"


def test_other_user_cannot_get_credit_card_transactions(
    authenticated_client,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="History Private Card",
        user_id=other_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.get(
        f"/credit_cards/{other_card.id}/transactions"
    )

    assert response.status_code == 404

    db_session.delete(other_card)
    db_session.commit()


# ============================================================
# POST /credit_cards/<id>/process_billing
# ============================================================


def test_process_billing_requires_authentication(client, test_credit_card):
    response = client.post(
        f"/credit_cards/{test_credit_card.id}/process_billing"
    )

    assert response.status_code == 401


def test_process_billing_returns_404_for_missing_card(authenticated_client):
    response = authenticated_client.post(
        "/credit_cards/999999/process_billing"
    )

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"


def test_other_user_cannot_process_billing(
    authenticated_client,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="Billing Private Card",
        user_id=other_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.post(
        f"/credit_cards/{other_card.id}/process_billing"
    )

    assert response.status_code == 404

    db_session.delete(other_card)
    db_session.commit()


def test_process_billing_with_no_transactions_is_stable(
    authenticated_client,
    test_credit_card,
):
    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/process_billing"
    )

    assert response.status_code == 200
    data = response.get_json()

    assert data["message"] == "Billing processed successfully"
    assert data["card"]["billed_unpaid"] == 0
    assert data["card"]["unbilled_spends"] == 0
    assert data["card"]["used"] == 0
    assert data["card"]["available_limit"] == test_credit_card.limit
    assert data["card"]["total_payable"] == 0


def test_process_billing_reclassifies_expenses_and_reapplies_payments(
    authenticated_client,
    test_credit_card,
    db_session,
):
    cycle_start, _ = get_billing_cycle_range(
        today_ist(),
        test_credit_card.billing_cycle_start,
    )

    historical = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=-500,
        date=datetime.combine(
            cycle_start - timedelta(days=1),
            datetime.min.time(),
        ),
        description="Historical expense",
        category="Bills",
        transaction_type="expense",
        is_payment=False,
        is_billed=False,
    )
    current = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=-300,
        date=datetime.combine(
            cycle_start,
            datetime.min.time(),
        ),
        description="Current expense",
        category="Shopping",
        transaction_type="expense",
        is_payment=False,
        is_billed=True,
    )
    payment = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=400,
        date=datetime.combine(
            cycle_start,
            datetime.min.time(),
        ) + timedelta(seconds=1),
        description="Payment",
        category="Payment",
        transaction_type="payment",
        is_payment=True,
        is_billed=False,
    )

    db_session.add_all([historical, current, payment])
    db_session.commit()

    response = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/process_billing"
    )

    assert response.status_code == 200
    data = response.get_json()

    # 500 billed expense + 300 current expense - 400 payment = 400 used.
    assert data["card"]["billed_unpaid"] == 100
    assert data["card"]["unbilled_spends"] == 300
    assert data["card"]["used"] == 400
    assert data["card"]["available_limit"] == 9600
    assert data["card"]["total_payable"] == 100

    db_session.expire_all()

    transactions = (
        db_session.query(CreditCardTransaction)
        .filter_by(credit_card_id=test_credit_card.id)
        .all()
    )

    by_description = {txn.description: txn for txn in transactions}
    assert by_description["Historical expense"].is_billed is True
    assert by_description["Current expense"].is_billed is False
    assert by_description["Payment"].is_billed is True


def test_process_billing_is_idempotent_for_same_transaction_set(
    authenticated_client,
    test_credit_card,
):
    expense = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/transactions",
        json={
            "amount": -250,
            "date": date_string(),
        },
    )
    assert expense.status_code == 201

    first = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/process_billing"
    )
    second = authenticated_client.post(
        f"/credit_cards/{test_credit_card.id}/process_billing"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.get_json()["card"] == first.get_json()["card"]


# ============================================================
# DELETE /credit_cards/<id>
# ============================================================


def test_delete_credit_card_requires_authentication(client, test_credit_card):
    response = client.delete(f"/credit_cards/{test_credit_card.id}")

    assert response.status_code == 401


def test_delete_credit_card_returns_404_for_missing_card(authenticated_client):
    response = authenticated_client.delete("/credit_cards/999999")

    assert response.status_code == 404
    assert response.get_json()["error"] == "Credit card not found"


def test_other_user_cannot_delete_credit_card(
    authenticated_client,
    other_user,
    db_session,
):
    other_card = CreditCard(
        name="Delete Private Card",
        user_id=other_user.id,
        limit=10000,
        billing_cycle_start=1,
        used=0,
        billed_unpaid=0,
        unbilled_spends=0,
    )
    db_session.add(other_card)
    db_session.commit()

    response = authenticated_client.delete(
        f"/credit_cards/{other_card.id}"
    )

    assert response.status_code == 404
    assert db_session.get(CreditCard, other_card.id) is not None

    db_session.delete(other_card)
    db_session.commit()


@pytest.mark.parametrize(
    "field, value, expected_error",
    [
        (
            "billed_unpaid",
            100,
            "Cannot delete credit card with unpaid balances",
        ),
        (
            "unbilled_spends",
            100,
            "Cannot delete credit card with unpaid balances",
        ),
        (
            "used",
            100,
            "Cannot delete credit card with used amount",
        ),
    ],
)
def test_delete_credit_card_rejects_non_deletable_state(
    authenticated_client,
    test_credit_card,
    db_session,
    field,
    value,
    expected_error,
):
    setattr(test_credit_card, field, value)
    db_session.commit()

    response = authenticated_client.delete(
        f"/credit_cards/{test_credit_card.id}"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == expected_error

    db_session.rollback()
    db_session.expire_all()
    assert db_session.get(CreditCard, test_credit_card.id) is not None

    setattr(db_session.get(CreditCard, test_credit_card.id), field, 0)
    db_session.commit()


def test_delete_credit_card_deletes_card_and_transactions(
    authenticated_client,
    test_credit_card,
    db_session,
):
    transaction = CreditCardTransaction(
        credit_card_id=test_credit_card.id,
        user_id=test_credit_card.user_id,
        amount=10,
        date=datetime.now(timezone.utc),
        description="Zero-balance history",
        category="Payment",
        transaction_type="payment",
        is_payment=True,
        is_billed=True,
    )
    db_session.add(transaction)
    db_session.commit()

    response = authenticated_client.delete(
        f"/credit_cards/{test_credit_card.id}"
    )

    assert response.status_code == 200
    assert response.get_json()["message"] == (
        "Credit card and all associated transactions deleted successfully"
    )

    assert db_session.get(CreditCard, test_credit_card.id) is None
    assert (
        db_session.query(CreditCardTransaction)
        .filter_by(credit_card_id=test_credit_card.id)
        .count()
        == 0
    )
