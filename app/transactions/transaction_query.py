"""GET /transactions/query: precise, read-only questions over the user's transactions.

Built for the AI service's "My data" mode (fine-tuning phase, Nov 26, 2026), and usable
by any client. The AI model does not write SQL. It fills in a small, structured query
(search words, type, dates, amounts, grouping, sort, row limit); this endpoint validates
every parameter and turns it into parameterised SQLAlchemy, always filtered to the
logged-in user. So a precise question ("when did I last pay for a haircut, and how
much?") gets an exact answer, and nothing the model writes is ever run as SQL.

It replaced GET /transactions/summary (Nov 25), which returned one fixed summary and
could not answer "my last transaction" or list matching rows.

Scope: bank and credit card transactions only (savings, asset and transfer-table rows
are excluded). Amounts are positive (card expenses are stored as negative amounts).
Dates are India time.

Update (Nov 27): savings transactions are included too (account_kind "savings", and in
"all"), because the owner also spends from savings. Savings rows record "withdrawal" and
"deposit", so they are mapped: withdrawal = money out (expense), deposit = money in
(income). Savings rows whose category is a money-movement category (transfers, card
bills, gold, ETF ...) are always left out, whatever money_movement says: they move money
between the user's own accounts. Other savings rows may still mirror a bank row (a
deposit of cash also entered as bank income), so the response counts the savings rows
and the client can say that such money may be counted twice. Asset and transfer-table
rows are still excluded.

Update (Nov 27, owner's decision): savings DEPOSITS are left out of totals too. Most are
the owner's own money moved in (cash, hundi, a trip fund, card refunds), not income. They
count as money movement: money_movement=only returns them ("how much did I put into
savings?"); every other mode leaves them out and reports how many.

Money movement: transfers between your own accounts, credit card bill payments and
investments are recorded as "expense" rows in PPA but are not spending, and counting
them double-counts card spends (once on the card, again when the bill is paid). The
categories listed in MONEY_MOVEMENT_CATEGORIES (comma-separated, case-insensitive;
default below) can be excluded, included or queried on their own.
"""

import os
from datetime import datetime, timedelta

import pytz
from flask import Blueprint, current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, jwt_required
from sqlalchemy import and_, case, func, or_

from ..models import Bank, CreditCard, Saving, Transaction

transaction_query_routes = Blueprint("transaction_query_routes", __name__)

IST = pytz.timezone("Asia/Kolkata")

# Bank and card transactions share one table (single-table inheritance); their
# account columns are mapped on the subclasses, so refer to the table columns.
BANK_ID = Transaction.__table__.c.bank_id
CARD_ID = Transaction.__table__.c.credit_card_id
SAVING_ID = Transaction.__table__.c.saving_id
SAVINGS = "saving_transaction"

TYPES_BY_KIND = {
    "bank": ("bank_transaction",),
    "credit_card": ("credit_card_transaction",),
    "savings": (SAVINGS,),
    "all": ("bank_transaction", "credit_card_transaction", SAVINGS),
}
# Savings rows say withdrawal / deposit; everything else says expense / income / payment.
KIND = case((Transaction.transaction_type == "withdrawal", "expense"),
            (Transaction.transaction_type == "deposit", "income"),
            else_=Transaction.transaction_type)
ALLOWED_TYPES = ("expense", "income", "payment")
GROUP_BY = ("none", "category", "month", "account", "description")
SORTS = ("date_desc", "date_asc", "amount_desc", "amount_asc")
MONEY_MOVEMENT_MODES = ("include", "exclude", "only")

MAX_TERMS = 6
MAX_MUST_MATCH = 3
TERM_CHARS = (2, 40)
MAX_TEXT = 60
MAX_ROWS = 30   # 20 until Nov 26; 30 so one trip or month can be listed whole and picked from
DEFAULT_ROWS = 10
MAX_GROUPS = 12
DESCRIPTION_CHARS = 80

DEFAULT_MONEY_MOVEMENT = ("transfer", "self", "self transfer", "cc bill", "cc bills", "credit card bill",
                          "payment", "asset transfer", "investment", "investments", "asset", "assets",
                          "balancing")


def money_movement_categories():
    raw = current_app.config.get("MONEY_MOVEMENT_CATEGORIES") or os.environ.get("MONEY_MOVEMENT_CATEGORIES")
    if raw:
        names = [name.strip().lower() for name in raw.split(",")]
        return tuple(sorted({name for name in names if name}))
    return DEFAULT_MONEY_MOVEMENT


def _round(value):
    return round(float(value or 0), 2)


def _ist_day_start_utc(day):
    """IST midnight of `day` as naive UTC (the stored-timestamp convention)."""
    local = IST.localize(datetime.combine(day, datetime.min.time()))
    return local.astimezone(pytz.UTC).replace(tzinfo=None)


def _ist_day(moment):
    return pytz.UTC.localize(moment).astimezone(IST).strftime("%Y-%m-%d") if moment else None


def _choice(args, name, allowed, default):
    value = (args.get(name) or default).strip().lower()
    if value not in allowed:
        raise ValueError(f"{name} must be one of: {', '.join(allowed)}")
    return value


def _amount(args, name):
    raw = args.get(name)
    if raw in (None, ""):
        return None
    try:
        value = float(raw)
    except ValueError:
        raise ValueError(f"{name} must be a number") from None
    if not 0 <= value <= 1e12:
        raise ValueError(f"{name} must be between 0 and 1000000000000")
    return value


MAX_ALTERNATIVES = 4


def _words(args, name, limit, *, alternatives=False):
    """alternatives: an entry may be "shree|shreya" (either may match). Each part is checked."""
    words = []
    for raw in args.getlist(name):
        parts = [" ".join(part.split()) for part in (raw.split("|") if alternatives else [raw])]
        parts = [part for part in parts if part]
        if not parts:
            continue
        if len(parts) > MAX_ALTERNATIVES:
            raise ValueError(f"at most {MAX_ALTERNATIVES} alternatives in one {name} entry")
        for part in parts:
            if not TERM_CHARS[0] <= len(part) <= TERM_CHARS[1]:
                raise ValueError(f"each {name} word must be {TERM_CHARS[0]} to {TERM_CHARS[1]} characters")
        word = "|".join(parts)
        if word.lower() not in (w.lower() for w in words):
            words.append(word)
    if len(words) > limit:
        raise ValueError(f"at most {limit} {name} words")
    return words


def parse_query(args):
    """Validate every parameter. Raises ValueError with a message for the caller.

    terms: ANY of them may match. must_match: EVERY one must match (added Nov 26 for
    questions like "food in the Goa trip": must_match=goa, terms=food, drinks, ...). A
    must_match entry may list alternatives, "shree|shreya": (shree OR shreya) AND ..."""
    terms = _words(args, "terms", MAX_TERMS)
    must_match = _words(args, "must_match", MAX_MUST_MATCH, alternatives=True)

    transaction_type = (args.get("type") or "").strip().lower() or None
    if transaction_type and transaction_type not in ALLOWED_TYPES:
        raise ValueError("type must be expense, income or payment")

    account_name = (args.get("account_name") or "").strip()
    if len(account_name) > MAX_TEXT:
        raise ValueError(f"account_name must be at most {MAX_TEXT} characters")

    try:
        start = datetime.strptime(args["start_date"], "%Y-%m-%d").date() if args.get("start_date") else None
        end = datetime.strptime(args["end_date"], "%Y-%m-%d").date() if args.get("end_date") else None
    except ValueError:
        raise ValueError("Dates must use YYYY-MM-DD format") from None
    if start and end and start > end:
        raise ValueError("Start date must be on or before end date")

    min_amount, max_amount = _amount(args, "min_amount"), _amount(args, "max_amount")
    if min_amount is not None and max_amount is not None and min_amount > max_amount:
        raise ValueError("min_amount must be at most max_amount")

    try:
        limit = int(args.get("limit", DEFAULT_ROWS))
    except ValueError:
        raise ValueError("limit must be a whole number") from None
    if not 0 <= limit <= MAX_ROWS:
        raise ValueError(f"limit must be between 0 and {MAX_ROWS}")

    return {
        "terms": terms,
        "must_match": must_match,
        "type": transaction_type,
        "account_kind": _choice(args, "account_kind", tuple(TYPES_BY_KIND), "all"),
        "account_name": account_name or None,
        "start_date": start,
        "end_date": end,
        "min_amount": min_amount,
        "max_amount": max_amount,
        "money_movement": _choice(args, "money_movement", MONEY_MOVEMENT_MODES, "include"),
        "group_by": _choice(args, "group_by", GROUP_BY, "none"),
        "sort": _choice(args, "sort", SORTS, "date_desc"),
        "limit": limit,
    }


def _like(text):
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _term_match(term):
    pattern = _like(term)
    return or_(Transaction.description.ilike(pattern, escape="\\"),
               Transaction.category.ilike(pattern, escape="\\"))


def _moving():
    return func.lower(func.trim(func.coalesce(Transaction.category, ""))).in_(money_movement_categories())


def _savings_transfer():
    """Savings rows that only move money between the user's own accounts: always left out."""
    return and_(Transaction.type == SAVINGS, _moving())


def _savings_deposit():
    """Money put into savings: money movement, not income (owner's decision, Nov 27)."""
    return and_(Transaction.type == SAVINGS, Transaction.transaction_type == "deposit")


def _movement():
    return or_(_moving(), _savings_deposit())


def _conditions(user_id, q, *, with_money_movement=True, savings_rule=True):
    """Every filter is applied in SQL, and the query is always scoped to the user."""
    amount = func.abs(Transaction.amount)
    conditions = [Transaction.user_id == user_id, Transaction.type.in_(TYPES_BY_KIND[q["account_kind"]])]
    if savings_rule:
        conditions.append(~_savings_transfer())
        if q["money_movement"] != "only":
            conditions.append(~_savings_deposit())
    if q["terms"]:
        conditions.append(or_(*[_term_match(t) for t in q["terms"]]))
    for entry in q["must_match"]:           # every entry must match; "a|b" = either a or b
        conditions.append(or_(*[_term_match(part) for part in entry.split("|")]))
    if q["type"]:
        conditions.append(KIND == q["type"])
    if q["start_date"]:
        conditions.append(Transaction.date >= _ist_day_start_utc(q["start_date"]))
    if q["end_date"]:
        conditions.append(Transaction.date < _ist_day_start_utc(q["end_date"] + timedelta(days=1)))
    if q["min_amount"] is not None:
        conditions.append(amount >= q["min_amount"])
    if q["max_amount"] is not None:
        conditions.append(amount <= q["max_amount"])
    if q["account_name"]:
        pattern = _like(q["account_name"])
        bank_ids = Bank.query.with_entities(Bank.id).filter(Bank.user_id == user_id,
                                                            Bank.name.ilike(pattern, escape="\\"))
        card_ids = CreditCard.query.with_entities(CreditCard.id).filter(
            CreditCard.user_id == user_id, CreditCard.name.ilike(pattern, escape="\\"))
        saving_ids = Saving.query.with_entities(Saving.id).filter(Saving.user_id == user_id,
                                                                  Saving.name.ilike(pattern, escape="\\"))
        conditions.append(or_(
            and_(Transaction.type == "bank_transaction", BANK_ID.in_(bank_ids.scalar_subquery())),
            and_(Transaction.type == "credit_card_transaction", CARD_ID.in_(card_ids.scalar_subquery())),
            and_(Transaction.type == SAVINGS, SAVING_ID.in_(saving_ids.scalar_subquery())),
        ))
    if with_money_movement and q["money_movement"] != "include":
        conditions.append(_movement() if q["money_movement"] == "only" else ~_movement())
    return conditions


def run_query(user_id, q):
    amount = func.abs(Transaction.amount)
    query = Transaction.query.filter(*_conditions(user_id, q))
    category = func.coalesce(func.nullif(func.initcap(func.trim(Transaction.category)), ""), "Uncategorized")
    # Stored timestamps are naive UTC; months are IST calendar months.
    local_date = func.timezone("Asia/Kolkata", func.timezone("UTC", Transaction.date))
    bank_name = Bank.query.with_entities(Bank.name).filter(Bank.id == BANK_ID).scalar_subquery()
    card_name = CreditCard.query.with_entities(CreditCard.name).filter(CreditCard.id == CARD_ID).scalar_subquery()
    saving_name = Saving.query.with_entities(Saving.name).filter(Saving.id == SAVING_ID).scalar_subquery()
    account = func.coalesce(bank_name, card_name, saving_name)

    by_type = (query.with_entities(KIND, func.count(), func.sum(amount), func.min(amount),
                                   func.max(amount), func.min(Transaction.date), func.max(Transaction.date))
               .group_by(KIND).order_by(KIND).all())
    totals = [{"type": t or "unknown", "count": n, "total": _round(s), "average": _round((s or 0) / n),
               "smallest": _round(lo), "largest": _round(hi), "first_date": _ist_day(first),
               "last_date": _ist_day(last)}
              for t, n, s, lo, hi, first, last in by_type]

    result = {
        "query": {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in q.items()
                  if v not in (None, [], "")},
        "matched": sum(row["count"] for row in totals),
        "totals": totals,
    }

    if SAVINGS in TYPES_BY_KIND[q["account_kind"]]:
        # Savings rows can mirror bank rows (cash deposited and also entered as bank income),
        # so say how many matched; and how many savings transfers were left out by rule.
        result["savings"] = {
            "matched": query.filter(Transaction.type == SAVINGS).count() if result["matched"] else 0,
        }
        left = (Transaction.query.filter(*_conditions(user_id, q, with_money_movement=False, savings_rule=False),
                                         _savings_transfer())
                .with_entities(func.count(), func.sum(amount)).one())
        result["savings"].update(transfers_left_out=left[0], transfers_left_out_total=_round(left[1]))
        if q["money_movement"] != "only":
            deposits = (Transaction.query.filter(*_conditions(user_id, q, with_money_movement=False, savings_rule=False),
                                                 ~_savings_transfer(), _savings_deposit())
                        .with_entities(func.count(), func.sum(amount)).one())
            result["savings"].update(deposits_left_out=deposits[0], deposits_left_out_total=_round(deposits[1]))

    if q["terms"] and result["matched"]:
        counts = query.with_entities(*[func.sum(case((_term_match(t), 1), else_=0)) for t in q["terms"]]).one()
        result["term_matches"] = [{"term": t, "count": int(n or 0)} for t, n in zip(q["terms"], counts)]

    if q["money_movement"] != "include":
        result["money_movement"] = {"mode": q["money_movement"], "categories": list(money_movement_categories())}
        if q["money_movement"] == "exclude":
            # What was left out, so the answer can say so and the user can check it.
            left_out = (Transaction.query.filter(*_conditions(user_id, q, with_money_movement=False), _moving())
                        .with_entities(func.count(), func.sum(amount)).one())
            result["money_movement"].update(excluded_count=left_out[0], excluded_total=_round(left_out[1]))

    if q["group_by"] != "none" and result["matched"]:
        # Groups describe one type: the one asked for, otherwise spending.
        present = [row["type"] for row in totals]
        focus = q["type"] or ("expense" if "expense" in present else present[0])
        focus_total = sum(row["total"] for row in totals if row["type"] == focus)
        key = {"category": category, "month": func.to_char(local_date, "YYYY-MM"), "account": account,
               "description": func.coalesce(func.nullif(func.trim(Transaction.description), ""), "(none)")
               }[q["group_by"]]
        order = key.desc() if q["group_by"] == "month" else func.sum(amount).desc()
        groups = (query.filter(KIND == focus)
                  .with_entities(key, func.count(), func.sum(amount)).group_by(key).order_by(order).all())
        shown = groups[:MAX_GROUPS]
        result["groups"] = {
            "by": q["group_by"], "type": focus, "groups_total": len(groups),
            "rows": [{"key": str(k)[:DESCRIPTION_CHARS], "count": n, "total": _round(s),
                      "share_pct": round(float(s or 0) * 100 / focus_total, 1) if focus_total else 0.0}
                     for k, n, s in shown],
            "other_total": _round(sum(s or 0 for _, _, s in groups[MAX_GROUPS:])),
        }

    if q["limit"] and result["matched"]:
        order = {"date_desc": (Transaction.date.desc(), Transaction.id.desc()),
                 "date_asc": (Transaction.date.asc(), Transaction.id.asc()),
                 "amount_desc": (amount.desc(), Transaction.date.desc()),
                 "amount_asc": (amount.asc(), Transaction.date.desc())}[q["sort"]]
        rows = (query.with_entities(Transaction.id, Transaction.date, KIND, account,
                                    category, Transaction.description, amount)
                .order_by(*order).limit(q["limit"]).all())
        # The id lets a client refer back to a row (the AI's "add up these rows" step).
        result["rows"] = [{"id": i, "date": _ist_day(d), "type": t, "account": a or "Unknown", "category": c,
                           "description": (desc or "")[:DESCRIPTION_CHARS], "amount": _round(s)}
                          for i, d, t, a, c, desc, s in rows]
    return result


@transaction_query_routes.route("/transactions/query", methods=["GET"])
@jwt_required()
def transaction_query():
    user_id = int(get_jwt_identity())
    try:
        q = parse_query(request.args)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(run_query(user_id, q)), 200
