"""Help mode: "Click here" links to the PPA page or form an answer describes (Nov 27).

The model never writes links. After an answer's citations are checked, this code looks
at which help sections it cited and maps them, through a fixed table, to an ACTION NAME
such as "creditcard.add_transaction". The browser turns an action name into a link from
its own fixed list (portfolio-app/src/services/assistantLinks.js), and asks the user
which of THEIR accounts when the action needs one. So:

- no URL ever comes from the model, a help note or a transaction description;
- the account list is fetched live by the browser with the user's own login, never seen
  by the model, and Flask returns only that user's accounts;
- a link is offered only when the cited sections are all about ONE page and the
  question names that page ("how to add a credit card transaction" -> link; "how to add
  a transaction" -> no link, because it is not clear which page is meant).
"""

import re
from collections.abc import Iterable

# Help note -> page.
PAGE_OF_DOC = {
    "ppa/02-banks.md": "bank",
    "ppa/03-savings.md": "savings",
    "ppa/04-credit-cards.md": "creditcard",
    "ppa/05-assets.md": "assets",
    "ppa/06-dashboard.md": "dashboard",
}

# Section (last part of the heading) -> action. Sections not listed link to the page itself.
SECTION_ACTIONS = {
    ("ppa/02-banks.md", "Adding a bank"): "bank.add",
    ("ppa/02-banks.md", "Recording transactions"): "bank.add_transaction",
    ("ppa/02-banks.md", "Viewing and filtering history"): "bank.view_transactions",
    ("ppa/02-banks.md", "Downloading transactions"): "bank.view_transactions",
    ("ppa/02-banks.md", "Deleting a bank"): "bank.delete",
    ("ppa/03-savings.md", "Adding a savings account"): "savings.add",
    ("ppa/03-savings.md", "Deposits and withdrawals"): "savings.add_transaction",
    ("ppa/03-savings.md", "History and downloads"): "savings.view_transactions",
    ("ppa/03-savings.md", "Deleting a savings account"): "savings.delete",
    ("ppa/04-credit-cards.md", "Adding a card"): "creditcard.add",
    ("ppa/04-credit-cards.md", "Recording spending (expenses)"): "creditcard.add_transaction",
    ("ppa/04-credit-cards.md", "Recording a payment"): "creditcard.add_transaction",
    ("ppa/04-credit-cards.md", "Deleting a card"): "creditcard.delete",
    ("ppa/04-credit-cards.md", "Viewing a card's transactions and details"): "creditcard.view_transactions",
    # Process Billing changes data, so a link only opens Card Details, where its button is.
    ("ppa/04-credit-cards.md", "Processing billing"): "creditcard.details",
    ("ppa/04-credit-cards.md", "Key numbers on a card"): "creditcard.details",
    ("ppa/05-assets.md", "Adding an asset"): "assets.add",
    ("ppa/05-assets.md", "Deposits and withdrawals"): "assets.add_transaction",
    ("ppa/05-assets.md", "History, downloads and deleting"): "assets.view_transactions",
    ("ppa/05-assets.md", "Deleting an asset"): "assets.delete",
}

# The question must name the page for a link to be offered.
PAGE_WORDS = {
    "bank": r"\bbanks?\b",
    "savings": r"\bsavings?\b",
    "creditcard": r"\bcredit[\s-]?cards?\b|\bcards?\b",
    "assets": r"\bassets?\b|\binvestments?\b",
    "dashboard": r"\bdashboard\b|\boverview\b",
}

# Every action the browser knows. Anything else is never sent.
ACTIONS = frozenset(
    [f"{page}.open" for page in PAGE_WORDS]
    + [f"{page}.{verb}" for page in ("bank", "savings", "creditcard", "assets")
       for verb in ("add", "add_transaction", "view_transactions", "delete")]
    + ["creditcard.details"]
)
MAX_LINKS = 3

# ---- "Give me a link to ..." (navigation requests, Nov 27) ----------------------------
#
# "Can you provide a link to the dashboard page?" or "Open Overview" is not a question the
# help notes answer (seen live: both were refused as "not in the help articles"). Code
# answers it directly: no search, no model call, no tokens.

PAGE_NAMES = {"dashboard": "Overview (dashboard)", "creditcard": "Credit Cards", "bank": "Banks",
              "savings": "Savings", "assets": "Assets"}
NAV_PAGE_WORDS = {**PAGE_WORDS, "dashboard": r"\bdashboard\b|\boverview\b|\bhome\s*page\b"}
NAVIGATION = re.compile(
    r"\b(links?|open|go\s+to|goto|take\s+me|navigate|redirect|bring\s+me|show\s+me\s+the\s+\w+\s+page)\b",
    re.IGNORECASE)
VERBS = [
    ("add_transaction", r"\b(add|record|enter|new)\b.*\b(transactions?|expenses?|payments?|deposits?|withdrawals?)\b"),
    ("view_transactions", r"\b(view|see|show|check|history|list)\b.*\btransactions?\b|\btransactions?\s+(history|of|for|in)\b"),
    ("delete", r"\b(delete|remove|close)\b"),
    ("details", r"\bdetails?\b|\bbilling\b|\bprocess\b.*\bbill"),   # credit cards only (Card Details)
    ("add", r"\b(add|create|new)\b"),
]


def asked_action(page: str, text: str) -> str | None:
    """The form the question itself asks for on this page ("view transactions of my Axis card")."""
    if page == "dashboard":
        return None
    for verb, pattern in VERBS:
        action = f"{page}.{verb}"
        if action in ACTIONS and re.search(pattern, text, re.IGNORECASE):
            return action
    return None
MAX_NAVIGATION_CHARS = 120


def navigation_request(question: str) -> list[str] | None:
    """A request to open or link to ONE page (optionally a form on it): its action, else None."""
    text = " ".join(question.split())
    if len(text) > MAX_NAVIGATION_CHARS or not NAVIGATION.search(text):
        return None
    if re.match(r"(how|why|what|when|which|explain)\b", text, re.IGNORECASE):
        return None   # "how do I open a bank account?" wants the steps: the help search answers it (with a link)
    pages = [page for page, words in NAV_PAGE_WORDS.items() if re.search(words, text, re.IGNORECASE)]
    if len(pages) != 1:
        return None
    page = pages[0]
    return [asked_action(page, text) or f"{page}.open"]


def navigation_answer(actions: list[str]) -> str:
    page = actions[0].split(".")[0]
    return f"Here is the link to the {PAGE_NAMES[page]} page."


def page_links(question: str, citations: Iterable) -> list[str]:
    """Action names for the "Click here" links under a help answer (may be empty)."""
    actions: list[str] = []
    for citation in citations:
        page = PAGE_OF_DOC.get(citation.source_path)
        if page is None:
            continue                       # finance notes and general PPA notes: no page
        section = str(citation.section).split(" > ")[-1].strip()
        actions.append(SECTION_ACTIONS.get((citation.source_path, section), f"{page}.open"))
    pages = {action.split(".")[0] for action in actions}
    if len(pages) != 1:
        return []                          # none, or several pages: not clear where to go
    page = pages.pop()
    if not re.search(PAGE_WORDS[page], question, re.IGNORECASE):
        return []                          # e.g. "how do I add a transaction?"
    # What the question itself asks for comes first: retrieval may cite only a general section
    # (seen live: "view transactions of axis credit card" cited the page intro -> "Open Credit Cards").
    asked = asked_action(page, question)
    specific = [a for a in dict.fromkeys([asked, *actions]) if a and not a.endswith(".open")]
    return [a for a in (specific or [f"{page}.open"]) if a in ACTIONS][:MAX_LINKS]
