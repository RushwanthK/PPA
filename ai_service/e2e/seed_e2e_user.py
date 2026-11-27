"""Create a test-only user with sample data, for end-to-end tests of the assistant.

Run against a LOCAL Flask API only (it refuses any other host):

    ai_service\\.venv\\Scripts\\python ai_service\\e2e\\seed_e2e_user.py

Everything goes through Flask's own API (register, banks, cards, transactions), so the
data is created exactly as the app would create it. Safe to run more than once: an
existing user is reused and each part is added only if it is missing.

The credentials below are test values for this local fixture, not a real account.
"""

import os
import sys
from datetime import date, timedelta
from urllib.parse import urlsplit

import httpx

FLASK_URL = os.environ.get("FLASK_API_URL", "http://127.0.0.1:5000").rstrip("/")
E2E_USER = "e2e_assistant_user"
E2E_PASSWORD = "E2e-Local-Test-Only-7"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}

BANK_INCOME = [(85000, "Salary", "Salary November")]
BANK_EXPENSES = [
    (18000, "Rent", "House rent"),
    (450, "Food", "Swiggy dinner"),
    (380, "Food", "Zomato lunch"),
    (1200, "Utilities", "Electricity bill"),
    (2200, "Groceries", "BigBasket order"),
]
# (days ago, amount, category, description); card expenses are negative amounts in PPA.
# Oldest first: Flask rejects a card transaction dated before the card's latest one.
CARD_EXPENSES = [
    (40, 799, "Entertainment", "Movie tickets"),
    (20, 4999, "Shopping", "Myntra jacket"),
    (12, 1500, "Travel", "Uber rides"),
    (5, 640, "Food", "Swiggy weekend"),
    (2, 2999, "Shopping", "Amazon headphones"),
]


def main() -> None:
    host = urlsplit(FLASK_URL).hostname
    if host not in LOCAL_HOSTS:
        sys.exit(f"Refusing to seed a non-local API ({host}). This fixture is for local testing only.")

    with httpx.Client(base_url=FLASK_URL, timeout=15) as client:
        login = client.post("/login", json={"name": E2E_USER, "password": E2E_PASSWORD})
        if login.status_code != 200:
            created = client.post("/register", json={"name": E2E_USER, "password": E2E_PASSWORD,
                                                       "dob": "1995-06-15", "place": "Bengaluru"})
            if created.status_code not in (200, 201):
                sys.exit(f"Register failed: HTTP {created.status_code} {created.json().get('error')}")
            login = client.post("/login", json={"name": E2E_USER, "password": E2E_PASSWORD})
            login.raise_for_status()
        client.headers["Authorization"] = f"Bearer {login.json()['token']}"

        # Each part is added only if missing, so a half-finished run can be completed.
        if not client.get("/banks").json():
            bank = client.post("/banks", json={"name": "E2E HDFC Savings", "balance": 0}).json()
            bank_id = bank.get("id") or bank.get("bank", {}).get("id")
            for amount, category, description in BANK_INCOME:
                client.post(f"/banks/{bank_id}/transactions", json={
                    "amount": amount, "type": "income", "category": category, "description": description,
                }).raise_for_status()
            for amount, category, description in BANK_EXPENSES:
                client.post(f"/banks/{bank_id}/transactions", json={
                    "amount": amount, "type": "expense", "category": category, "description": description,
                }).raise_for_status()

        cards = client.get("/credit_cards").json()
        if cards:
            card_id = cards[0]["id"]
        else:
            created = client.post("/credit_cards", json={"name": "E2E SBI Card", "limit": 100000,
                                                         "billing_cycle_start": 1})
            created.raise_for_status()
            card_id = created.json()["card"]["id"]
        if not client.get(f"/credit_cards/{card_id}/transactions").json():
            for days_ago, amount, category, description in CARD_EXPENSES:
                day = (date.today() - timedelta(days=days_ago)).isoformat()
                client.post(f"/credit_cards/{card_id}/transactions", json={
                    "amount": -amount, "date": day, "category": category, "description": description,
                }).raise_for_status()

    print(f"'{E2E_USER}' is ready: 1 bank with {len(BANK_INCOME) + len(BANK_EXPENSES)} transactions, "
          f"1 card with {len(CARD_EXPENSES)} transactions.")


if __name__ == "__main__":
    main()
