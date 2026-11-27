"""A scripted stand-in for Flask's GET endpoints (no network)."""

from app.assistant.flask_data import DataUnavailable


class FakeFlask:
    def __init__(self, routes=None, fail=()):
        self.routes = routes or {}
        self.fail = set(fail)
        self.calls = []

    async def get(self, path, token, params=None):
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        self.calls.append((path, token, params))
        if path in self.fail:
            raise DataUnavailable()
        value = self.routes.get(path)
        return value(params) if callable(value) else value


def bank_txn(i, date, amount, category="Food", kind="expense", description="Swiggy order"):
    return {"id": i, "amount": amount, "description": description, "category": category,
            "transaction_type": kind, "date": f"{date} 10:00:00", "bank_balance_after": 0}


def card_txn(i, date, amount, category="Shopping", kind="expense", description="Amazon"):
    return {"id": i, "amount": amount, "description": description, "category": category,
            "transaction_type": kind, "is_payment": kind == "payment", "is_billed": False,
            "date": f"{date} 09:00:00"}


# What Flask's GET /transactions/query returns (shape from app/transactions/transaction_query.py).
QUERY_RESULT = {
    "query": {"terms": [], "account_kind": "all", "money_movement": "exclude", "group_by": "category",
              "sort": "date_desc", "limit": 3},
    "matched": 4,
    "totals": [{"type": "expense", "count": 3, "total": 4000.0, "average": 1333.33, "smallest": 1000.0,
                "largest": 2000.0, "first_date": "2026-09-01", "last_date": "2026-11-20"},
               {"type": "income", "count": 1, "total": 50000.0, "average": 50000.0, "smallest": 50000.0,
                "largest": 50000.0, "first_date": "2026-11-01", "last_date": "2026-11-01"}],
    "money_movement": {"mode": "exclude", "categories": ["transfer"], "excluded_count": 2, "excluded_total": 23000.0},
    "groups": {"by": "category", "type": "expense", "groups_total": 2, "other_total": 0.0,
               "rows": [{"key": "Food", "count": 2, "total": 3000.0, "share_pct": 75.0},
                        {"key": "Rent", "count": 1, "total": 1000.0, "share_pct": 25.0}]},
    "rows": [{"id": 101, "date": "2026-11-20", "type": "expense", "account": "HDFC Savings", "category": "Food",
              "description": "Swiggy order " + "x" * 100, "amount": 2000.0}],
}
GOA_RESULT = {
    "query": {"terms": ["goa", "trip"]}, "matched": 2,
    "totals": [{"type": "expense", "count": 2, "total": 4300.0, "average": 2150.0, "smallest": 1800.0,
                "largest": 2500.0, "first_date": "2026-01-05", "last_date": "2026-01-06"}],
    "term_matches": [{"term": "goa", "count": 2}, {"term": "trip", "count": 2}],
    "rows": [{"id": 201, "date": "2026-01-06", "type": "expense", "account": "HDFC Savings", "category": "Repayment",
              "description": "Goa trip share", "amount": 2500.0}],
}
# One trip listed in full (matched == rows), for picking rows by meaning.
TRIP_RESULT = {
    "query": {"must_match": ["goa"]}, "matched": 4,
    "totals": [{"type": "expense", "count": 4, "total": 3530.0, "average": 882.5, "smallest": 120.0,
                "largest": 2500.0, "first_date": "2026-01-01", "last_date": "2026-01-03"}],
    "rows": [{"id": 301, "date": "2026-01-03", "type": "expense", "account": "Card", "category": "Travel",
              "description": "goa trip 31st bf", "amount": 620.0},
             {"id": 302, "date": "2026-01-02", "type": "expense", "account": "Card", "category": "Travel",
              "description": "goa trip juice", "amount": 290.0},
             {"id": 303, "date": "2026-01-02", "type": "expense", "account": "Card", "category": "Travel",
              "description": "goa trip petrol", "amount": 120.0},
             {"id": 304, "date": "2026-01-01", "type": "expense", "account": "Bank", "category": "Repayment",
              "description": "friend - goa trip share", "amount": 2500.0}],
}
EMPTY_RESULT = {"query": {"terms": ["zzz"]}, "matched": 0, "totals": []}


def _query(params):
    terms = params.get("terms") or []
    if params.get("must_match") == ["goa"] and not terms:
        return TRIP_RESULT
    if len(params.get("must_match") or []) > 1:
        return EMPTY_RESULT                      # no row has all the words
    if params.get("must_match") == ["goa|trip"]:
        return GOA_RESULT
    if "zzz" in terms:
        return EMPTY_RESULT
    return GOA_RESULT if "goa" in terms else QUERY_RESULT


def sample_flask():
    bank_pages = {
        None: {"transactions": [bank_txn(1, "2026-11-20", 450.0),
                                bank_txn(2, "2026-11-02", 50000, "Salary", "income", "Salary")],
               "has_more": True, "next_cursor": "c1"},
        "c1": {"transactions": [bank_txn(3, "2026-10-15", 1200.5, "Rent", description="Rent October")],
               "has_more": False, "next_cursor": None},
    }
    card_pages = {1: {"transactions": [card_txn(10, "2026-11-10", 2999.0), card_txn(11, "2026-09-01", 799.0),
                                       card_txn(12, "2026-11-12", 5000.0, "Payment", "payment", "Bill paid")],
                      "total_pages": 1}}
    return FakeFlask({
        "/banks/dropdown": [{"id": 1, "name": "HDFC Savings"}],
        "/banks": [{"id": 1, "name": "HDFC Savings", "user_id": 42, "balance": 81234.5}],
        "/credit_cards": [{"id": 7, "name": "SBI Card", "user_id": 42, "limit": 100000, "available_limit": 92000,
                           "used": 8000, "billed_unpaid": 3000, "unbilled_spends": 5000, "total_payable": 8000}],
        "/savings": [{"id": 3, "name": "Emergency", "bank_name": "HDFC Savings", "balance": 150000}],
        "/dashboard/summary": {"total_assets": 250000.0, "total_bank_balance": 81234.5, "total_savings": 150000.0,
                               "total_credit_card_debt": 8000.0, "net_worth": 473234.5},
        "/dashboard/asset-allocation": [{"name": "Stocks", "value": 150000.0}, {"name": "Gold", "value": 100000.0}],
        "/banks/1/transactions": lambda p: bank_pages[p.get("cursor")],
        "/credit_cards/7/transactions": lambda p: card_pages[p["page"]],
        "/transactions/query": _query,
    })
