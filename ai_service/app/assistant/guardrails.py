"""Deterministic input checks that run BEFORE any model call.

Layered defence: these cheap checks catch clear cases (and cost zero tokens). The
system prompt, relevance threshold and citation check catch the rest. Regexes are
deliberately narrow: blocking a legitimate education question ("What is a SIP?")
is also a failure, and tests check that no evaluation question is blocked.
"""

import re
import unicodedata

_INJECTION = [
    r"\b(ignore|disregard|forget|override)\b.{0,30}\b(previous|prior|above|earlier|all|your|the)\b.{0,20}"
    r"\b(instructions?|rules|prompts?|directions|guidelines)\b",
    r"\b(reveal|show|print|repeat|display|leak|tell me)\b.{0,30}\b(system|hidden|initial|original)\s+"
    r"(prompt|instructions?|message|rules)\b",
    r"\byou are now\b",
    r"\b(developer|dan|jailbreak|god)\s*mode\b",
    r"\bjailbreak\b",
    r"\bpretend (to be|you are)\b",
    r"</?\s*(system|sources?|question)\s*>",
]

_ADVICE = [
    # "Should I buy/sell/invest in X?"
    r"\bshould i\b.{0,40}\b(buy|sell|invest|hold|exit|switch|redeem)\b",
    # "Which stock/fund should I buy?" / "What fund to invest in?"
    r"\b(which|what)\b.{0,20}\b(stocks?|shares?|funds?|etfs?|crypto\w*|coins?|ipos?)\b.{0,30}"
    r"\b(buy|sell|invest|pick|choose|hold)\b",
    # "Best mutual fund to invest in", "top stocks for 2027"
    r"\b(best|top|safest)\b.{0,20}\b(stocks?|shares?|funds?|etfs?|crypto\w*|coins?|ipos?)\b.{0,30}"
    r"\b(to|for)\b.{0,20}\b(buy|invest|returns?|20\d\d|now|today)\b",
    # Price predictions
    r"\b(will|is)\b.{0,40}\b(go up|go down|rise|fall|crash|rally|moon)\b",
    r"\bprice target\b",
    # "Is X a good investment/buy?"
    r"\bis\b.{0,40}\ba good (investment|buy|stock|fund)\b",
    r"\b(recommend|suggest|tip)\b.{0,20}\b(me )?(a |some )?(stocks?|shares?|funds?|etfs?|crypto\w*)\b",
    r"\bwhere should i (invest|put my money)\b",
]

_INJECTION_RE = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _INJECTION]
_ADVICE_RE = [re.compile(p, re.IGNORECASE | re.DOTALL) for p in _ADVICE]

REFUSAL_ADVICE = (
    "I can't give personalised investment advice, such as which stock or fund to buy or sell, "
    "or where prices are heading. I can explain how things work, for example what a SIP, an index "
    "fund or asset allocation is, so you can decide. For a recommendation, consult a "
    "SEBI-registered investment adviser."
)
REFUSAL_SCOPE = "I can only help with questions about PPA and personal finance."
INSUFFICIENT = (
    "I couldn't find this in PPA's help articles or finance notes, so I won't guess. "
    "Try rephrasing, or ask about a PPA feature or a personal-finance topic."
)
FINANCE_DISCLAIMER = "General information only, not personal financial advice."
TRUNCATED_NOTICE = "This answer was cut short because it reached the length limit. Ask a narrower question for the rest."


class InvalidQuestion(ValueError):
    pass


def normalize_question(text: str, max_chars: int) -> str:
    """Remove control/invisible characters (a common way to hide injected text) and extra spaces."""
    text = unicodedata.normalize("NFKC", text)
    text = "".join(ch for ch in text if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < 3:
        raise InvalidQuestion("Please type a question.")
    if len(text) > max_chars:
        raise InvalidQuestion(f"Please keep questions under {max_chars} characters.")
    return text


def looks_like_injection(question: str) -> bool:
    return any(p.search(question) for p in _INJECTION_RE)


def asks_for_investment_advice(question: str) -> bool:
    return any(p.search(question) for p in _ADVICE_RE)
