from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta

from .models import (
    Asset,
    Bank,
    Saving,
    CreditCard,
    Transaction
)


def get_dashboard_summary(user_id):
    total_assets = (
        func.coalesce(
            func.sum(Asset.balance),
            0
        )
    )

    total_bank_balance = (
        func.coalesce(
            func.sum(Bank.balance),
            0
        )
    )

    total_savings = (
        func.coalesce(
            func.sum(Saving.balance),
            0
        )
    )

    total_credit_card_debt = (
        func.coalesce(
            func.sum(CreditCard.used),
            0
        )
    )

    asset_total = (
        Asset.query
        .with_entities(total_assets)
        .filter_by(user_id=user_id)
        .scalar()
        or 0
    )

    bank_total = (
        Bank.query
        .with_entities(total_bank_balance)
        .filter_by(user_id=user_id)
        .scalar()
        or 0
    )

    savings_total = (
        Saving.query
        .with_entities(total_savings)
        .filter_by(user_id=user_id)
        .scalar()
        or 0
    )

    debt_total = (
        CreditCard.query
        .with_entities(total_credit_card_debt)
        .filter_by(user_id=user_id)
        .scalar()
        or 0
    )

    net_worth = (
        asset_total
        + bank_total
        + savings_total
        - debt_total
    )

    return {
        "total_assets": float(asset_total),
        "total_bank_balance": float(bank_total),
        "total_savings": float(savings_total),
        "total_credit_card_debt": float(debt_total),
        "net_worth": float(net_worth)
    }



def get_spending_by_category(user_id, range_key="30d"):
    """
    Returns spending grouped by category.

    Matches current dashboard behavior:
    - Includes only expense transactions
    - Includes both bank and credit card expenses
    - Excludes payments, income, savings transactions,
      asset transactions, transfers, etc.
    """

    now = datetime.now(timezone.utc)

    cutoff_date = None

    if range_key == "30d":
        cutoff_date = now - timedelta(days=30)

    elif range_key == "3m":
        cutoff_date = now - relativedelta(months=3)

    elif range_key == "6m":
        cutoff_date = now - relativedelta(months=6)

    elif range_key == "1y":
        cutoff_date = now - relativedelta(years=1)

    elif range_key == "all":
        cutoff_date = None

    query = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == "expense"
    )

    if cutoff_date:
        query = query.filter(
            Transaction.date >= cutoff_date
        )

    results = (
        query.with_entities(
            func.coalesce(
                func.lower(
                    func.trim(Transaction.category)
                ),
                "uncategorized"
            ).label("category"),
            func.sum(
                func.abs(Transaction.amount)
            ).label("total")
        )
        .group_by(
            func.lower(
                func.trim(Transaction.category)
            )
        )
        .order_by(
            func.sum(
                func.abs(Transaction.amount)
            ).desc()
        )
        .all()
    )

    return [
        {
            "name": (
                row.category.title()
                if row.category
                else "Uncategorized"
            ),
            "value": float(row.total or 0)
        }
        for row in results[:12]
    ]


def get_asset_allocation(user_id):
    """
    Returns asset allocation grouped by category.
    Used by dashboard asset allocation chart.
    """

    results = (
        Asset.query
        .with_entities(
            func.coalesce(
                Asset.category,
                "Uncategorized"
            ).label("category"),
            func.sum(
                Asset.balance
            ).label("total")
        )
        .filter(
            Asset.user_id == user_id
        )
        .group_by(
            Asset.category
        )
        .order_by(
            func.sum(
                Asset.balance
            ).desc()
        )
        .all()
    )

    return [
        {
            "name": row.category or "Uncategorized",
            "value": float(row.total or 0)
        }
        for row in results
    ]