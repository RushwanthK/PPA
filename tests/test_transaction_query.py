"""GET /transactions/query: structured, read-only questions over bank, card and savings transactions."""

from datetime import date, datetime

import pytest

from app.models import (BankTransaction, CreditCardTransaction, SavingTransaction, Transaction, User)


def utc(text):
    """Naive UTC timestamp (the stored convention)."""
    return datetime.strptime(text, "%Y-%m-%d %H:%M")


@pytest.fixture(autouse=True)
def fixed_money_movement(app):
    """Pin the money-movement categories: the developer's .env (e.g. the owner added
    "repayment" on Nov 27) must not change what these tests expect."""
    from app.transactions.transaction_query import DEFAULT_MONEY_MOVEMENT
    app.config["MONEY_MOVEMENT_CATEGORIES"] = ",".join(DEFAULT_MONEY_MOVEMENT)
    yield
    app.config.pop("MONEY_MOVEMENT_CATEGORIES", None)


@pytest.fixture()
def other_user(db_session):
    user = User(name="someone_else", age=30, dob=date(1990, 1, 1), place="Mysuru")
    user.set_password("OtherPassword123!")
    db_session.add(user)
    db_session.commit()
    yield user
    db_session.rollback()
    db_session.query(Transaction).filter(Transaction.user_id == user.id).delete(synchronize_session=False)
    db_session.delete(db_session.get(User, user.id))
    db_session.commit()


@pytest.fixture()
def ledger(db_session, test_user, other_user, test_bank, test_credit_card, test_saving):
    uid = test_user.id
    bank = dict(user_id=uid, bank_id=test_bank.id)
    card = dict(user_id=uid, credit_card_id=test_credit_card.id)
    rows = [
        BankTransaction(**bank, amount=450, category="food", description="Swiggy order",
                        transaction_type="expense", date=utc("2026-11-20 04:30")),
        BankTransaction(**bank, amount=1200.5, category="Rent", description="Rent October",
                        transaction_type="expense", date=utc("2026-10-15 04:30")),
        BankTransaction(**bank, amount=50000, category="Salary", description="Salary",
                        transaction_type="income", date=utc("2026-11-01 04:30")),
        # 31 Oct 19:00 UTC is 1 Nov 00:30 IST: it belongs to November in India.
        BankTransaction(**bank, amount=100, category=" FOOD ", description="Zomato",
                        transaction_type="expense", date=utc("2026-10-31 19:00")),
        # Money movement: a transfer and a card bill paid from the bank.
        BankTransaction(**bank, amount=20000, category="Transfer", description="HDFC to ICICI",
                        transaction_type="expense", date=utc("2026-11-03 04:30")),
        BankTransaction(**bank, amount=3000, category=" cc bills", description="cred - CC bill",
                        transaction_type="expense", date=utc("2026-11-04 04:30")),
        # A trip: money paid to a friend counts, money received back is income.
        BankTransaction(**bank, amount=2500, category="Repayment", description="Solo - Goa trip share",
                        transaction_type="expense", date=utc("2026-01-06 04:30")),
        BankTransaction(**bank, amount=1000, category="Repayment", description="Goa trip - solo returned",
                        transaction_type="income", date=utc("2026-01-20 04:30")),
        CreditCardTransaction(**card, amount=-1800, category="Travel", description="goa trip hotel",
                              transaction_type="expense", date=utc("2026-01-05 03:30")),
        CreditCardTransaction(**card, amount=-2999, category="Shopping", description="Amazon 50%_off",
                              transaction_type="expense", date=utc("2026-11-10 03:30")),
        CreditCardTransaction(**card, amount=-799, category=None, description="Misc",
                              transaction_type="expense", date=utc("2026-09-01 03:30")),
        CreditCardTransaction(**card, amount=5000, category="Payment", description="Bill paid",
                              transaction_type="payment", is_payment=True, date=utc("2026-11-12 03:30")),
        # Out of scope: a savings transfer (always left out since Nov 27), and another user's rows.
        SavingTransaction(user_id=uid, saving_id=test_saving.id, amount=99999, category="Transfer",
                          description="food money to bank", transaction_type="withdrawal",
                          date=utc("2026-11-05 03:30")),
        BankTransaction(user_id=other_user.id, bank_id=test_bank.id, amount=777, category="food",
                        description="Swiggy order", transaction_type="expense", date=utc("2026-11-20 04:30")),
    ]
    db_session.add_all(rows)
    db_session.commit()
    return rows


def query(client, **params):
    return client.get("/transactions/query", query_string=params)


def totals_of(data):
    return {row["type"]: row for row in data["totals"]}


def test_requires_authentication(client):
    assert query(client).status_code == 401


def test_new_user_gets_an_empty_result(authenticated_client):
    data = query(authenticated_client, group_by="category").get_json()
    assert data["matched"] == 0 and data["totals"] == []
    assert "rows" not in data and "groups" not in data


def test_totals_cover_bank_and_card_only_for_this_user(authenticated_client, ledger):
    data = query(authenticated_client, type="expense", limit=0).get_json()
    expense = totals_of(data)["expense"]
    # 450 + 1200.5 + 100 + 20000 + 3000 + 2500 + 1800 + 2999 + 799; no savings transfer, no other user's 777.
    assert expense["count"] == 9 and expense["total"] == 32848.5
    assert expense["smallest"] == 100.0 and expense["largest"] == 20000.0
    assert expense["first_date"] == "2026-01-05" and expense["last_date"] == "2026-11-20"
    assert "rows" not in data


def test_latest_transaction(authenticated_client, ledger):
    data = query(authenticated_client, sort="date_desc", limit=1).get_json()
    swiggy = ledger[0]
    assert data["rows"] == [{"id": swiggy.id, "date": "2026-11-20", "type": "expense", "account": "Test Bank",
                             "category": "Food", "description": "Swiggy order", "amount": 450.0}]
    assert len(query(authenticated_client, limit=30).get_json()["rows"]) == 12   # every in-scope row


def test_any_of_several_terms_matches_description_or_category(authenticated_client, ledger):
    data = query(authenticated_client, terms=["goa", "trip"], type="expense").get_json()
    assert totals_of(data)["expense"]["total"] == 4300.0      # 2500 repayment + 1800 hotel
    assert data["term_matches"] == [{"term": "goa", "count": 2}, {"term": "trip", "count": 2}]
    assert [r["amount"] for r in data["rows"]] == [2500.0, 1800.0]   # newest first

    # Received money is income, kept apart from spending.
    data = query(authenticated_client, terms=["solo"]).get_json()
    assert set(totals_of(data)) == {"expense", "income"} and totals_of(data)["income"]["total"] == 1000.0

    # Category text matches too, case-insensitively.
    assert query(authenticated_client, terms=["FOOD"]).get_json()["matched"] == 2


def test_must_match_words_are_all_required(authenticated_client, ledger):
    # "food in the Goa trip": must contain goa, and any of the food words.
    data = query(authenticated_client, must_match=["goa"], terms=["hotel", "food"], type="expense").get_json()
    assert data["matched"] == 1 and totals_of(data)["expense"]["total"] == 1800.0
    assert data["query"]["must_match"] == ["goa"]
    # Without terms, every must_match word has to match.
    assert query(authenticated_client, must_match=["goa", "share"]).get_json()["matched"] == 1
    assert query(authenticated_client, must_match=["goa", "swiggy"]).get_json()["matched"] == 0
    # "a|b" inside one entry: either may match, still ANDed with the other filters.
    data = query(authenticated_client, must_match=["swiggy|zomato"], type="expense").get_json()
    assert data["matched"] == 2 and data["query"]["must_match"] == ["swiggy|zomato"]
    assert query(authenticated_client, must_match=["goa|swiggy"], terms=["hotel"]).get_json()["matched"] == 1


def test_like_wildcards_in_terms_are_literal(authenticated_client, ledger):
    assert query(authenticated_client, terms=["50%_"]).get_json()["matched"] == 1
    assert query(authenticated_client, terms=["%_"]).get_json()["matched"] == 1     # not "everything"


def test_ist_month_and_amount_filters(authenticated_client, ledger):
    # IST date boundaries: 1 Nov IST starts at 31 Oct 18:30 UTC, so Zomato is in November.
    data = query(authenticated_client, terms=["food"], start_date="2026-11-01", end_date="2026-11-30").get_json()
    assert totals_of(data)["expense"]["total"] == 550.0
    data = query(authenticated_client, type="expense", min_amount=1000, max_amount=3000, sort="amount_asc").get_json()
    assert [r["amount"] for r in data["rows"]] == [1200.5, 1800.0, 2500.0, 2999.0, 3000.0]


def test_money_movement_can_be_excluded_or_queried_alone(authenticated_client, ledger):
    data = query(authenticated_client, type="expense", money_movement="exclude", limit=0).get_json()
    assert totals_of(data)["expense"]["total"] == 9848.5
    assert data["money_movement"]["excluded_count"] == 2 and data["money_movement"]["excluded_total"] == 23000.0

    data = query(authenticated_client, money_movement="only", limit=0).get_json()
    assert totals_of(data)["expense"]["total"] == 23000.0 and "excluded_total" not in data["money_movement"]


def test_money_movement_categories_are_configurable(app, authenticated_client, ledger):
    app.config["MONEY_MOVEMENT_CATEGORIES"] = " Rent ,  "
    data = query(authenticated_client, type="expense", money_movement="only", limit=0).get_json()
    assert data["money_movement"]["categories"] == ["rent"] and totals_of(data)["expense"]["total"] == 1200.5


def test_grouping_by_category_month_account_and_description(authenticated_client, ledger):
    data = query(authenticated_client, group_by="category", money_movement="exclude", limit=0).get_json()
    groups = data["groups"]
    assert groups["type"] == "expense" and groups["groups_total"] == 6
    cats = {g["key"]: g for g in groups["rows"]}
    assert cats["Food"] == {"key": "Food", "count": 2, "total": 550.0, "share_pct": 5.6}   # "food" + " FOOD "
    assert cats["Uncategorized"]["total"] == 799.0

    months = query(authenticated_client, group_by="month", type="expense", limit=0).get_json()["groups"]["rows"]
    assert [m["key"] for m in months] == ["2026-11", "2026-10", "2026-09", "2026-01"]   # newest first
    assert months[0]["total"] == 26549.0

    accounts = query(authenticated_client, group_by="account", type="expense", limit=0).get_json()["groups"]["rows"]
    assert {a["key"]: a["total"] for a in accounts} == {"Test Bank": 27250.5, "Test Credit Card": 5598.0}

    income = query(authenticated_client, group_by="description", type="income", limit=0).get_json()["groups"]
    assert income["type"] == "income" and income["rows"][0]["key"] == "Salary"


def test_savings_withdrawals_are_spending_and_deposits_and_transfers_left_out(
        authenticated_client, ledger, db_session, test_user, test_saving):
    saving = dict(user_id=test_user.id, saving_id=test_saving.id)
    recharge, hundi = (
        SavingTransaction(**saving, amount=499, category="recharge", description="Excitel recharge",
                          transaction_type="withdrawal", date=utc("2026-11-21 04:30")),
        SavingTransaction(**saving, amount=2000, category="Hundi", description="Hundi cash",
                          transaction_type="deposit", date=utc("2026-11-22 04:30")),
    )
    db_session.add_all([recharge, hundi,
                        SavingTransaction(**saving, amount=410, category="CC bills", description="card bill",
                                          transaction_type="withdrawal", date=utc("2026-11-23 04:30"))])
    db_session.commit()

    data = query(authenticated_client, account_kind="savings", limit=5).get_json()
    assert {t["type"]: t["total"] for t in data["totals"]} == {"expense": 499.0}
    assert data["rows"][0] == {"id": recharge.id, "date": "2026-11-21", "type": "expense", "account": "Test Saving",
                               "category": "Recharge", "description": "Excitel recharge", "amount": 499.0}
    # The transfer (99999) and the card bill (410) are always left out; the deposit (money put into
    # savings, owner's decision) is left out of totals too, and reported.
    assert data["savings"] == {"matched": 1, "transfers_left_out": 2, "transfers_left_out_total": 100409.0,
                               "deposits_left_out": 1, "deposits_left_out_total": 2000.0}
    assert query(authenticated_client, account_kind="savings", type="income").get_json()["matched"] == 0
    # Asked about money movement on its own, the deposit is there (as money in), transfers still are not.
    data = query(authenticated_client, account_kind="savings", money_movement="only").get_json()
    assert data["matched"] == 1 and data["rows"][0]["id"] == hundi.id and data["rows"][0]["type"] == "income"

    # "all" now includes savings: the recharge is spending, found by words, type and account name.
    data = query(authenticated_client, type="expense", limit=0).get_json()
    assert totals_of(data)["expense"]["total"] == 32848.5 + 499 and data["savings"]["matched"] == 1
    data = query(authenticated_client, terms=["excitel"], type="expense").get_json()
    assert data["rows"][0]["account"] == "Test Saving" and data["rows"][0]["type"] == "expense"
    assert query(authenticated_client, account_name="test sav").get_json()["matched"] == 1
    # Bank-only questions are unchanged and carry no savings section.
    assert "savings" not in query(authenticated_client, account_kind="bank").get_json()


@pytest.mark.parametrize("params,message", [
    ({"terms": ["x"]}, "2 to 40"),
    ({"terms": ["ab", "cd", "ef", "gh", "ij", "kl", "mn"]}, "at most 6"),
    ({"must_match": ["ab", "cd", "ef", "gh"]}, "at most 3"),
    ({"must_match": ["x"]}, "2 to 40"),
    ({"must_match": ["ab|x"]}, "2 to 40"),
    ({"must_match": ["aa|bb|cc|dd|ee"]}, "at most 4 alternatives"),
    ({"type": "refund"}, "type must be"),
    ({"group_by": "user_id"}, "group_by must be"),
    ({"sort": "id; drop table"}, "sort must be"),
    ({"limit": 31}, "limit must be between"),
    ({"limit": "ten"}, "whole number"),
    ({"min_amount": "abc"}, "must be a number"),
    ({"min_amount": 10, "max_amount": 5}, "min_amount must be at most"),
    ({"start_date": "2026-11-30", "end_date": "2026-11-01"}, "Start date"),
    ({"start_date": "30-11-2026"}, "YYYY-MM-DD"),
    ({"money_movement": "maybe"}, "money_movement must be"),
    ({"account_name": "x" * 61}, "account_name"),
])
def test_invalid_parameters_are_400(authenticated_client, params, message):
    response = query(authenticated_client, **params)
    assert response.status_code == 400 and message in response.get_json()["error"]
