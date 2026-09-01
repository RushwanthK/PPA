from io import BytesIO

from openpyxl import Workbook

from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Table,
    TableStyle,
    Paragraph,
    Spacer
)

from ..models import (
    Transaction,
    BankTransaction,
    CreditCardTransaction,
    AssetTransaction,
    SavingTransaction,
    Bank,
    CreditCard,
    Asset,
    Saving,
    TransferTransaction
)
from .. import db

def get_transaction_export_rows(user_id):
    """
    Return normalized transaction rows for the specified user.

    Includes all Transaction subclasses:
    - BankTransaction
    - CreditCardTransaction
    - AssetTransaction
    - SavingTransaction
    """

    transactions = (
        db.session.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .order_by(Transaction.date.asc(), Transaction.id.asc())
        .all()
    )

    rows = []

    for transaction in transactions:
        account_type = ""
        account_name = ""
        balance_after = ""

        if isinstance(transaction, BankTransaction):
            account_type = "Bank"
            bank = db.session.get(Bank, transaction.bank_id)

            if bank:
                account_name = bank.name

            balance_after = transaction.bank_balance_after

        elif isinstance(transaction, CreditCardTransaction):
            account_type = "Credit Card"
            card = db.session.get(
                CreditCard,
                transaction.credit_card_id
            )

            if card:
                account_name = card.name

            balance_after = transaction.card_balance_after

        elif isinstance(transaction, AssetTransaction):
            account_type = "Asset"
            asset = db.session.get(
                Asset,
                transaction.asset_id
            )

            if asset:
                account_name = asset.name

            balance_after = transaction.asset_balance_after

        elif isinstance(transaction, SavingTransaction):
            account_type = "Saving"
            saving = db.session.get(
                Saving,
                transaction.saving_id
            )

            if saving:
                account_name = saving.name

            balance_after = transaction.saving_balance_after

        else:
            account_type = "Transaction"

        rows.append({
            "id": transaction.id,
            "date": (
                transaction.date.strftime("%Y-%m-%d %H:%M:%S")
                if transaction.date
                else ""
            ),
            "amount": transaction.amount,
            "transaction_type": transaction.transaction_type or "",
            "description": transaction.description or "",
            "category": transaction.category or "",
            "account_type": account_type,
            "account_name": account_name,
            "balance_after": balance_after
        })

    return rows


def get_transfer_export_rows(user_id):
    """
    Return transfer transaction rows for the specified user.
    """

    transfers = (
        db.session.query(TransferTransaction)
        .filter(TransferTransaction.user_id == user_id)
        .order_by(
            TransferTransaction.date.asc(),
            TransferTransaction.id.asc()
        )
        .all()
    )

    rows = []

    for transfer in transfers:
        rows.append({
            "id": transfer.id,
            "date": (
                transfer.date.strftime("%Y-%m-%d %H:%M:%S")
                if transfer.date
                else ""
            ),
            "amount": transfer.amount,
            "from_account_type": (
                transfer.from_account_type or ""
            ),
            "from_account_id": (
                transfer.from_account_id or ""
            ),
            "to_account_type": (
                transfer.to_account_type or ""
            ),
            "to_account_id": (
                transfer.to_account_id or ""
            ),
            "description": transfer.description or "",
            "fee": transfer.fee or 0
        })

    return rows


def get_total_transaction_history_count(user_id):
    transaction_count = (
        db.session.query(Transaction)
        .filter(Transaction.user_id == user_id)
        .count()
    )

    transfer_count = (
        db.session.query(TransferTransaction)
        .filter(TransferTransaction.user_id == user_id)
        .count()
    )

    return transaction_count + transfer_count


def create_transaction_excel(user_id):
    transactions = get_transaction_export_rows(user_id)
    transfers = get_transfer_export_rows(user_id)

    workbook = Workbook()

    # -----------------------------
    # Transactions worksheet
    # -----------------------------
    transaction_sheet = workbook.active
    transaction_sheet.title = "Transactions"

    transaction_headers = [
        "ID",
        "Date",
        "Amount",
        "Transaction Type",
        "Description",
        "Category",
        "Account Type",
        "Account Name",
        "Balance After"
    ]

    transaction_sheet.append(transaction_headers)

    for row in transactions:
        transaction_sheet.append([
            row["id"],
            row["date"],
            row["amount"],
            row["transaction_type"],
            row["description"],
            row["category"],
            row["account_type"],
            row["account_name"],
            row["balance_after"]
        ])

    # -----------------------------
    # Transfers worksheet
    # -----------------------------
    transfer_sheet = workbook.create_sheet("Transfers")

    transfer_headers = [
        "ID",
        "Date",
        "Amount",
        "From Account Type",
        "From Account ID",
        "To Account Type",
        "To Account ID",
        "Description",
        "Fee"
    ]

    transfer_sheet.append(transfer_headers)

    for row in transfers:
        transfer_sheet.append([
            row["id"],
            row["date"],
            row["amount"],
            row["from_account_type"],
            row["from_account_id"],
            row["to_account_type"],
            row["to_account_id"],
            row["description"],
            row["fee"]
        ])

    # Make columns readable.
    for sheet in workbook.worksheets:
        for column_cells in sheet.columns:
            max_length = 0

            for cell in column_cells:
                value = "" if cell.value is None else str(cell.value)
                max_length = max(
                    max_length,
                    len(value)
                )

            column_letter = column_cells[0].column_letter

            sheet.column_dimensions[
                column_letter
            ].width = min(max_length + 2, 40)

        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions

    output = BytesIO()

    workbook.save(output)

    output.seek(0)

    return output


def create_transaction_pdf(user_id):
    transactions = get_transaction_export_rows(user_id)
    transfers = get_transfer_export_rows(user_id)

    output = BytesIO()

    document = SimpleDocTemplate(
        output,
        pagesize=landscape(A4),
        rightMargin=10 * mm,
        leftMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm
    )

    styles = getSampleStyleSheet()

    elements = []

    elements.append(
        Paragraph(
            "PPA Transaction History Backup",
            styles["Title"]
        )
    )

    elements.append(
        Spacer(1, 5 * mm)
    )

    # -----------------------------
    # Transactions
    # -----------------------------
    elements.append(
        Paragraph(
            "Transactions",
            styles["Heading2"]
        )
    )

    transaction_data = [[
        "ID",
        "Date",
        "Amount",
        "Type",
        "Description",
        "Category",
        "Account",
        "Account Name",
        "Balance After"
    ]]

    for row in transactions:
        transaction_data.append([
            str(row["id"]),
            row["date"],
            str(row["amount"]),
            row["transaction_type"],
            row["description"],
            row["category"],
            row["account_type"],
            row["account_name"],
            str(row["balance_after"])
        ])

    if len(transaction_data) == 1:
        transaction_data.append([
            "",
            "",
            "",
            "",
            "No transaction records",
            "",
            "",
            "",
            ""
        ])

    transaction_table = Table(
        transaction_data,
        repeatRows=1
    )

    transaction_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                7
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            )
        ])
    )

    elements.append(transaction_table)

    elements.append(
        Spacer(1, 8 * mm)
    )

    # -----------------------------
    # Transfers
    # -----------------------------
    elements.append(
        Paragraph(
            "Transfers",
            styles["Heading2"]
        )
    )

    transfer_data = [[
        "ID",
        "Date",
        "Amount",
        "From Type",
        "From ID",
        "To Type",
        "To ID",
        "Description",
        "Fee"
    ]]

    for row in transfers:
        transfer_data.append([
            str(row["id"]),
            row["date"],
            str(row["amount"]),
            row["from_account_type"],
            str(row["from_account_id"]),
            row["to_account_type"],
            str(row["to_account_id"]),
            row["description"],
            str(row["fee"])
        ])

    if len(transfer_data) == 1:
        transfer_data.append([
            "",
            "",
            "",
            "",
            "",
            "",
            "",
            "No transfer records",
            ""
        ])

    transfer_table = Table(
        transfer_data,
        repeatRows=1
    )

    transfer_table.setStyle(
        TableStyle([
            (
                "BACKGROUND",
                (0, 0),
                (-1, 0),
                colors.lightgrey
            ),
            (
                "GRID",
                (0, 0),
                (-1, -1),
                0.5,
                colors.grey
            ),
            (
                "VALIGN",
                (0, 0),
                (-1, -1),
                "TOP"
            ),
            (
                "FONTSIZE",
                (0, 0),
                (-1, -1),
                7
            ),
            (
                "BOTTOMPADDING",
                (0, 0),
                (-1, -1),
                4
            ),
            (
                "TOPPADDING",
                (0, 0),
                (-1, -1),
                4
            )
        ])
    )

    elements.append(transfer_table)

    document.build(elements)

    output.seek(0)

    return output
