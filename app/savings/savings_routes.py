from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from sqlalchemy import String, cast, or_
from datetime import datetime, timezone
import math
import pytz

from ..models import Bank, Saving, SavingTransaction
from .. import db
from ..utils.financial_util import money

savings_routes = Blueprint("savings_routes", __name__)

IST = pytz.timezone('Asia/Kolkata')

@savings_routes.route('/savings', methods=['POST'])
@jwt_required()
def create_saving():
    user_id = int(get_jwt_identity())
    data = request.get_json(silent=True) or {}

    # Validate saving name.
    if not data.get('name') or not data['name'].strip():
        return jsonify({
            "error": "Saving account name is required"
        }), 400

    # Balance is system-controlled.
    if 'balance' in data:
        return jsonify({
            "error": (
                "Balance cannot be set during savings creation. "
                "Use transactions instead."
            )
        }), 400

    # Savings must always be linked to a bank.
    if not data.get('bank_id'):
        return jsonify({
            "error": "Savings account must be linked to a bank"
        }), 400

    bank = Bank.query.filter_by(
        id=data['bank_id'],
        user_id=user_id
    ).first()

    if not bank:
        return jsonify({
            "error": "Bank not found"
        }), 404

    saving = Saving(
        name=data['name'].strip(),
        user_id=user_id,
        bank_id=data['bank_id'],
        balance=0
    )

    try:
        db.session.add(saving)
        db.session.commit()

        return jsonify({
            "message": "Saving account created!",
            "saving": {
                "id": saving.id,
                "name": saving.name,
                "user_id": saving.user_id,
                "bank_id": saving.bank_id,
                "balance": saving.balance
            }
        }), 201

    except IntegrityError as e:
        db.session.rollback()

        if 'saving_name_key' in str(e.orig):
            return jsonify({
                "error": "Saving account name already exists"
            }), 400

        return jsonify({
            "error": "Database integrity error"
        }), 400

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@savings_routes.route('/savings', methods=['GET'])
@jwt_required()
def get_savings():
    user_id = int(get_jwt_identity())
    savings = Saving.query.filter_by(user_id=user_id).all()
    return jsonify([
        {
            "id": saving.id,
            "name": saving.name,
            "user_id": saving.user_id,
            "bank_id": saving.bank_id,
            "bank_name": saving.bank.name if saving.bank else None,
            "balance": saving.balance
        } 
        for saving in savings
    ])

@savings_routes.route('/savings/<int:saving_id>', methods=['PUT'])
@jwt_required()
def update_saving(saving_id):
    user_id = int(get_jwt_identity())

    saving = Saving.query.filter_by(
        id=saving_id,
        user_id=user_id
    ).first()

    if not saving:
        return jsonify({
            "error": "Saving account not found"
        }), 404

    data = request.get_json(silent=True) or {}

    # Balance is system-controlled.
    # It must be changed only through transactions.
    if 'balance' in data:
        return jsonify({
            "error": (
                "Balance cannot be updated directly. "
                "Use transactions instead."
            )
        }), 400

    # Validate name when it is supplied.
    if 'name' in data:
        if not data['name'] or not data['name'].strip():
            return jsonify({
                "error": "Saving account name is required"
            }), 400

    # Validate bank when it is supplied.
    if 'bank_id' in data:
        if not data['bank_id']:
            return jsonify({
                "error": "Savings account must remain linked to a bank"
            }), 400

    old_bank = None
    new_bank = None

    # Validate a bank change completely BEFORE modifying
    # either bank or the saving.
    if 'bank_id' in data and data['bank_id'] != saving.bank_id:
        new_bank = Bank.query.filter_by(
            id=data['bank_id'],
            user_id=user_id
        ).first()

        if not new_bank:
            return jsonify({
                "error": "New bank not found"
            }), 404

        if saving.balance > 0:
            old_bank = Bank.query.filter_by(
                id=saving.bank_id,
                user_id=user_id
            ).first()

            if not old_bank:
                return jsonify({
                    "error": "Linked bank account not found"
                }), 404

            if new_bank.balance < saving.balance:
                return jsonify({
                    "error": (
                        "New bank has insufficient funds "
                        "for this transfer"
                    )
                }), 400

    try:
        # All validation has passed.
        # Now perform the actual changes.

        if new_bank is not None and saving.balance > 0:
            old_bank.balance = money(
                old_bank.balance + saving.balance
            )

            new_bank.balance = money(
                new_bank.balance - saving.balance
            )

        if 'bank_id' in data:
            saving.bank_id = data['bank_id']

        if 'name' in data:
            saving.name = data['name'].strip()

        db.session.commit()

        return jsonify({
            "message": "Saving account updated successfully",
            "saving": {
                "id": saving.id,
                "name": saving.name,
                "user_id": saving.user_id,
                "bank_id": saving.bank_id,
                "balance": saving.balance
            }
        }), 200

    except IntegrityError as e:
        db.session.rollback()

        if 'saving_name_key' in str(e.orig):
            return jsonify({
                "error": "Saving account name already exists"
            }), 400

        return jsonify({
            "error": "Database integrity error"
        }), 400

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@savings_routes.route('/savings/<int:saving_id>/transactions', methods=['POST'])
@jwt_required()
def add_saving_transaction(saving_id):
    user_id = int(get_jwt_identity())

    saving = Saving.query.filter_by(
        id=saving_id,
        user_id=user_id
    ).first()

    if not saving:
        return jsonify({
            "error": "Saving account not found"
        }), 404

    # Safety check - savings must be linked to a bank.
    if not saving.bank_id:
        return jsonify({
            "error": "Savings account is not linked to a bank"
        }), 400

    data = request.get_json(silent=True) or {}

    if 'amount' not in data:
        return jsonify({
            "error": "Amount is required"
        }), 400

    try:
        amount = float(data['amount'])
    except (TypeError, ValueError):
        return jsonify({
            "error": "Invalid amount"
        }), 400

    # Reject NaN and Infinity.
    if not math.isfinite(amount):
        return jsonify({
            "error": "Invalid amount"
        }), 400

    if amount <= 0:
        return jsonify({
            "error": "Amount must be greater than zero"
        }), 400

    transaction_type = data.get('type', 'deposit')

    if transaction_type not in ['deposit', 'withdrawal']:
        return jsonify({
            "error": (
                "Transaction type must be deposit or withdrawal"
            )
        }), 400

    if (
        transaction_type == 'withdrawal'
        and saving.balance < amount
    ):
        return jsonify({
            "error": "Insufficient balance"
        }), 400

    bank = Bank.query.filter_by(
        id=saving.bank_id,
        user_id=user_id
    ).first()

    if not bank:
        return jsonify({
            "error": "Linked bank account not found"
        }), 404

    # Deposit into savings = money leaves the bank.
    if (
        transaction_type == 'deposit'
        and bank.balance < amount
    ):
        return jsonify({
            "error": "Insufficient bank balance"
        }), 400

    if transaction_type == 'deposit':
        new_saving_balance = money(
            saving.balance + amount
        )
        new_bank_balance = money(
            bank.balance - amount
        )
    else:
        new_saving_balance = money(
            saving.balance - amount
        )
        new_bank_balance = money(
            bank.balance + amount
        )

    transaction = SavingTransaction(
        saving_id=saving_id,
        user_id=user_id,
        amount=amount,
        description=data.get('description'),
        category=data.get('category'),
        transaction_type=transaction_type,
        saving_balance_after=new_saving_balance,
        date=datetime.now(timezone.utc)
    )

    try:
        saving.balance = new_saving_balance
        bank.balance = new_bank_balance

        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            "message": "Transaction added",
            "saving_balance": new_saving_balance,
            "bank_balance": new_bank_balance
        }), 201

    except Exception as e:
        db.session.rollback()

        return jsonify({
            "error": f"Server error: {str(e)}"
        }), 500

@savings_routes.route('/savings/<int:saving_id>/transactions', methods=['GET'])
@jwt_required()
def get_saving_transactions(saving_id):
    user_id = int(get_jwt_identity())
    saving = Saving.query.filter_by(id=saving_id, user_id=user_id).first()
    if not saving:
        return jsonify({"error": "Saving account not found"}), 404

    # Keep the original list response when no pagination/filter parameters are
    # supplied. This preserves backward compatibility for existing API users
    # while allowing the refactored frontend to opt into server-side paging.
    uses_pagination = any(
        key in request.args
        for key in ('page', 'page_size', 'search', 'type')
    )

    if not uses_pagination:
        transactions = SavingTransaction.query.filter_by(
            saving_id=saving_id,
            user_id=user_id,
        ).order_by(
            SavingTransaction.date.desc(),
            SavingTransaction.id.desc(),
        ).all()

        return jsonify([
            {
                "id": tx.id,
                "amount": tx.amount,
                "description": tx.description or '',
                "category": tx.category or '',
                "transaction_type": tx.transaction_type,
                "date": tx.date.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                "saving_balance_after": tx.saving_balance_after
            }
            for tx in transactions
        ])

    try:
        page = max(int(request.args.get('page', 1)), 1)
    except (TypeError, ValueError):
        page = 1

    try:
        page_size = int(request.args.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25

    page_size = min(max(page_size, 1), 100)

    search = (request.args.get('search') or '').strip()
    transaction_type = (request.args.get('type') or '').strip().lower()

    query = SavingTransaction.query.filter(
        SavingTransaction.saving_id == saving_id,
        SavingTransaction.user_id == user_id,
    )

    if transaction_type:
        if transaction_type not in ('deposit', 'withdrawal'):
            return jsonify({
                "error": "Invalid transaction type filter"
            }), 400

        query = query.filter(
            SavingTransaction.transaction_type == transaction_type
        )

    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            SavingTransaction.description.ilike(search_pattern),
            SavingTransaction.category.ilike(search_pattern),
            SavingTransaction.transaction_type.ilike(search_pattern),
            cast(SavingTransaction.amount, String).ilike(search_pattern),
            cast(SavingTransaction.date, String).ilike(search_pattern),
            cast(
                SavingTransaction.saving_balance_after,
                String,
            ).ilike(search_pattern),
        ))

    query = query.order_by(
        SavingTransaction.date.desc(),
        SavingTransaction.id.desc(),
    )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size

    if total_pages and page > total_pages:
        page = total_pages

    transactions = (
        query
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return jsonify({
        "transactions": [
            {
                "id": tx.id,
                "amount": tx.amount,
                "description": tx.description or '',
                "category": tx.category or '',
                "transaction_type": tx.transaction_type,
                "date": tx.date.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
                "saving_balance_after": tx.saving_balance_after,
            }
            for tx in transactions
        ],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    })

@savings_routes.route('/savings/<int:saving_id>', methods=['DELETE'])
@jwt_required()
def delete_saving(saving_id):
    user_id = int(get_jwt_identity())

    saving = Saving.query.filter_by(
        id=saving_id,
        user_id=user_id
    ).first()

    if not saving:
        return jsonify({
            'error': 'Saving account not found'
        }), 404

    if saving.balance != 0:
        return jsonify({
            'error': (
                'Saving account cannot be deleted because '
                'its balance is not zero.'
            )
        }), 400

    try:
        # Delete the saving's transaction history first.
        SavingTransaction.query.filter_by(
            saving_id=saving_id
        ).delete(
            synchronize_session=False
        )

        db.session.delete(saving)
        db.session.commit()

        return jsonify({
            'message': 'Saving account deleted successfully'
        }), 200

    except Exception as e:
        db.session.rollback()

        return jsonify({
            'error': f'Server error: {str(e)}'
        }), 500
