"""Number grounding: every figure in a "my data" answer must come from a tool result.

This is the data-mode equivalent of the citation check in help mode. Language models
are good at wording and bad at arithmetic, and a confidently wrong rupee amount is
the most harmful mistake a finance assistant can make. So the model is told to copy
figures, and this check enforces it: an answer containing any number that is not in
the tool results (allowing for rounding) is not shown. The user gets the exact
figures from the tools instead.

Allowed sources of numbers: the tool results, the user's question ("last 3 months"),
today's date, and small whole numbers up to 10 ("your top 3 categories"). Dates are
removed before checking: they come from the same data and a wrong date is far less
harmful than a wrong amount. Words like lakh, crore or k are not understood, so the
model is told not to use them; if it does, the check fails safely.
"""

import re

_MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
_DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}(?:-\d{2})?(?:[ T]\d{2}:\d{2}(?::\d{2})?)?\b"),           # 2026-11-03, 2026-11
    re.compile(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"),                                    # 03/11/2026
    re.compile(rf"\b\d{{1,2}}(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTHS}(?:,?\s+\d{{4}})?\b", re.I),  # 3 Nov 2026
    re.compile(rf"\b{_MONTHS}\s+\d{{1,2}}(?:st|nd|rd|th)?(?:,?\s+\d{{4}})?\b", re.I),        # Nov 3, 2026
    re.compile(rf"\b{_MONTHS}\s+\d{{4}}\b", re.I),                                       # November 2026
]
# 1,23,456.50 (Indian grouping), 123,456.50, 1234.5, 12
_NUMBER = re.compile(r"(?<![\w.])\d{1,3}(?:,\d{2,3})+(?:\.\d+)?(?![\w])|(?<![\w.,])\d+(?:\.\d+)?(?![\w])")
_ANY_NUMBER = re.compile(r"\d+(?:\.\d+)?")
SMALL_INTEGERS = {float(i) for i in range(0, 11)}


# Models write dates with typographic hyphens (2026‑11‑01 was seen from gpt-oss) and
# use thin or non-breaking spaces; turn them into plain ones before matching.
_HYPHENS = str.maketrans({c: "-" for c in "‐‑‒–—−"}
                         | {c: " " for c in "   "})


def numbers_in_answer(text: str) -> list[float]:
    text = text.translate(_HYPHENS)
    for pattern in _DATE_PATTERNS:
        text = pattern.sub(" ", text)
    return [float(m.group(0).replace(",", "")) for m in _NUMBER.finditer(text)]


def allowed_numbers(*sources: str) -> set[float]:
    """Every number in the sources, plus the roundings a writer might use."""
    allowed = set(SMALL_INTEGERS)
    for source in sources:
        for m in _ANY_NUMBER.finditer(source):
            value = float(m.group(0))
            allowed |= {value, round(value), round(value, 1), round(value, 2)}
    return allowed


def unverified_numbers(answer: str, *sources: str) -> list[float]:
    allowed = allowed_numbers(*sources)
    return [n for n in numbers_in_answer(answer) if not any(abs(n - a) < 0.005 for a in allowed)]
