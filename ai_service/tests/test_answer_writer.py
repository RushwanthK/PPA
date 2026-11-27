"""Code writes the answer (Nov 27): templates filled from the query and its result."""

from datetime import date

from app.assistant.answer_writer import inr, nice_date, period, searched, write_answer
from app.assistant.tools import MATCHING, DataBlock, Table


def test_rupees_use_indian_grouping():
    assert inr(16143.29) == "₹16,143.29"
    assert inr(1234567.5) == "₹12,34,567.50"
    assert inr(300) == "₹300" and inr(-2000.0) == "₹2,000" and inr(0.999) == "₹1"


def test_dates_periods_and_search_words():
    assert nice_date("2026-03-15 10:00:00") == "15 Mar 2026" and nice_date(date(2025, 7, 1)) == "1 Jul 2025"
    assert period({}) == "all time"
    assert period({"start_date": date(2025, 7, 1)}) == "1 Jul 2025 to today"
    assert period({"start_date": date(2026, 1, 1), "end_date": date(2026, 1, 31)}) == "1 Jan 2026 to 31 Jan 2026"
    assert searched({"must_match": ["shree|shreya"]}) == "'shree' or 'shreya'"
    assert searched({"must_match": ["goa"], "terms": ["cab", "auto"]}) == "'goa' and any of 'cab', 'auto'"
    assert searched({"terms": ["zomato"]}) == "'zomato'"


def query_block(facts, rows=None, **meta):
    block = DataBlock("Transactions", {"query": "q", **facts}, meta={"kind": "query", "group_by": "none",
                                                                      "sort": "date_desc", "limit": 10, **meta})
    if rows:
        block.tables.append(Table(f"{MATCHING} (newest first)", list(rows[0]), [list(r.values()) for r in rows]))
    return block


def test_how_much_for_one_merchant():
    block = query_block({"matched": 52, "expense_count": 52, "expense_total": 16143.29,
                         "expense_first_date": "2024-02-01", "expense_last_date": "2026-11-20"},
                        terms=["zomato"], type="expense")
    assert write_answer([block]) == ("You spent ₹16,143.29 in 52 transactions matching 'zomato' (all time), "
                                     "from 1 Feb 2024 to 20 Nov 2026.")


def test_savings_rows_get_the_double_counting_note():
    block = query_block({"matched": 3, "expense_count": 3, "expense_total": 1499.0, "savings_rows": 1,
                         "savings_transfers_left_out_count": 2, "savings_transfers_left_out_total": 100409.0,
                         "savings_deposits_left_out_count": 1, "savings_deposits_left_out_total": 2000.0},
                        terms=["recharge"])
    assert write_answer([block]) == (
        "You spent ₹1,499 in 3 transactions matching 'recharge' (all time). Includes 1 savings account withdrawal; "
        "money moved between your own accounts may be counted twice. Left out 1 savings deposit (₹2,000): money "
        "put into savings is not income. Left out 2 savings transfers (₹1,00,409).")


def test_latest_transaction():
    rows = [{"id": 9, "date": "2026-03-15", "category": "Personal", "description": "haircut", "amount": 300.0}]
    block = query_block({"matched": 4, "expense_count": 4, "expense_total": 1200.0}, rows,
                        terms=["haircut"], type="expense", limit=1)
    assert write_answer([block]) == ("Your latest expense transaction matching 'haircut' (all time) was on "
                                     "15 Mar 2026: ₹300, 'haircut'. 4 transactions matched in all.")


def test_nothing_found_suggests_another_word():
    block = query_block({"matched": 0}, must_match=["shree|shreya"], type="expense",
                        start_date=date(2025, 7, 1))
    assert write_answer([block]) == ("No expense transactions matching 'shree' or 'shreya' (1 Jul 2025 to today). "
                                     "A shorter form of the word, or a different spelling, may find them.")


def test_picked_rows_replace_the_list_they_came_from():
    listing = query_block({"matched": 23, "pick": "...", "all_rows_listed": True}, must_match=["goa"],
                          type="expense", pick_kind="travel")
    picked = DataBlock("Picked by meaning: travel on the Goa trip", {
        "picked": "travel on the Goa trip", "picked_count": 5, "picked_total": 2350.0, "picked_types": "as filtered",
        "rows_considered_count": 23, "not_counted_count": 18, "not_counted_total": 37543.0},
        meta={"kind": "picked", "source": listing.meta})
    assert write_answer([listing, picked], "Left out lump sums paid to friends.") == (
        "You spent ₹2,350 on travel on the Goa trip: 5 of the 23 transactions matching 'goa' (all time). "
        "Not counted: 18 transactions (₹37,543), listed below. Note: Left out lump sums paid to friends.")


def test_income_pick_and_none_fit():
    source = {"kind": "query", "type": "income", "must_match": ["solo|solomon"]}
    picked = DataBlock("Picked", {"picked": "repayment for the Goa trip", "picked_count": 1, "picked_total": 1000.0,
                                  "rows_considered_count": 3, "not_counted_count": 2, "not_counted_total": 500.0},
                       meta={"kind": "picked", "source": source})
    assert write_answer([picked]).startswith("You received ₹1,000 (repayment for the Goa trip): 1 of the 3")
    picked.facts.update(picked_count=0, picked_total=0)
    assert write_answer([picked]) == ("None of the 3 transactions matching 'solo' or 'solomon' (all time) looked "
                                      "like repayment for the Goa trip.")


def test_balances_and_accounts():
    summary = DataBlock("Financial summary (now)", {"net_worth": 473234.5, "total_bank_balance": 81234.5,
                                                    "total_savings": 150000, "total_assets": 250000,
                                                    "total_credit_card_debt": 8000}, meta={"kind": "summary"})
    accounts = DataBlock("Accounts (now)", {"bank_accounts": 1, "total_bank_balance": 81234.5},
                         meta={"kind": "accounts"})
    assert write_answer([summary, accounts]) == (
        "Your net worth is ₹4,73,234.50: bank balance ₹81,234.50, savings ₹1,50,000, assets ₹2,50,000, "
        "credit card debt ₹8,000. Bank balance: ₹81,234.50 across 1 account.")
