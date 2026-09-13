from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, cast, String
from datetime import datetime, timezone
import pytz

from ..models import Bank, Saving, BankTransaction
from .. import db
from ..utils.financial_util import money

bank_routes = Blueprint("bank_routes", __name__)

IST = pytz.timezone('Asia/Kolkata')

@bank_routes.route('/banks', methods=['POST'])
@jwt_required()
def create_bank():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify({
            "error": "Bank name is required"
        }), 400

    name = name.strip()

    try:
        balance = float(data.get("balance", 0))
    except (TypeError, ValueError):
        return jsonify({
            "error": "Balance must be a valid number"
        }), 400

    if balance < 0:
        return jsonify({
            "error": "Bank balance cannot be negative"
        }), 400

    try:
        bank = Bank(
            name=name,
            user_id=user_id,
            balance=money(balance)
        )

        db.session.add(bank)
        db.session.commit()

        return jsonify({
            "message": "Bank created successfully",
            "bank": {
                "id": bank.id,
                "name": bank.name,
                "user_id": bank.user_id,
                "balance": bank.balance
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()

        if 'bank_name_key' in str(e.orig):
            return jsonify({
                "error": "Bank name already exists"
            }), 400

        return jsonify({
            "error": "Database integrity error"
        }), 400

    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to create bank"
        }), 500

@bank_routes.route('/banks', methods=['GET'])
@jwt_required()
def get_banks():
    user_id = int(get_jwt_identity())
    banks = Bank.query.filter_by(user_id=user_id).all()
    return jsonify([{
        "id": bank.id,
        "name": bank.name,
        "user_id": bank.user_id,
        "balance": bank.balance
    } for bank in banks])

@bank_routes.route('/banks/<int:bank_id>', methods=['PUT'])
@jwt_required()
def update_bank(bank_id):
    user_id = int(get_jwt_identity())

    bank = Bank.query.filter_by(
        id=bank_id,
        user_id=user_id
    ).first()

    if not bank:
        return jsonify({
            "error": "Bank not found"
        }), 404

    data = request.get_json(silent=True) or {}

    if "name" not in data:
        return jsonify({
            "error": "Bank name is required"
        }), 400

    name = data.get("name")

    if not isinstance(name, str) or not name.strip():
        return jsonify({
            "error": "Bank name is required"
        }), 400

    bank.name = name.strip()

    try:
        db.session.commit()

        return jsonify({
            "message": "Bank updated successfully",
            "bank": {
                "id": bank.id,
                "name": bank.name,
                "user_id": bank.user_id,
                "balance": bank.balance
            }
        }), 200

    except IntegrityError as e:
        db.session.rollback()

        if 'bank_name_key' in str(e.orig):
            return jsonify({
                "error": "Bank name already exists"
            }), 400

        return jsonify({
            "error": "Database integrity error"
        }), 400

    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to update bank"
        }), 500


@bank_routes.route('/banks/<int:bank_id>', methods=['DELETE'])
@jwt_required()
def delete_bank(bank_id):
    user_id = int(get_jwt_identity())
    bank = Bank.query.filter_by(id=bank_id, user_id=user_id).first()
    if not bank:
        return jsonify({"error": "Bank not found"}), 404
    
    if bank.balance != 0:
        return jsonify({"error": "Cannot delete bank with non-zero balance"}), 400
    
    # Check if any savings accounts are linked to this bank
    linked_savings = Saving.query.filter_by(bank_id=bank_id, user_id=user_id).count()
    if linked_savings > 0:
        return jsonify({
            "error": "Cannot delete bank because it has linked savings accounts",
            "linked_savings_count": linked_savings
        }), 400
    
    db.session.delete(bank)
    db.session.commit()
    return jsonify({"message": "Bank deleted successfully"}), 200


@bank_routes.route('/banks/<int:bank_id>/transactions', methods=['POST'])
@jwt_required()
def add_bank_transaction(bank_id):
    user_id = int(get_jwt_identity())

    bank = Bank.query.filter_by(
        id=bank_id,
        user_id=user_id
    ).first()

    if not bank:
        return jsonify({
            "error": "Bank not found"
        }), 404

    data = request.get_json(silent=True) or {}

    if "amount" not in data:
        return jsonify({
            "error": "Amount is required"
        }), 400

    try:
        amount = float(data["amount"])
    except (TypeError, ValueError):
        return jsonify({
            "error": "Amount must be a valid number"
        }), 400

    if amount <= 0:
        return jsonify({
            "error": "Amount must be greater than 0"
        }), 400

    transaction_type = data.get("type", "income")

    if transaction_type not in ("income", "expense"):
        return jsonify({
            "error": "Invalid transaction type"
        }), 400

    if transaction_type == "expense" and bank.balance < amount:
        return jsonify({
            "error": "Insufficient balance"
        }), 400

    try:
        if transaction_type == "income":
            new_balance = money(bank.balance + amount)
        else:
            new_balance = money(bank.balance - amount)

        transaction = BankTransaction(
            bank_id=bank_id,
            user_id=user_id,
            amount=amount,
            description=data.get("description", ""),
            category=data.get("category", ""),
            transaction_type=transaction_type,
            bank_balance_after=new_balance,
            date=datetime.now(timezone.utc)
        )

        bank.balance = new_balance

        db.session.add(transaction)

        # Force SQLAlchemy to execute the INSERT here.
        # This makes DB problems appear at this exact point.
        db.session.flush()

        db.session.commit()

        return jsonify({
            "message": "Transaction added successfully",
            "balance": new_balance,
            "transaction": {
                "id": transaction.id,
                "amount": transaction.amount,
                "type": transaction.transaction_type,
                "description": transaction.description,
                "category": transaction.category,
                "date": transaction.date.isoformat(),
                "balance_after": new_balance
            }
        }), 201

    except IntegrityError:
        db.session.rollback()

        return jsonify({
            "error": "Unable to save bank transaction because of a database integrity error"
        }), 400

    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to add bank transaction"
        }), 500

@bank_routes.route('/banks/<int:bank_id>/transactions', methods=['GET'])
@jwt_required()
def get_bank_transactions(bank_id):
    user_id = int(get_jwt_identity())
    bank = Bank.query.filter_by(id=bank_id, user_id=user_id).first()
    if not bank:
        return jsonify({"error": "Bank not found"}), 404

    # Pagination is deliberately handled by the backend so the browser never
    # has to load the bank's entire transaction history at once.
    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = int(request.args.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25

    # Keep the API bounded even if a client sends an excessively large value.
    page_size = min(max(page_size, 1), 100)

    search = (request.args.get('search') or '').strip()
    transaction_type = (request.args.get('type') or '').strip().lower()

    query = BankTransaction.query.filter(
        BankTransaction.bank_id == bank_id,
        BankTransaction.user_id == user_id,
    )

    if transaction_type:
        if transaction_type not in ('income', 'expense'):
            return jsonify({
                "error": "Invalid transaction type filter"
            }), 400
        query = query.filter(BankTransaction.transaction_type == transaction_type)

    if search:
        # The global search intentionally covers the fields a user can see
        # in the bank transaction table. This means search applies to the
        # complete bank history in the database, not only the current page.
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            BankTransaction.description.ilike(search_pattern),
            BankTransaction.category.ilike(search_pattern),
            BankTransaction.transaction_type.ilike(search_pattern),
            cast(BankTransaction.amount, String).ilike(search_pattern),
            cast(BankTransaction.date, String).ilike(search_pattern),
            cast(BankTransaction.bank_balance_after, String).ilike(search_pattern),
        ))

    # id makes ordering deterministic when two transactions have the same
    # timestamp. The composite DB index added for this endpoint supports
    # this common bank-history access pattern efficiently.
    query = query.order_by(
        BankTransaction.date.desc(),
        BankTransaction.id.desc(),
    )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    # A filtered result can shrink while the user is on a later page. Move
    # that request back to the last valid page instead of returning nothing.
    if total_pages and page > total_pages:
        page = total_pages

    transactions = query.offset((page - 1) * page_size).limit(page_size).all()

    return jsonify({
        "transactions": [{
            "id": tx.id,
            "amount": tx.amount,
            "description": tx.description or '',
            "category": tx.category or '',
            "transaction_type": tx.transaction_type,
            "date": tx.date.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
            "bank_balance_after": tx.bank_balance_after
        } for tx in transactions],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    })

@bank_routes.route('/banks/dropdown', methods=['GET'])
@jwt_required()
def get_banks_dropdown():
    user_id = int(get_jwt_identity())
    banks = Bank.query.filter_by(user_id=user_id).all()
    return jsonify([{'id': bank.id, 'name': bank.name} for bank in banks])

@bank_routes.route('/bank_balance', methods=['GET'])
@jwt_required()
def get_bank_balance():
    bank_id = request.args.get("bank_id")

    if not bank_id:
        return jsonify({
            "error": "bank_id parameter is required"
        }), 400

    user_id = int(get_jwt_identity())

    bank = Bank.query.filter_by(
        id=bank_id,
        user_id=user_id
    ).first()

    if not bank:
        return jsonify({
            "error": "Bank not found"
        }), 404
    
    return jsonify({
        "id": bank.id,           # Bank ID
        "name": bank.name,        # Bank name
        "balance": bank.balance   # Current balance
    })
