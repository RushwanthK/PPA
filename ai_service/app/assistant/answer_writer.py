"""Code writes the answer (Nov 27).

Until Nov 26 the model wrote the final sentence in one more trip to Groq. That trip cost
about 2,400-3,500 tokens, pushed a "pick by meaning" question past Groq's free 8,000
tokens a minute, and when it failed the user got "I couldn't write a checked summary".
Now the model only decides WHAT to fetch (the structured query) and, for picks, WHICH rows
count. By then everything a sentence needs is already in plain fields:

    from the query (meta):  type -> "spent" / "received", search words, dates, sort, grouping
    from the result:        totals, counts, first/last dates, the top row, groups, picked total

So this module fills in templates. No tokens, and the figures are exact because code put
them there. The tables under the answer show the rows that were matched and counted.
"""

import re
from datetime import date, datetime
from typing import Any

from .tools import MATCHING, DataBlock

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
SMALL_LIST = 3          # a query listing at most this many rows is a "latest / first / largest" question
TYPE_WORDS = {"expense": "expense", "income": "income", "payment": "card bill payment"}


# ---- Formatting -------------------------------------------------------------------------

def inr(value: Any) -> str:
    """₹1,23,456.50 (Indian grouping); whole rupees without .00."""
    amount = round(abs(float(value or 0)), 2)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))
    if paise == 100:
        rupees, paise = rupees + 1, 0
    digits = str(rupees)
    if len(digits) > 3:
        head = re.sub(r"(\d)(?=(\d{2})+$)", r"\1,", digits[:-3])
        digits = f"{head},{digits[-3:]}"
    return f"₹{digits}" + (f".{paise:02d}" if paise else "")


def nice_date(value: Any) -> str:
    """2026-03-15 (or a datetime / '2026-03-15 10:00:00') -> 15 Mar 2026."""
    if isinstance(value, (date, datetime)):
        d = value
    else:
        try:
            d = date.fromisoformat(str(value)[:10])
        except ValueError:
            return str(value)
    return f"{d.day} {MONTHS[d.month - 1]} {d.year}"


def period(meta: dict) -> str:
    start, end = meta.get("start_date"), meta.get("end_date")
    if start and end:
        return f"{nice_date(start)} to {nice_date(end)}"
    if start:
        return f"{nice_date(start)} to today"
    if end:
        return f"up to {nice_date(end)}"
    return "all time"


def searched(meta: dict) -> str:
    """'goa' · 'shree' or 'shreya' · any of 'food', 'dinner'."""
    parts = [" or ".join(f"'{w}'" for w in entry.split("|")) for entry in meta.get("must_match") or []]
    terms = meta.get("terms") or []
    if terms:
        words = ", ".join(f"'{t}'" for t in terms)
        parts.append(f"any of {words}" if len(terms) > 1 else words)
    text = " and ".join(parts)
    if meta.get("account_name"):
        text = (text + " " if text else "") + f"in accounts named '{meta['account_name']}'"
    return text


def _count(n: int, word: str = "transaction") -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _rows(block: DataBlock) -> list[dict]:
    for table in block.tables:
        if table.title.startswith(MATCHING):
            return [dict(zip(table.columns, r)) for r in table.rows]
    return []


# ---- One sentence group per tool result ---------------------------------------------------

def _query(block: DataBlock) -> list[str]:
    m, f = block.meta, block.facts
    what = searched(m)
    when = period(m)
    matching = f" matching {what}" if what else ""
    kind = TYPE_WORDS.get(m.get("type") or "", "")
    out: list[str] = []

    if not f.get("matched"):
        out.append(f"No {kind + ' ' if kind else ''}transactions{matching or ' matched your filters'} ({when}).")
        if what:
            out.append("A shorter form of the word, or a different spelling, may find them.")
        return out

    if m.get("pick_kind") and "pick" in f:
        # Totals were hidden for picking, and no pick followed (too many rows, or no model trip left).
        out.append(f"{_count(f['matched'])}{matching} ({when}), but I couldn't pick the "
                   f"{m['pick_kind']} ones this time. Try a shorter period or a narrower search, "
                   "or ask again in a minute.")
        return out

    rows = _rows(block)
    if rows and m.get("group_by") in (None, "none") and int(m.get("limit") or 0) <= SMALL_LIST:
        which = {"date_desc": "latest", "date_asc": "first", "amount_desc": "largest",
                 "amount_asc": "smallest"}.get(m.get("sort"), "latest")
        top = rows[0]
        desc = str(top.get("description") or top.get("category") or "").strip()
        out.append(f"Your {which} {kind + ' ' if kind else ''}transaction{matching} ({when}) was on "
                   f"{nice_date(top.get('date'))}: {inr(top.get('amount'))}" + (f", '{desc}'." if desc else "."))
        if f["matched"] > 1:
            out.append(f"{_count(f['matched'])} matched in all.")
        return out

    verbs = {"expense": "You spent", "income": "You received", "payment": "Card bill payments came to"}
    for t, verb in verbs.items():
        if f"{t}_count" not in f:
            continue
        n, first, last = f[f"{t}_count"], f.get(f"{t}_first_date"), f.get(f"{t}_last_date")
        dates = (f", on {nice_date(first)}" if first == last else
                 f", from {nice_date(first)} to {nice_date(last)}") if first else ""
        out.append(f"{verb} {inr(f[t + '_total'])} in {_count(n)}{matching} ({when}){dates}.")

    group_table = next((t for t in block.tables if " by " in t.title and "amount" in t.columns), None)
    if group_table and group_table.rows:
        key, _, amount, pct = group_table.rows[0][:4]
        out.append(f"Largest {m.get('group_by')}: {key}, {inr(amount)}" + (f" ({pct}%)." if pct is not None else "."))

    if f.get("left_out_money_movement_count"):
        out.append(f"Left out of the totals: {_count(f['left_out_money_movement_count'])} that move money "
                   f"between your own accounts, pay card bills or invest ({inr(f['left_out_money_movement_total'])}).")
    if f.get("savings_rows"):
        out.append(f"Includes {_count(f['savings_rows'], 'savings account withdrawal')}; money moved between your "
                   "own accounts may be counted twice.")
    if f.get("savings_deposits_left_out_count"):
        out.append(f"Left out {_count(f['savings_deposits_left_out_count'], 'savings deposit')} "
                   f"({inr(f['savings_deposits_left_out_total'])}): money put into savings is not income.")
    if f.get("savings_transfers_left_out_count"):
        out.append(f"Left out {_count(f['savings_transfers_left_out_count'], 'savings transfer')} "
                   f"({inr(f['savings_transfers_left_out_total'])}).")
    if f.get("note") and "No transactions match" not in str(f["note"]):
        out.append(str(f["note"]))
    return out


def _picked(block: DataBlock) -> list[str]:
    f, src = block.facts, block.meta.get("source") or {}
    t = src.get("type") or (f.get("picked_types") if f.get("picked_types") in TYPE_WORDS else None)
    label, total = f["picked"], inr(f["picked_total"])
    head = {"expense": f"You spent {total} on {label}",
            "income": f"You received {total} ({label})"}.get(t or "", f"{label}: {total}")
    what = searched(src)
    among = f"{_count(f['rows_considered_count'])}{' matching ' + what if what else ''} ({period(src)})"
    out = []
    if not f["picked_count"]:
        out.append(f"None of the {among} looked like {label}.")
        return out
    out.append(f"{head}: {f['picked_count']} of the {among}.")
    if f.get("not_counted_count"):
        out.append(f"Not counted: {_count(f['not_counted_count'])} ({inr(f['not_counted_total'])}), listed below.")
    return out


def _summary(block: DataBlock) -> list[str]:
    f = block.facts
    return [f"Your net worth is {inr(f.get('net_worth'))}: bank balance {inr(f.get('total_bank_balance'))}, "
            f"savings {inr(f.get('total_savings'))}, assets {inr(f.get('total_assets'))}, "
            f"credit card debt {inr(f.get('total_credit_card_debt'))}."]


def _allocation(block: DataBlock) -> list[str]:
    out = [f"Your assets are worth {inr(block.facts.get('total_assets'))}."]
    rows = block.tables[0].rows if block.tables else []
    if rows:
        top = max(rows, key=lambda r: r[1] or 0)
        out.append(f"Largest: {top[0]}, {inr(top[1])} ({top[2]}%).")
    return out


def _accounts(block: DataBlock) -> list[str]:
    f, out = block.facts, []
    if "bank_accounts" in f:
        out.append(f"Bank balance: {inr(f['total_bank_balance'])} across {_count(f['bank_accounts'], 'account')}.")
    if "credit_cards" in f:
        out.append(f"Credit cards: {inr(f['total_credit_card_payable'])} payable across "
                   f"{_count(f['credit_cards'], 'card')}.")
    if "savings_accounts" in f:
        out.append(f"Savings: {inr(f['total_savings'])} across {_count(f['savings_accounts'], 'account')}.")
    return out


WRITERS = {"query": _query, "picked": _picked, "summary": _summary, "allocation": _allocation,
           "accounts": _accounts}


def write_answer(blocks: list[DataBlock], note: str | None = None) -> str:
    """The answer, from the tool results. A list that was only fetched so rows could be
    picked is described by its pick, not by itself."""
    picked_from = any(b.meta.get("kind") == "picked" for b in blocks)
    lines: list[str] = []
    for block in blocks:
        kind = block.meta.get("kind")
        if picked_from and kind == "query" and block.meta.get("pick_kind") and "pick" in block.facts:
            continue
        writer = WRITERS.get(kind)
        if writer:
            lines.extend(writer(block))
    if note:
        lines.append(f"Note: {note}")
    return " ".join(lines) if lines else "I couldn't find PPA data that answers this."
