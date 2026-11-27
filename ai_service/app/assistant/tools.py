"""The read-only tools the model may call to answer questions about the user's own data.

Safety model
- Whitelist: the model can only pick one of the tools below, by name. There is no
  "run SQL" or "call any URL" tool.
- Validated arguments: the model writes the arguments as JSON; they are checked
  against a Pydantic model (types, allowed values, lengths) before anything runs.
- Read-only: every tool is a GET on an existing Flask endpoint, with the user's token.
- The code computes, the model writes: totals, averages, shares and groupings are
  computed here in Python. The model only receives small summary tables and is told
  to copy figures, not calculate them. The answer is then checked against these
  figures (see numbers.py).
- Summaries, not rows: the model gets totals, top categories, months, accounts and the
  largest few, never the raw transaction list. (Original rule, Nov 24. Since Nov 26 the
  query tool may also return up to 20 matching rows (date, account, category, description,
  amount), because precise questions such as "my last haircut" need the row itself.)

Where the maths happens: transaction totals are computed by PostgreSQL in Flask's
GET /transactions/summary (SUM / COUNT / GROUP BY over every matching row). The first
version paged through rows here (100 per request, capped at 1,000 rows), which gave
partial totals for users with thousands of transactions; moving the aggregation into
the database fixed that. pandas would not have: the cost was fetching rows over HTTP,
not adding them up. pandas is worth adding only for analysis SQL does badly (trends,
rolling averages, anomalies), on top of these summaries.

Update (Nov 26, fine-tuning phase): one fixed summary could not answer precise questions
("my last transaction", "list my Uber rides in February", "did my friend send me money for
the trip?"), and the model sometimes quoted one slice of it as the total. The model now
fills in a structured query (query_transactions): search words, type, dates, amounts,
grouping, sort and a row limit. Flask's GET /transactions/query validates it and turns it
into parameterised SQL, always scoped to the user; the model never writes SQL. The
spending-by-category tool was removed: it listed only the 12 largest categories, defaulted
to 30 days and counted transfers and card bills as spending; query_transactions with
group_by=category covers it.
"""

import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from .flask_data import DataUnavailable, FlaskDataClient

log = logging.getLogger("ppa_ai.tools")

DESCRIPTION_CHARS = 80   # Flask already truncates; kept as a second limit

# ---- Result shape: what the model reads and what the UI shows ------------------------

@dataclass
class Table:
    title: str
    columns: list[str]
    rows: list[list[Any]]


# Facts that are instructions for the model, not figures for the user (hidden on screen).
MODEL_ONLY_FACTS = ("pick", "all_rows_listed")


@dataclass
class DataBlock:
    """One tool's result. The same object goes to the model (as compact JSON) and to
    the user (as figures and tables under the answer), so the user can check the answer.
    `meta` (Nov 27) is the structured query behind it, for the code that writes the answer;
    it is never sent to the model or shown."""
    title: str
    facts: dict[str, Any] = field(default_factory=dict)
    tables: list[Table] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict, repr=False)

    def _public(self) -> dict:
        return {"title": self.title, "facts": self.facts, "tables": [asdict(t) for t in self.tables]}

    def to_json(self) -> str:
        return json.dumps(self._public(), ensure_ascii=False, separators=(",", ":"), default=str)

    def for_user(self) -> dict:
        """What the browser shows under the answer: figures and tables, no model instructions."""
        public = self._public()
        public["facts"] = {k: v for k, v in self.facts.items() if k not in MODEL_ONLY_FACTS}
        return public

    def for_model(self) -> str:
        """What goes back to the model. The same as to_json, except for picked rows: the model
        has just seen every row, so it gets the total and the descriptions, not the full rows
        again. This keeps a pick question near Groq's 8,000 tokens/minute (measured ~8,000
        with full rows)."""
        if self.facts.get("pick") and self.facts.get("all_rows_listed"):
            # Rules on demand (Nov 27): how to pick rows by meaning is sent only with a list to
            # pick from, not in the system prompt of every trip of every question.
            public = self._public()
            public["how_to_pick"] = PICK_RULES.format(kind=self.meta.get("pick_kind") or "what the question asks for")
            return json.dumps(public, ensure_ascii=False, separators=(",", ":"), default=str)
        if not self.title.startswith(PICKED):
            return self.to_json()
        brief = {"title": self.title, "facts": self.facts,
                 **{t.title.lower().replace(" ", "_"): [r[2] for r in t.rows] for t in self.tables}}
        return json.dumps(brief, ensure_ascii=False, separators=(",", ":"), default=str)


PICK_RULES = (
    "Call add_up_transactions with the ids of every listed row that is {kind}. Judge each row by its "
    "DESCRIPTION: a category shared by the whole set (e.g. every trip row filed as Travel) says nothing. "
    "Examples after 'like' or 'such as' name a kind, not the full list. Kinds: travel = cabs, autos, "
    "trains, buses, flights, bike or car rent, fuel/petrol, parking, tolls, vehicle repair, tickets; "
    "food = meals, breakfast (bf), lunch, dinner, snacks, drinks, juice, water, desserts, food delivery "
    "(food includes drinks unless the user says otherwise); stay = hotel, hostel, room, deposit for a stay. "
    "Treat similar rows the same (if one 'water' row counts, all do). When unsure, include the row. Lump "
    "sums paid to friends ('share', 'repayment', a person's name with the trip) are not one kind: leave "
    "them out. label = a few words for what was picked. note (optional) = one short line, no numbers, "
    "on kinds of rows you were unsure about or left out.")


def money(value: Any) -> float:
    try:
        return round(abs(float(value or 0)), 2)
    except (TypeError, ValueError):
        return 0.0


def share(part: float, total: float) -> float:
    return round(part * 100 / total, 1) if total else 0.0


# ---- Arguments -----------------------------------------------------------------------

class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArgs(_Args):
    pass


class AccountsArgs(_Args):
    kind: Literal["bank", "credit_card", "savings", "all"] = Field("all", description="Which accounts to list.")


MAX_TERMS = 6
MAX_MUST_MATCH = 3


class QueryArgs(_Args):
    # No maxItems in the schema sent to Groq: Groq rejects a whole reply whose tool call breaks
    # the schema (seen live: 7 words for a limit of 6), and the user gets "unavailable". Extra
    # words are dropped instead (_trim_words); Flask still enforces 6 and 3.
    terms: list[Annotated[str, Field(min_length=2, max_length=40)]] = Field(
        default_factory=list,
        description="Up to 6 words to find in the description OR the category (any of them matches). For a "
                    "general kind of spending add synonyms, e.g. food -> ['food', 'dinner', 'lunch', 'snacks']. "
                    "Empty = all transactions.")
    must_match: list[Annotated[str, Field(min_length=2, max_length=170)]] = Field(
        default_factory=list,
        description="Up to 3 entries that must ALL match (description or category): the named thing the "
                    "question is limited to, e.g. the Goa trip -> ['goa']. Alternatives go in ONE entry "
                    "with |, e.g. 'Shree or Shreya' -> ['shree|shreya'].")
    type: Literal["expense", "income", "payment"] | None = Field(
        None, description="expense = money going out (spent or paid to someone, savings withdrawals); income = "
                          "money received (savings deposits); payment = credit card bill payments. Omit for all.")
    account_kind: Literal["bank", "credit_card", "savings", "all"] = Field(
        "all", description="Bank accounts, credit cards, savings accounts, or all of them.")
    account_name: str | None = Field(None, max_length=60, description="Only accounts whose name contains this.")
    start_date: date | None = Field(None, description="First day, YYYY-MM-DD (India time). Omit for all time.")
    end_date: date | None = Field(None, description="Last day, YYYY-MM-DD (India time). Omit for up to today.")
    min_amount: float | None = Field(None, ge=0, description="Only transactions of at least this many rupees.")
    max_amount: float | None = Field(None, ge=0, description="Only transactions of at most this many rupees.")
    money_movement: Literal["auto", "include", "exclude", "only"] = Field(
        "auto", description="Transfers between own accounts, card bill payments and investments. auto = left "
                            "out of totals when no search terms are given (overall spending), kept when "
                            "searching. only = just those (e.g. 'how much did I transfer').")
    group_by: Literal["none", "category", "month", "account", "description"] = Field(
        "none", description="Totals per category, month, account or description.")
    sort: Literal["date_desc", "date_asc", "amount_desc", "amount_asc"] = Field(
        "date_desc", description="Order of the listed rows: newest, oldest, largest or smallest first.")
    limit: int = Field(10, ge=0, le=30, description="How many matching rows to list (0 = totals only).")
    pick_kind: str | None = Field(
        None, min_length=2, max_length=40,
        description="The KIND of spending asked for inside the named set, e.g. 'gifts' in 'gifts for Shree', "
                    "'travel' in 'travel in the Goa trip'. The set is listed without totals and you pick rows next.")

    @field_validator("terms", "must_match", mode="before")
    @classmethod
    def _trim_words(cls, value, info):
        limit = MAX_TERMS if info.field_name == "terms" else MAX_MUST_MATCH
        return value[:limit] if isinstance(value, list) else value

    @model_validator(mode="after")
    def _ranges_in_order(self):
        if self.start_date and self.end_date and self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")
        if self.min_amount is not None and self.max_amount is not None and self.min_amount > self.max_amount:
            raise ValueError("min_amount must be at most max_amount")
        return self

    def resolved_money_movement(self) -> str:
        if self.money_movement != "auto":
            return self.money_movement
        return "include" if self.terms or self.must_match else "exclude"

    def describe(self) -> str:
        """The query in plain words, shown under the answer so the user can check it."""
        parts = [{"expense": "money out (expenses)", "income": "money in (income)",
                  "payment": "card bill payments"}.get(self.type or "", "all types")]
        if self.must_match:
            parts.append(f"must contain: {', '.join(m.replace('|', ' or ') for m in self.must_match)}")
        if self.terms:
            parts.append(f"any of: {', '.join(self.terms)}" if self.must_match else f"words: {', '.join(self.terms)}")
        elif not self.must_match:
            parts.append("no search words")
        if self.start_date or self.end_date:
            parts.append(f"{self.start_date.isoformat() if self.start_date else 'the beginning'} to "
                         f"{self.end_date.isoformat() if self.end_date else 'today'}")
        else:
            parts.append("all time (no date filter)")
        if self.account_kind != "all":
            parts.append({"bank": "bank accounts", "credit_card": "credit cards",
                          "savings": "savings accounts"}[self.account_kind])
        if self.account_name:
            parts.append(f"account: {self.account_name}")
        if self.min_amount is not None:
            parts.append(f"at least {self.min_amount:g}")
        if self.max_amount is not None:
            parts.append(f"at most {self.max_amount:g}")
        parts.append({"include": "transfers, card bills and investments included",
                      "exclude": "transfers, card bills and investments left out",
                      "only": "only transfers, card bills and investments"}[self.resolved_money_movement()])
        if self.group_by != "none":
            parts.append(f"grouped by {self.group_by}")
        if self.pick_kind:
            parts.append(f"rows listed to pick: {self.pick_kind}")
        elif self.limit:
            parts.append(f"up to {self.limit} rows, {SORT_WORDS[self.sort]}")
        return " · ".join(parts)


SORT_WORDS = {"date_desc": "newest first", "date_asc": "oldest first",
              "amount_desc": "largest first", "amount_asc": "smallest first"}


# ---- Tools -----------------------------------------------------------------------------

async def financial_summary(flask: FlaskDataClient, token: str, args: NoArgs) -> DataBlock:
    data = await flask.get("/dashboard/summary", token) or {}
    keys = ["net_worth", "total_bank_balance", "total_savings", "total_assets", "total_credit_card_debt"]
    return DataBlock("Financial summary (now)", {k: round(float(data.get(k) or 0), 2) for k in keys},
                     meta={"kind": "summary"})


async def asset_allocation(flask: FlaskDataClient, token: str, args: NoArgs) -> DataBlock:
    rows = await flask.get("/dashboard/asset-allocation", token) or []
    total = round(sum(money(r.get("value")) for r in rows), 2)
    table = Table("Assets by category", ["category", "value", "share_pct"],
                  [[r.get("name") or "Uncategorized", money(r.get("value")), share(money(r.get("value")), total)]
                   for r in rows])
    return DataBlock("Asset allocation (now)", {"total_assets": total}, [table], meta={"kind": "allocation"})


async def list_accounts(flask: FlaskDataClient, token: str, args: AccountsArgs) -> DataBlock:
    block = DataBlock("Accounts (now)", meta={"kind": "accounts"})
    if args.kind in ("bank", "all"):
        banks = await flask.get("/banks", token) or []
        block.tables.append(Table("Bank accounts", ["name", "balance"],
                                  [[b.get("name"), round(float(b.get("balance") or 0), 2)] for b in banks]))
        block.facts["bank_accounts"] = len(banks)
        block.facts["total_bank_balance"] = round(sum(float(b.get("balance") or 0) for b in banks), 2)
    if args.kind in ("credit_card", "all"):
        cards = await flask.get("/credit_cards", token) or []
        cols = ["limit", "used", "available_limit", "total_payable", "billed_unpaid", "unbilled_spends"]
        block.tables.append(Table("Credit cards", ["name", *cols],
                                  [[c.get("name"), *[money(c.get(k)) for k in cols]] for c in cards]))
        block.facts["credit_cards"] = len(cards)
        block.facts["total_credit_card_payable"] = round(sum(money(c.get("total_payable")) for c in cards), 2)
    if args.kind in ("savings", "all"):
        savings = await flask.get("/savings", token) or []
        block.tables.append(Table("Savings", ["name", "bank", "balance"],
                                  [[s.get("name"), s.get("bank_name"), round(float(s.get("balance") or 0), 2)]
                                   for s in savings]))
        block.facts["savings_accounts"] = len(savings)
        block.facts["total_savings"] = round(sum(float(s.get("balance") or 0) for s in savings), 2)
    return block


async def query_transactions(flask: FlaskDataClient, token: str, args: QueryArgs) -> DataBlock:
    """One call to Flask's GET /transactions/query: PostgreSQL filters, totals, groups and
    lists the matching rows, so totals are exact however many transactions the user has."""
    if args.must_match and args.terms and not args.pick_kind:
        # "A kind of spending inside a named set" (must contain X, any of these words). Seen
        # live: "travel like cab, bike rent, train, auto in the Goa trip" was searched for
        # exactly those words, found only the cab (₹800) and missed petrol, parking and the
        # vehicle repair. If the named set is small, list all of it with totals hidden, so the
        # rows are picked by meaning; the words become a hint. Large sets keep the word search.
        whole = await query_transactions(flask, token, args.model_copy(
            update={"terms": [], "pick_kind": ", ".join(args.terms)[:40]}))
        if whole.facts.get("all_rows_listed"):
            whole.facts["pick"] = (f"The whole set is listed ({whole.facts['matched']} rows) so rows can be picked "
                                   f"by meaning, not only by the words {', '.join(args.terms)}. Totals hidden. "
                                   "Call add_up_transactions with the ids of every row that fits the question.")
            return whole
    params: dict[str, Any] = {
        "terms": args.terms or None, "must_match": args.must_match or None, "type": args.type, "account_kind": args.account_kind,
        "account_name": args.account_name,
        "start_date": args.start_date.isoformat() if args.start_date else None,
        "end_date": args.end_date.isoformat() if args.end_date else None,
        "min_amount": args.min_amount, "max_amount": args.max_amount,
        "money_movement": args.resolved_money_movement(), "group_by": args.group_by,
        "sort": args.sort, "limit": 30 if args.pick_kind else args.limit,
    }
    data = await flask.get("/transactions/query", token, params) or {}

    note = None
    if not int(data.get("matched") or 0) and len(args.must_match) > 1:
        # Seen live, several times: "Shree or Shreya" sent as two must_match words, which need
        # both names in one row, so nothing matched. Rerun at once with them as alternatives
        # (shree|shreya), keeping the other words, and say so; this saves a model round and
        # stops the model from "fixing" it into an any-of search that adds unrelated rows.
        note = (f"No row contains all of {', '.join(args.must_match)}; showing rows that contain any of them.")
        args = args.model_copy(update={"must_match": ["|".join(args.must_match)]})
        params.update(must_match=args.must_match)
        data = await flask.get("/transactions/query", token, params) or {}

    matched = int(data.get("matched") or 0)
    block = DataBlock("Transactions", {"query": args.describe(), "matched": matched}, meta={
        "kind": "query", "type": args.type, "must_match": list(args.must_match), "terms": list(args.terms),
        "start_date": args.start_date, "end_date": args.end_date, "group_by": args.group_by,
        "sort": args.sort, "limit": args.limit, "pick_kind": args.pick_kind,
        "money_movement": args.resolved_money_movement(), "account_kind": args.account_kind,
        "account_name": args.account_name})
    if note:
        block.facts["note"] = note
    if not matched:
        block.facts["note"] = ((note + " ") if note else "") + (
            "No transactions match. Say what was searched for; a different word or a shorter form may match.")
    if args.pick_kind and matched:
        # Guard (seen live): asked for "gifts for Shree", the model listed every Shree row and
        # called their total (transfers included) "gifts". With pick_kind set there is no
        # whole-set total to quote: the only way to a figure is picking rows, and any other
        # number is stopped by the number check.
        listed = len(data.get("rows") or [])
        block.facts["pick"] = (f"Totals hidden. Read every row and call add_up_transactions with the ids of the "
                               f"rows that are {args.pick_kind}." if listed >= matched else
                               f"Too many rows ({matched}) to pick from. Narrow the dates or the named thing, or "
                               f"search with words for {args.pick_kind} instead (pick_kind unset).")
        data = {**data, "totals": [], "groups": None, "money_movement": None}
    # Totals cover every matching row. Each type is totalled separately: adding money in
    # and money out together would be meaningless.
    for row in data.get("totals", []):
        kind = row.get("type", "unknown")
        block.facts[f"{kind}_count"] = int(row.get("count") or 0)
        block.facts[f"{kind}_total"] = money(row.get("total"))
        block.facts[f"{kind}_average"] = money(row.get("average"))
        block.facts[f"{kind}_smallest"] = money(row.get("smallest"))
        block.facts[f"{kind}_largest"] = money(row.get("largest"))
        block.facts[f"{kind}_first_date"] = row.get("first_date")
        block.facts[f"{kind}_last_date"] = row.get("last_date")

    savings = data.get("savings") or {}
    if savings.get("matched"):
        # Nov 27: savings rows are included (withdrawal = money out, deposit = money in).
        block.facts["savings_rows"] = int(savings["matched"])
    if savings.get("transfers_left_out"):
        block.facts["savings_transfers_left_out_count"] = int(savings["transfers_left_out"])
        block.facts["savings_transfers_left_out_total"] = money(savings.get("transfers_left_out_total"))
    if savings.get("deposits_left_out"):
        # Owner's decision (Nov 27): money put into savings is not income.
        block.facts["savings_deposits_left_out_count"] = int(savings["deposits_left_out"])
        block.facts["savings_deposits_left_out_total"] = money(savings.get("deposits_left_out_total"))

    moving = data.get("money_movement") or {}
    if moving.get("mode") == "exclude":
        block.facts["left_out_money_movement_count"] = int(moving.get("excluded_count") or 0)
        block.facts["left_out_money_movement_total"] = money(moving.get("excluded_total"))

    if data.get("term_matches"):
        block.tables.append(Table("Matches per search word", ["word", "count"],
                                  [[t.get("term"), t.get("count")] for t in data["term_matches"]]))
    groups = data.get("groups")
    if groups and groups.get("rows"):
        label = str(groups.get("type") or "expense").title()
        block.facts["groups_total"] = int(groups.get("groups_total") or len(groups["rows"]))
        if money(groups.get("other_total")):
            block.facts["other_groups_amount"] = money(groups.get("other_total"))
        block.tables.append(Table(f"{label} by {groups.get('by')} (parts of the {groups.get('type')} total)",
                                  [str(groups.get("by")), "count", "amount", "share_pct"],
                                  [[g.get("key"), g.get("count"), money(g.get("total")), g.get("share_pct")]
                                   for g in groups["rows"]]))
    if data.get("rows"):
        block.facts["all_rows_listed"] = len(data["rows"]) >= matched
        # Rows listed for picking leave out what the model does not need (the account, and the
        # type when the query fixed it): a pick question sits at Groq's 8,000 tokens/minute.
        columns = ["id", "date", "type", "account", "category", "description", "amount"]
        if args.pick_kind:
            columns = [c for c in columns if c != "account" and not (c == "type" and args.type)]
        rows = [{**r, "description": str(r.get("description") or "")[:DESCRIPTION_CHARS],
                 "amount": money(r.get("amount"))} for r in data["rows"]]
        block.tables.append(Table(f"{MATCHING} ({SORT_WORDS[args.sort]})", columns,
                                  [[r.get(c) for c in columns] for r in rows]))
    return block


# ---- "X or Y" in the question is OR, decided by code ---------------------------------
#
# The model has repeatedly sent "Shree or Shreya" as two must_match entries (AND: both in
# one row). When the user's own words join two entries with "or", the code merges them
# into one alternatives entry ("shree|shreya") before the query runs. Deterministic: it
# does not depend on the model following the prompt.

def merge_or_alternatives(question: str, args: "QueryArgs") -> "QueryArgs":
    entries = list(args.must_match)
    if len(entries) < 2:
        return args
    text = " ".join(question.lower().split())

    def joined_by_or(a: str, b: str) -> bool:
        # "a or b", allowing longer word forms ("shre" matches "shreya") and "a, b or c" lists.
        word_a = rf"\b{re.escape(a.lower())}\w*"
        word_b = rf"\b{re.escape(b.lower())}\w*"
        link = r"(?:(?:\s*,\s*(?:\w+\s*,\s*)*|\s+)or\s+|\s*,\s*)"   # grouped: "|" must not split the pattern
        return bool(re.search(word_a + link + word_b, text) or re.search(word_b + link + word_a, text)) and \
            bool(re.search(r"\bor\b", text))

    groups: list[list[str]] = []
    for entry in entries:
        if "|" not in entry:
            for group in groups:
                if any("|" not in other and joined_by_or(other, entry) for other in group):
                    group.append(entry)
                    break
            else:
                groups.append([entry])
        else:
            groups.append([entry])
    merged = ["|".join(group) for group in groups]
    return args if merged == entries else args.model_copy(update={"must_match": merged})


# ---- Picking rows by meaning ----------------------------------------------------------
#
# Keyword search misses rows whose words nobody predicts ("31st bf" is breakfast). For a
# small set listed in full (one trip, one month of one merchant), the model reads the rows
# and returns the ids that fit the question by meaning; this code adds them up. So the
# model classifies, the code does the arithmetic, and only rows already fetched for this
# request (as this user) can be picked. Runs locally: no Flask call, no extra data.

MATCHING = "Matching transactions"
PICKED = "Picked by meaning"


class PickArgs(_Args):
    ids: list[int] = Field(..., max_length=30,
                           description="ids of listed rows that fit the question by meaning (empty if none fit).")
    label: str = Field(..., min_length=2, max_length=60,
                       description="What was picked, in a few words, e.g. 'food and drinks on the Goa trip'.")
    note: str | None = Field(None, max_length=200,
                             description="Optional: one short line on rows you were unsure about or left out.")


class PickError(ValueError):
    """The model picked rows it may not use; the message goes back to it."""


def listed_rows(blocks: list[DataBlock]) -> dict[int, dict]:
    """Rows from earlier query results in this request whose matching set was listed in full."""
    rows: dict[int, dict] = {}
    for block in blocks:
        if not block.facts.get("all_rows_listed"):
            continue
        for table in block.tables:
            if table.title.startswith(MATCHING) and "id" in table.columns:
                for values in table.rows:
                    row = dict(zip(table.columns, values))
                    rows[int(row["id"])] = row
    return rows


def add_up_picked(blocks: list[DataBlock], args: PickArgs) -> DataBlock:
    rows = listed_rows(blocks)
    source = next((b.meta for b in reversed(blocks) if b.facts.get("all_rows_listed")), {})
    if not rows:
        raise PickError("no complete list of rows to pick from: first call query_transactions with a narrow "
                        "search (must_match) and limit 30, so that all matching rows are listed")
    unknown = [i for i in args.ids if i not in rows]
    if unknown:
        raise PickError(f"these ids were not in the listed rows: {unknown[:10]}")
    picked = [rows[i] for i in dict.fromkeys(args.ids)]
    left = [r for i, r in rows.items() if i not in set(args.ids)]
    columns = ["id", "date", "description", "amount"]
    types = sorted({str(r["type"]) for r in picked if r.get("type")}) or ["as filtered"]
    block = DataBlock(f"{PICKED}: {args.label}", {
        "picked": args.label,
        "picked_count": len(picked),
        "picked_total": round(sum(money(r.get("amount")) for r in picked), 2),
        "picked_types": ", ".join(types),
        "rows_considered_count": len(rows),
        "not_counted_count": len(left),
        "not_counted_total": round(sum(money(r.get("amount")) for r in left), 2),
    }, meta={"kind": "picked", "source": source, "note": args.note})
    block.tables.append(Table("Counted", columns, [[r.get(c) for c in columns] for r in picked]))
    if left:
        block.tables.append(Table("Not counted", columns, [[r.get(c) for c in columns] for r in left]))
    return block


# ---- Registry --------------------------------------------------------------------------

@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    args: type[_Args]
    run: Callable[[FlaskDataClient, str, Any], Awaitable[DataBlock]] | None   # None: runs on fetched rows

    def schema(self) -> dict:
        params = self.args.model_json_schema()
        params.pop("title", None)
        for prop in params.get("properties", {}).values():
            prop.pop("title", None)
        params.setdefault("properties", {})
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": params}}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("get_financial_summary",
         "Current net worth, total bank balance, savings, assets and credit card debt.",
         NoArgs, financial_summary),
    Tool("get_asset_allocation", "Current value of assets per category, with shares.", NoArgs, asset_allocation),
    Tool("list_accounts",
         "Bank accounts and balances, credit cards (limit, used, available, payable) and savings accounts.",
         AccountsArgs, list_accounts),
    Tool("query_transactions",
         "Answers any question about bank, credit card and savings transactions with exact figures from the "
         "database: totals per type over ALL matching rows, optional groups, and the matching rows "
         "themselves. Use for amounts, merchants, people, trips, categories, the latest or largest "
         "transactions, monthly totals and money received from someone.",
         QueryArgs, query_transactions),
    Tool("add_up_transactions",
         "Adds up rows picked by meaning from a query_transactions result that listed ALL matching rows "
         "(all_rows_listed is true). Use when words cannot catch everything, e.g. food on one trip: list the "
         "trip's rows, then pass the ids of the rows that are food. The code computes the total.",
         PickArgs, None),
]}

TOOL_SCHEMAS = [t.schema() for t in TOOLS.values()]


class ToolInputError(ValueError):
    """The model asked for an unknown tool or wrote invalid arguments."""


def parse_call(name: str, arguments: str) -> tuple[Tool, _Args]:
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolInputError(f"unknown tool '{name[:40]}'")
    try:
        raw = json.loads(arguments or "{}")
    except ValueError:
        raise ToolInputError("arguments are not valid JSON") from None
    try:
        return tool, tool.args.model_validate(raw if isinstance(raw, dict) else {})
    except ValidationError as exc:
        problems = "; ".join(f"{'.'.join(map(str, e['loc'])) or 'arguments'}: {e['msg']}" for e in exc.errors())
        raise ToolInputError(problems[:300]) from None


__all__ = ["TOOLS", "TOOL_SCHEMAS", "DataBlock", "PickError", "QueryArgs", "Table", "ToolInputError",
           "add_up_picked", "merge_or_alternatives", "parse_call", "DataUnavailable"]
