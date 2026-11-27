"""Help mode "Click here" links: decided by code from the cited sections (Nov 27)."""

import pytest

from app.assistant.page_links import ACTIONS, PAGE_OF_DOC, SECTION_ACTIONS, page_links
from app.assistant.service import Citation


def cite(path, section, title="T"):
    return Citation("S1", path, title, f"{title} > {section}" if section else title)


CARD_TXN = cite("ppa/04-credit-cards.md", "Recording spending (expenses)")
BANK_TXN = cite("ppa/02-banks.md", "Recording transactions")


def test_a_question_naming_the_page_gets_the_action():
    assert page_links("how do I add a credit card transaction?", [CARD_TXN]) == ["creditcard.add_transaction"]
    assert page_links("how to delete an asset in assets page",
                      [cite("ppa/05-assets.md", "Deleting an asset")]) == ["assets.delete"]


def test_a_question_without_a_page_gets_no_link():
    assert page_links("how do I add a transaction?", [CARD_TXN]) == []


def test_sections_from_several_pages_get_no_link():
    assert page_links("add a transaction to my bank or card", [CARD_TXN, BANK_TXN]) == []


def test_unmapped_sections_link_to_the_page_and_specific_actions_win():
    on_dashboard = cite("ppa/04-credit-cards.md", "On the dashboard")
    assert page_links("where do my credit cards appear", [on_dashboard]) == ["creditcard.open"]
    assert page_links("credit card: record spending",
                      [on_dashboard, cite("ppa/04-credit-cards.md", "Adding a card"), CARD_TXN]) == \
        ["creditcard.add", "creditcard.add_transaction"]
    # Key numbers are shown in Card Details (Nov 27).
    key_numbers = cite("ppa/04-credit-cards.md", "Key numbers on a card")
    assert page_links("what is unbilled on my credit card page", [key_numbers]) == ["creditcard.details"]


def test_notes_without_a_page_are_ignored():
    finance = cite("finance/03-credit-cards-and-credit-score.md", "The billing cycle")
    assert page_links("how does credit card billing work", [finance]) == []
    assert page_links("how do I add a credit card transaction", [finance, CARD_TXN]) == ["creditcard.add_transaction"]


@pytest.mark.parametrize("key,action", sorted(SECTION_ACTIONS.items()))
def test_every_mapped_action_is_known_and_matches_its_page(key, action):
    assert action in ACTIONS and action.split(".")[0] == PAGE_OF_DOC[key[0]]


# ---- "Give me a link to ..." answered by code (Nov 27) ----------------------------------

@pytest.mark.parametrize("question,actions", [
    ("can you provide link to dashboard page", ["dashboard.open"]),
    ("can you provide link to overview page", ["dashboard.open"]),
    ("Open Overview", ["dashboard.open"]),
    ("take me to my credit cards", ["creditcard.open"]),
    ("open add transaction for credit card", ["creditcard.add_transaction"]),
    ("link to delete an asset", ["assets.delete"]),
    ("go to savings and show transaction history", ["savings.view_transactions"]),
    ("open the bank page to add a new bank", ["bank.add"]),
])
def test_navigation_requests_get_the_page_link(question, actions):
    from app.assistant.page_links import navigation_request
    assert navigation_request(question) == actions


@pytest.mark.parametrize("question", [
    "what is a credit card",                         # no navigation words
    "how do I open a bank account?",                 # wants the steps: help search answers it
    "open the bank or the credit card page",         # two pages
    "can you provide a link",                        # no page
    "open " + "the dashboard " * 20,                 # too long to be a simple request
])
def test_other_questions_are_not_navigation(question):
    from app.assistant.page_links import navigation_request
    assert navigation_request(question) is None


# ---- Seen live (Nov 27): only "Open Credit Cards" was offered ---------------------------

CARD_INTRO = cite("ppa/04-credit-cards.md", "")   # the page intro, no section


@pytest.mark.parametrize("question,actions", [
    ("i want to view transactions of axis credit card", ["creditcard.view_transactions"]),
    ("how to view transactions of credit cards", ["creditcard.view_transactions"]),
    ("how do I process billing for my credit card", ["creditcard.details"]),
    ("where are my credit card details", ["creditcard.details"]),
])
def test_the_questions_own_verb_decides_when_retrieval_is_general(question, actions):
    assert page_links(question, [CARD_INTRO]) == actions


def test_new_card_sections_are_mapped():
    viewing = cite("ppa/04-credit-cards.md", "Viewing a card's transactions and details")
    billing = cite("ppa/04-credit-cards.md", "Processing billing")
    assert page_links("credit card history", [viewing]) == ["creditcard.view_transactions"]
    assert page_links("credit card bill", [billing]) == ["creditcard.details"]


def test_details_exist_only_for_credit_cards():
    from app.assistant.page_links import navigation_request
    assert navigation_request("open my credit card details") == ["creditcard.details"]
    assert navigation_request("open my bank details") == ["bank.open"]
