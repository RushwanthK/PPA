---
title: Credit cards in PPA
category: ppa
audience: PPA users
last_reviewed: 2026-11-23
---

# Credit cards in PPA

The **Credit Cards** page tracks what you have spent on each card, what you owe, and how much limit is left.

## Adding a card

Enter:

- **Card name:** must be unique.
- **Credit limit:** must be positive.
- **Billing cycle start day:** the day of the month (1 to 31) on which a new billing cycle starts.

Calculated values such as used amount, billed and unbilled amounts cannot be typed in. PPA computes them from transactions.

## Key numbers on a card

| Field | Meaning |
|---|---|
| **Limit** | Maximum the bank lets you spend on the card |
| **Used** | Total currently owed on the card |
| **Available limit** | Limit minus used |
| **Unbilled spends** | Spending in the current billing cycle, not yet on a bill |
| **Billed unpaid** | Spending from earlier cycles that is on a bill and not yet paid |
| **Total payable** | The amount due now. It equals billed unpaid |
| **Last payment** | Date and amount of your most recent payment |

## Recording spending (expenses)

Add an expense when you use the card. It increases **used** and reduces **available limit**.

- It cannot exceed the available limit.
- The date cannot be in the future, and it must be on or after the card's latest transaction date. This keeps the history in order.
- If the date falls before the current billing cycle started, the expense counts as already **billed**. Otherwise it is **unbilled**.

## Recording a payment

Add a payment when you pay the card bill. A payment:

- is applied to **billed unpaid** first, then to **unbilled spends**;
- reduces **used** and frees up available limit;
- cannot be larger than the total owed;
- cannot be added on a card that has no spending yet.

## Viewing a card's transactions and details

On the **Credit Cards** page, each card in the list has two buttons:

- **Add Transaction:** record a new expense or payment for that card.
- **Details:** opens the **Card Details** dialog for that card. It shows the card's key numbers (limit, used, available limit, unbilled spends, billed unpaid, total payable and last payment) and has these buttons:
  - **View Transactions:** the card's full transaction history, which can be filtered and downloaded.
  - **Process Billing:** recalculates billed and unbilled amounts (see below).
  - **Edit Card:** change the card's name, limit or billing cycle start day.
  - **Delete Card:** remove the card (only when nothing is owed).

So to see one card's transactions, click **Details** on that card, then **View Transactions**.

## Processing billing

**Process billing** recalculates a card from its transaction history. Expenses before the current cycle's start date become billed, newer ones stay unbilled, and all payments are re-applied in date order. Use it after a new billing cycle starts so the billed and unbilled amounts reflect the new bill.

## Deleting a card

A card can only be deleted when nothing is owed on it: no billed unpaid amount, no unbilled spends and no used credit.

## On the dashboard

The amount owed on your cards is counted as **credit card debt** and is subtracted when calculating your net worth.
