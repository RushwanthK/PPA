"""Finance tools: argument validation and how results become facts and tables (no network)."""

import json
from datetime import date

import pytest

from app.assistant.tools import TOOL_SCHEMAS, TOOLS, AccountsArgs, NoArgs, QueryArgs, ToolInputError, parse_call
from tests.fake_flask import sample_flask

TOKEN = "user-token"


def test_schemas_are_clean_function_definitions():
    names = {s["function"]["name"] for s in TOOL_SCHEMAS}
    assert names == set(TOOLS) == {"get_financial_summary", "get_asset_allocation", "list_accounts",
                                   "query_transactions", "add_up_transactions"}
    for s in TOOL_SCHEMAS:
        params = s["function"]["parameters"]
        assert s["type"] == "function" and params["type"] == "object" and "title" not in params


@pytest.mark.parametrize("name,args,error", [
    ("drop_tables", "{}", "unknown tool"),
    ("get_spending_by_category", "{}", "unknown tool"),          # removed on Nov 26
    ("query_transactions", "{not json", "not valid JSON"),
    ("get_financial_summary", '{"sql": "select 1"}', "Extra inputs"),
    ("query_transactions", '{"sql": "select * from user"}', "Extra inputs"),
    ("query_transactions", '{"start_date": "2026-11-30", "end_date": "2026-11-01"}', "start_date must be"),
    ("query_transactions", '{"min_amount": 500, "max_amount": 100}', "min_amount must be"),
    ("query_transactions", '{"min_amount": -1}', "min_amount"),
    ("query_transactions", json.dumps({"terms": ["a"]}), "terms"),
    ("query_transactions", json.dumps({"terms": ["x" * 41]}), "terms"),
    ("query_transactions", '{"limit": 31}', "limit"),
    ("add_up_transactions", '{"ids": [1], "label": "f"}', "label"),   # empty ids are allowed since Nov 27 (none fit)
    ("add_up_transactions", '{"ids": [1], "label": "food", "amount": 5}', "Extra inputs"),
    ("query_transactions", '{"group_by": "user_id"}', "group_by"),
    ("query_transactions", '{"sort": "id desc; drop table"}', "sort"),
    ("query_transactions", '{"type": "transfer"}', "type"),
])
def test_invalid_calls_are_rejected(name, args, error):
    with pytest.raises(ToolInputError, match=error):
        parse_call(name, args)


def test_valid_call_is_parsed():
    tool, args = parse_call("query_transactions", '{"terms": [" Swiggy "], "start_date": "2026-11-01"}')
    assert tool.name == "query_transactions"
    assert args.terms == ["Swiggy"] and args.start_date == date(2026, 11, 1) and args.limit == 10


@pytest.mark.parametrize("args,expected", [
    (QueryArgs(), "exclude"),                                  # overall spending: transfers left out
    (QueryArgs(terms=["goa"]), "include"),                     # a search keeps everything that matches
    (QueryArgs(money_movement="only"), "only"),
    (QueryArgs(terms=["goa"], money_movement="exclude"), "exclude"),
])
def test_money_movement_auto_rule(args, expected):
    assert args.resolved_money_movement() == expected


def test_query_is_described_in_plain_words():
    args = QueryArgs(terms=["goa", "trip"], type="expense", start_date=date(2026, 1, 1), min_amount=500,
                     group_by="category", sort="amount_desc", limit=5)
    assert args.describe() == ("money out (expenses) · words: goa, trip · 2026-01-01 to today · at least 500 · "
                               "transfers, card bills and investments included · grouped by category · "
                               "up to 5 rows, largest first")
    assert "all time (no date filter)" in QueryArgs().describe()
    combined = QueryArgs(must_match=["goa"], terms=["food", "drinks"], type="expense")
    assert "must contain: goa · any of: food, drinks" in combined.describe()
    assert combined.resolved_money_movement() == "include"


async def test_must_match_is_sent_to_flask():
    flask = sample_flask()
    await TOOLS["query_transactions"].run(flask, TOKEN, QueryArgs(must_match=["zzz"], terms=["food"]))
    # The whole "zzz" set is checked first (nothing), then the word search runs.
    assert [(c[2].get("must_match"), c[2].get("terms")) for c in flask.calls] == [(["zzz"], None), (["zzz"], ["food"])]


async def test_financial_summary():
    block = await TOOLS["get_financial_summary"].run(sample_flask(), TOKEN, NoArgs())
    assert block.facts["net_worth"] == 473234.5 and block.facts["total_credit_card_debt"] == 8000.0


async def test_list_accounts_drops_internal_fields():
    block = await TOOLS["list_accounts"].run(sample_flask(), TOKEN, AccountsArgs())
    assert block.facts == {"bank_accounts": 1, "total_bank_balance": 81234.5, "credit_cards": 1,
                           "total_credit_card_payable": 8000.0, "savings_accounts": 1, "total_savings": 150000.0}
    assert "user_id" not in block.to_json() and '"id"' not in block.to_json()


async def test_query_is_one_call_with_only_the_set_parameters():
    flask = sample_flask()
    args = QueryArgs(terms=["uber", "ola"], type="expense", account_kind="credit_card",
                     start_date=date(2026, 2, 1), end_date=date(2026, 2, 28), limit=20)
    await TOOLS["query_transactions"].run(flask, TOKEN, args)
    assert flask.calls == [("/transactions/query", TOKEN, {
        "terms": ["uber", "ola"], "type": "expense", "account_kind": "credit_card",
        "start_date": "2026-02-01", "end_date": "2026-02-28", "money_movement": "include",
        "group_by": "none", "sort": "date_desc", "limit": 20})]


async def test_result_becomes_facts_and_tables():
    block = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(group_by="category", limit=3))
    f = block.facts
    assert f["matched"] == 4 and f["expense_total"] == 4000.0 and f["income_total"] == 50000.0
    assert f["expense_last_date"] == "2026-11-20" and f["expense_largest"] == 2000.0
    assert f["left_out_money_movement_total"] == 23000.0 and f["left_out_money_movement_count"] == 2
    assert f["groups_total"] == 2 and "other_groups_amount" not in f
    assert [t.title for t in block.tables] == ["Expense by category (parts of the expense total)",
                                               "Matching transactions (newest first)"]
    assert block.tables[0].rows[0] == ["Food", 2, 3000.0, 75.0]
    assert block.tables[1].columns[0] == "id" and block.facts["all_rows_listed"] is False   # 1 of 4 listed
    row = block.tables[1].rows[0]
    assert row[0] == 101 and row[1] == "2026-11-20" and len(row[5]) <= 80 and row[6] == 2000.0


async def test_savings_rows_and_left_out_savings_transfers_become_facts():
    from tests.fake_flask import QUERY_RESULT, FakeFlask
    result = {**QUERY_RESULT, "savings": {"matched": 2, "transfers_left_out": 3, "transfers_left_out_total": 7500.0,
                                          "deposits_left_out": 4, "deposits_left_out_total": 2500.0}}
    args = QueryArgs(account_kind="savings", limit=0)
    block = await TOOLS["query_transactions"].run(FakeFlask({"/transactions/query": result}), TOKEN, args)
    assert block.facts["savings_rows"] == 2
    assert (block.facts["savings_transfers_left_out_count"], block.facts["savings_transfers_left_out_total"]) == \
        (3, 7500.0)
    assert (block.facts["savings_deposits_left_out_count"], block.facts["savings_deposits_left_out_total"]) ==         (4, 2500.0)
    assert "savings accounts" in block.facts["query"]


async def test_no_matching_transactions_is_said_plainly():
    block = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(terms=["zzz"]))
    assert block.facts["matched"] == 0 and "No transactions match" in block.facts["note"]
    assert block.tables == []



# ---- Picking rows by meaning ---------------------------------------------------------------

async def trip_block():
    return await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(must_match=["goa"], limit=30))


async def test_picked_rows_are_added_up_by_code_with_what_was_left_out():
    from app.assistant.tools import PickArgs, add_up_picked
    trip = await trip_block()
    assert trip.facts["all_rows_listed"] is True
    block = add_up_picked([trip], PickArgs(ids=[301, 302, 302], label="food and drinks on the Goa trip"))
    assert block.facts["picked_total"] == 910.0 and block.facts["picked_count"] == 2   # duplicate id counted once
    assert block.facts["rows_considered_count"] == 4 and block.facts["picked_types"] == "expense"
    assert [r[0] for r in block.tables[0].rows] == [301, 302]
    assert block.tables[1].title == "Not counted" and [r[0] for r in block.tables[1].rows] == [303, 304]


async def test_only_rows_from_a_complete_list_can_be_picked():
    from app.assistant.tools import PickArgs, PickError, add_up_picked
    partial = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(limit=3))  # 1 of 4 listed
    with pytest.raises(PickError, match="no complete list"):
        add_up_picked([partial], PickArgs(ids=[101], label="food"))
    with pytest.raises(PickError, match="not in the listed rows"):
        add_up_picked([await trip_block()], PickArgs(ids=[301, 999], label="food"))



def test_extra_words_are_dropped_instead_of_failing():
    _, args = parse_call("query_transactions", json.dumps({"terms": [f"w{i}" for i in range(8)],
                                                           "must_match": ["aa", "bb", "cc", "dd"]}))
    assert args.terms == ["w0", "w1", "w2", "w3", "w4", "w5"] and args.must_match == ["aa", "bb", "cc"]
    schema = next(s for s in TOOL_SCHEMAS if s["function"]["name"] == "query_transactions")
    assert "maxItems" not in json.dumps(schema["function"]["parameters"]["properties"]["terms"])



async def test_the_model_gets_a_short_version_of_picked_rows():
    from app.assistant.tools import PickArgs, add_up_picked
    block = add_up_picked([await trip_block()], PickArgs(ids=[301, 302], label="food"))
    brief = json.loads(block.for_model())
    assert brief["facts"]["picked_total"] == 910.0
    assert brief["counted"] == ["goa trip 31st bf", "goa trip juice"]
    assert brief["not_counted"] == ["goa trip petrol", "friend - goa trip share"]
    assert len(block.for_model()) < len(block.to_json())
    trip = await trip_block()
    assert trip.for_model() == trip.to_json()          # other results go to the model in full



async def test_alternatives_sent_as_must_match_are_rerun_as_any_of():
    flask = sample_flask()
    block = await TOOLS["query_transactions"].run(flask, TOKEN, QueryArgs(must_match=["goa", "trip"], terms=["food"],
                                                                          type="expense"))
    # Whole-set check (AND, then as alternatives: 1 of 2 rows listed, so not pickable), then the
    # word search: AND finds nothing, rerun as alternatives with the other words kept.
    assert [c[2].get("must_match") for c in flask.calls] == [["goa", "trip"], ["goa|trip"],
                                                             ["goa", "trip"], ["goa|trip"]]
    assert flask.calls[3][2]["terms"] == ["food"]
    assert block.facts["matched"] == 2 and "No row contains all of goa, trip" in block.facts["note"]
    assert "must contain: goa or trip · any of: food" in block.facts["query"]


async def test_empty_result_with_several_must_match_words_explains_and_vs_or():
    block = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(must_match=["zzz", "yyy"],
                                                                                    terms=["zzz"]))
    # Rerun as alternatives found nothing either: both notes, in order.
    assert block.facts["matched"] == 0
    assert block.facts["note"].startswith("No row contains all of zzz, yyy") and "No transactions match" in block.facts["note"]
    one = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(terms=["zzz"]))
    assert one.facts["note"].startswith("No transactions match")



async def test_pick_kind_lists_rows_and_hides_totals():
    flask = sample_flask()
    block = await TOOLS["query_transactions"].run(flask, TOKEN, QueryArgs(must_match=["goa"], pick_kind="food"))
    assert flask.calls[0][2]["limit"] == 30
    assert block.facts["all_rows_listed"] is True and "Totals hidden" in block.facts["pick"]
    assert not any(k.endswith("_total") for k in block.facts)          # nothing to misquote
    assert "rows listed to pick: food" in block.facts["query"]

    partial = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(pick_kind="food"))
    assert partial.facts["all_rows_listed"] is False and "Too many rows (4)" in partial.facts["pick"]
    assert "expense_total" not in partial.facts



@pytest.mark.parametrize("question,sent,expected", [
    ("gifts for shree or Shreya from july 2025", ["shree", "shreya"], ["shree|shreya"]),
    ("gifts for Shreya or Shree", ["shree", "shreya"], ["shree|shreya"]),
    ("anything for shree, rakshitha or skanda?", ["shree", "rakshitha", "skanda"], ["shree|rakshitha|skanda"]),
    ("money for Shree or Shreya on the goa trip", ["goa", "shree", "shreya"], ["goa", "shree|shreya"]),
    ("food in goa trip with solo", ["goa", "solo"], ["goa", "solo"]),           # "with" is AND: unchanged
    ("hotel and food in goa", ["goa", "hotel"], ["goa", "hotel"]),
    ("shree or shreya", ["shre"], ["shre"]),                                    # one entry: nothing to merge
])
def test_or_in_the_question_is_or_in_the_query(question, sent, expected):
    from app.assistant.tools import merge_or_alternatives
    assert merge_or_alternatives(question, QueryArgs(must_match=sent)).must_match == expected



async def test_kind_inside_a_small_named_set_is_listed_whole_for_picking():
    flask = sample_flask()
    block = await TOOLS["query_transactions"].run(flask, TOKEN, QueryArgs(must_match=["goa"], terms=["cab", "train"],
                                                                          type="expense"))
    assert len(flask.calls) == 1 and "terms" not in flask.calls[0][2] and flask.calls[0][2]["limit"] == 30
    assert block.facts["all_rows_listed"] is True and "picked by meaning" in block.facts["pick"]
    assert "cab, train" in block.facts["pick"] and "expense_total" not in block.facts



async def test_rows_listed_for_picking_are_slimmer():
    block = await TOOLS["query_transactions"].run(sample_flask(), TOKEN,
                                                  QueryArgs(must_match=["goa"], pick_kind="food", type="expense"))
    assert block.tables[-1].columns == ["id", "date", "category", "description", "amount"]
    full = await TOOLS["query_transactions"].run(sample_flask(), TOKEN, QueryArgs(limit=3))
    assert full.tables[-1].columns == ["id", "date", "type", "account", "category", "description", "amount"]
