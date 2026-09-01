from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from datetime import datetime, timezone
import pytz

from ..models import CreditCard, CreditCardTransaction
from .. import db
from ..utils.financial_util import money 

from .credit_card_util import (
    calculate_current_cycle_start,
    get_billing_cycle_range,
)

credit_card_routes = Blueprint("credit_card_routes", __name__)

IST = pytz.timezone('Asia/Kolkata')

@credit_card_routes.route('/credit_cards', methods=['POST'])
@jwt_required()
def create_credit_card():
    user_id = int(get_jwt_identity())
    data = request.json
    
    # Validate required fields
    required_fields = ['name', 'limit']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Prevent manual setting of calculated fields
    forbidden_fields = ['used', 'available_limit', 'billed_unpaid', 'unbilled_spends']
    for field in forbidden_fields:
        if field in data:
            return jsonify({"error": f"Cannot manually set calculated field: {field}"}), 400
            
    # Additional validations
    try:
        billing_cycle_start = int(data.get('billing_cycle_start', 1))
        if not 1 <= billing_cycle_start <= 31:
            return jsonify({"error": "Billing cycle start must be between 1-31"}), 400
            
        limit = float(data['limit'])
        if limit <= 0:
            return jsonify({"error": "Limit must be positive"}), 400
            
    except ValueError as e:
        return jsonify({"error": f"Invalid numeric value: {str(e)}"}), 400
        
    try:
        card = CreditCard(
            name=data['name'],
            user_id=user_id,  # Use JWT identity
            limit=money(limit),
            billing_cycle_start=billing_cycle_start,
            used=0,
            billed_unpaid=0,
            unbilled_spends=0
        )
        
        db.session.add(card)
        db.session.commit()
        
        return jsonify({
            "message": "Credit card created successfully",
            "card": {
                "id": card.id,
                "name": card.name,
                "user_id": card.user_id,
                "limit": card.limit,
                "available_limit": card.available_limit,
                "used": card.used,
                "billed_unpaid": card.billed_unpaid,
                "unbilled_spends": card.unbilled_spends,
                "billing_cycle_start": card.billing_cycle_start,
                "total_payable": card.total_payable
            }
        }), 201
        
    except IntegrityError as e:
        db.session.rollback()
        if 'credit_card_name_key' in str(e.orig):
            return jsonify({"error": "Credit card name already exists"}), 400
        return jsonify({"error": "Database integrity error"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@credit_card_routes.route('/credit_cards', methods=['GET'])
@jwt_required()
def get_credit_cards():
    user_id = int(get_jwt_identity())
    cards = CreditCard.query.filter_by(user_id=user_id).all()
    return jsonify([{
        "id": card.id,
        "name": card.name,
        "user_id": card.user_id,
        "limit": card.limit,
        "available_limit": card.available_limit,
        "used": card.used,
        "billed_unpaid": card.billed_unpaid,
        "unbilled_spends": card.unbilled_spends,
        "billing_cycle_start": card.billing_cycle_start,
        "total_payable": card.total_payable,
        "last_payment_date": card.last_payment_date.astimezone(IST).strftime('%d%m%Y') if card.last_payment_date else None,
        "last_payment_amount": card.last_payment_amount
    } for card in cards])

@credit_card_routes.route('/credit_cards/<int:card_id>', methods=['GET'])
@jwt_required()
def get_credit_card(card_id):
    user_id = int(get_jwt_identity())
    card = CreditCard.query.filter_by(id=card_id, user_id=user_id).first()
    if not card:
        return jsonify({"error": "Credit card not found"}), 404
        
    return jsonify({
        "id": card.id,
        "name": card.name,
        "user_id": card.user_id,
        "limit": card.limit,
        "available_limit": card.available_limit,
        "used": card.used,
        "billed_unpaid": card.billed_unpaid,
        "unbilled_spends": card.unbilled_spends,
        "billing_cycle_start": card.billing_cycle_start,
        "total_payable": card.total_payable,
        "last_payment_date": card.last_payment_date.astimezone(IST).strftime('%d%m%Y') if card.last_payment_date else None,
        "last_payment_amount": card.last_payment_amount
    })

@credit_card_routes.route('/credit_cards/<int:card_id>', methods=['PUT'])
@jwt_required()
def update_credit_card(card_id):
    user_id = int(get_jwt_identity())
    card = CreditCard.query.filter_by(id=card_id, user_id=user_id).with_for_update().first()
    if not card:
        return jsonify({"error": "Credit card not found"}), 404
        
    data = request.json
    allowed_fields = {'name', 'limit', 'user_id', 'billing_cycle_start'}
    disallowed_fields = set(data.keys()) - allowed_fields
    if disallowed_fields:
        return jsonify({"error": f"Cannot update calculated fields: {', '.join(disallowed_fields)}"}), 400

    try:
        changes_made = False
        billing_cycle_changed = False

        if 'name' in data and data['name'] != card.name:
            card.name = data['name']
            changes_made = True

        if 'limit' in data:
            new_limit = float(data['limit'])
            if new_limit <= 0:
                return jsonify({"error": "Limit must be positive"}), 400
            if new_limit < card.used:
                return jsonify({"error": f"New limit cannot be less than currently used amount ({card.used})"}), 400
            if new_limit != card.limit:
                card.limit = money(new_limit)
                changes_made = True

        if 'billing_cycle_start' in data:
            new_billing_cycle = int(data['billing_cycle_start'])
            if not 1 <= new_billing_cycle <= 31:
                return jsonify({"error": "Billing cycle start must be between 1-31"}), 400
            if new_billing_cycle != card.billing_cycle_start:
                billing_cycle_changed = True
                card.billing_cycle_start = new_billing_cycle
                changes_made = True

        if not changes_made:
            return jsonify({"message": "No changes detected", "card": {
                "id": card.id,
                "name": card.name,
                "user_id": card.user_id,
                "limit": card.limit,
                "available_limit": card.available_limit,
                "used": card.used,
                "billed_unpaid": card.billed_unpaid,
                "unbilled_spends": card.unbilled_spends,
                "billing_cycle_start": card.billing_cycle_start,
                "total_payable": card.total_payable
            }}), 200

        if billing_cycle_changed:
            current_cycle_start = calculate_current_cycle_start(card.billing_cycle_start)

            card.unbilled_spends = db.session.query(
                func.sum(func.abs(CreditCardTransaction.amount))
            ).filter(
                CreditCardTransaction.credit_card_id == card.id,
                CreditCardTransaction.amount < 0,
                CreditCardTransaction.date >= current_cycle_start
            ).scalar() or 0

            payments_applied = db.session.query(
                func.sum(CreditCardTransaction.amount)
            ).filter(
                CreditCardTransaction.credit_card_id == card.id,
                CreditCardTransaction.amount > 0,
                CreditCardTransaction.date >= current_cycle_start
            ).scalar() or 0

            card.unbilled_spends = money(max(0,card.unbilled_spends - payments_applied))

        db.session.commit()
        return jsonify({
            "message": "Credit card updated successfully",
            "card": {
                "id": card.id,
                "name": card.name,
                "user_id": card.user_id,
                "limit": card.limit,
                "available_limit": card.available_limit,
                "used": card.used,
                "billed_unpaid": card.billed_unpaid,
                "unbilled_spends": card.unbilled_spends,
                "billing_cycle_start": card.billing_cycle_start,
                "total_payable": card.total_payable
            }
        })

    except ValueError as e:
        db.session.rollback()
        return jsonify({"error": f"Invalid numeric value: {str(e)}"}), 400
    except IntegrityError as e:
        db.session.rollback()
        if 'credit_card_name_key' in str(e.orig):
            return jsonify({"error": "Credit card name already exists"}), 400
        return jsonify({"error": "Database integrity error"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@credit_card_routes.route('/credit_cards/<int:card_id>', methods=['DELETE'])
@jwt_required()
def delete_credit_card(card_id):
    user_id = int(get_jwt_identity())
    card = CreditCard.query.filter_by(id=card_id, user_id=user_id).with_for_update().first()
    if not card:
        return jsonify({"error": "Credit card not found"}), 404
        
    try:
        # Check conditions for deletion
        if card.billed_unpaid != 0 or card.unbilled_spends != 0:
            return jsonify({"error": "Cannot delete credit card with unpaid balances"}), 400
            
        if card.used != 0:
            return jsonify({"error": "Cannot delete credit card with used amount"}), 400
            
        if card.available_limit != card.limit:
            return jsonify({"error": "Cannot delete credit card with used credit"}), 400
            
        # Delete all associated transactions first
        CreditCardTransaction.query.filter_by(credit_card_id=card_id).delete()
        
        # Now delete the card
        db.session.delete(card)
        db.session.commit()
        
        return jsonify({"message": "Credit card and all associated transactions deleted successfully"}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@credit_card_routes.route('/credit_cards/<int:card_id>/transactions', methods=['GET'])
@jwt_required()
def get_credit_card_transactions(card_id):
    user_id = int(get_jwt_identity())
    card = CreditCard.query.filter_by(id=card_id, user_id=user_id).first()
    if not card:
        return jsonify({"error": "Credit card not found"}), 404
        
    transactions = CreditCardTransaction.query.filter_by(credit_card_id=card_id).order_by(CreditCardTransaction.date.desc()).all()
    
    return jsonify([{
        "id": t.id,
        "amount": t.amount,
        "date": t.date.astimezone(IST).strftime('%d-%m-%Y %H:%M:%S'),
        "description": t.description,
        "category": t.category,
        "type": t.transaction_type,
        "is_payment": t.is_payment,
        "is_billed": t.is_billed
    } for t in transactions])

@credit_card_routes.route('/credit_cards/<int:card_id>/transactions', methods=['POST'])
@jwt_required()
def add_credit_card_transaction(card_id):
    user_id = int(get_jwt_identity())
    card = CreditCard.query.filter_by(id=card_id, user_id=user_id).with_for_update().first()
    if not card:
        return jsonify({"error": "Credit card not found"}), 404

    data = request.json

    # Validate required fields
    if 'amount' not in data:
        return jsonify({"error": "Amount is required"}), 400
    if 'date' not in data:
        return jsonify({"error": "Transaction date is required (DDMMYYYY format)"}), 400

    try:
        # Parse and validate date
        date_part = datetime.strptime(data['date'], '%Y-%m-%d')
        now_ist = datetime.now(IST)
        local_dt = IST.localize(datetime(
            year=date_part.year,
            month=date_part.month,
            day=date_part.day,
            hour=now_ist.hour,
            minute=now_ist.minute,
            second=now_ist.second,
            microsecond=now_ist.microsecond
        ))
        transaction_date = local_dt.astimezone(pytz.utc)
        if transaction_date > datetime.now(timezone.utc):
            return jsonify({"error": "Transaction date cannot be in the future"}), 400

        amount = float(data['amount'])
        if amount == 0:
            return jsonify({"error": "Amount cannot be zero"}), 400

        # Enforce chronological transaction order
        latest_txn = CreditCardTransaction.query.filter_by(
            credit_card_id=card.id
        ).order_by(CreditCardTransaction.date.desc()).first()

        if latest_txn:
            latest_txn_date = latest_txn.date
            if latest_txn_date.tzinfo is None:
                latest_txn_date = pytz.utc.localize(latest_txn_date)
            else:
                latest_txn_date = latest_txn_date.astimezone(pytz.utc)

            # print("\n" + "=" * 80)
            # print("NEW TRANSACTION")
            # print("transaction_date:", transaction_date)
            # print("transaction_date tzinfo:", transaction_date.tzinfo)

            # print("\nLATEST TRANSACTION")
            # print("latest_txn_date:", latest_txn_date)
            # print("latest_txn_date tzinfo:", latest_txn_date.tzinfo)

            # print("\nCOMPARISON")
            # print("transaction_date < latest_txn_date:",
            #     transaction_date < latest_txn_date)
            # print("=" * 80 + "\n")

            if transaction_date < latest_txn_date:
                return jsonify({
                    "error": "Transaction date must be on or after the last transaction's date."
                }), 400

        # Reject early payments if no expenses exist yet
        if amount > 0 and (card.used == 0 or card.available_limit == card.limit):
            return jsonify({
                "error": "Cannot add payment without any prior expenses."
            }), 400

        # Check available limit for expenses
        if amount < 0 and abs(amount) > card.available_limit:
            return jsonify({"error": "Transaction would exceed available credit limit"}), 400

        # Determine if this transaction is already past a billing cycle
        today = datetime.now(timezone.utc).date()
        txn_date = transaction_date.date()
        cycle_start, _ = get_billing_cycle_range(today, card.billing_cycle_start)

        # True if this transaction is older than the current cycle
        already_billed = amount < 0 and txn_date < cycle_start

        # Create transaction with correct is_billed
        transaction = CreditCardTransaction(
            credit_card_id=card_id,
            user_id=user_id,
            amount=amount,
            date=transaction_date,
            description=data.get('description'),
            category=data.get('category'),
            transaction_type='expense' if amount < 0 else 'payment',
            is_payment=data.get('is_payment', amount > 0),
            is_billed=(already_billed if amount < 0 else True)
        )

        # Update card balances
        if amount < 0:  # Expense
            card.used = money(card.used + abs(amount))

            current_cycle_start, current_cycle_end = get_billing_cycle_range(today, card.billing_cycle_start)

            if txn_date < current_cycle_start:
                card.billed_unpaid = money(card.billed_unpaid + abs(amount))
            else:
                card.unbilled_spends = money(card.unbilled_spends + abs(amount))

        else:  # Payment
            total_owed = card.billed_unpaid + card.unbilled_spends
            if amount > total_owed:
                return jsonify({"error": "Payment amount exceeds total owed amount"}), 400

            payment_remaining = amount

            if card.billed_unpaid > 0:
                paid = min(payment_remaining, card.billed_unpaid)
                card.billed_unpaid = money(card.billed_unpaid - paid)
                payment_remaining -= paid

            if payment_remaining > 0 and card.unbilled_spends > 0:
                paid = min(payment_remaining, card.unbilled_spends)
                card.unbilled_spends = money(card.unbilled_spends - paid)
                payment_remaining -= paid

            total_paid = amount - payment_remaining
            card.used = money(card.used - total_paid)

            if total_paid > 0:
                card.last_payment_date = transaction_date
                card.last_payment_amount = money(amount)

        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            "message": "Transaction added successfully",
            "transaction": {
                "id": transaction.id,
                "amount": transaction.amount,
                "date": transaction.date.strftime('%Y-%m-%d %H:%M:%S.%f'),
                "description": transaction.description,
                "category": transaction.category,
                "type": transaction.transaction_type,
                "is_billed": transaction.is_billed
            },
            "card": {
                "used": card.used,
                "available_limit": card.available_limit,
                "billed_unpaid": card.billed_unpaid,
                "unbilled_spends": card.unbilled_spends,
                "total_payable": card.total_payable
            }
        }), 201

    except ValueError as e:
        return jsonify({"error": f"Invalid data format: {str(e)}"}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

#When to Call This Endpoint /process_billing
#When a user views their statement (trigger it first)
#When a payment is made (optional - to ensure correct payable amount)
@credit_card_routes.route('/credit_cards/<int:card_id>/process_billing', methods=['POST'])
@jwt_required()
def process_billing(card_id):
    user_id = int(get_jwt_identity())
    card = CreditCard.query.filter_by(id=card_id, user_id=user_id).with_for_update().first()
    if not card:
        return jsonify({"error": "Credit card not found"}), 404

    try:
        today = datetime.now(timezone.utc).date()
        billing_start, billing_end = get_billing_cycle_range(today, card.billing_cycle_start)

        transactions = CreditCardTransaction.query.filter(
            CreditCardTransaction.credit_card_id == card.id
        ).order_by(CreditCardTransaction.date.asc()).all()

        billed_expenses = []
        unbilled_expenses = []
        payments = []

        for txn in transactions:
            if txn.amount > 0:
                txn.is_billed = True
                payments.append(txn)
            else:
                if txn.date.date() < billing_start:
                    txn.is_billed = True
                    billed_expenses.append(txn)
                else:
                    txn.is_billed = False
                    unbilled_expenses.append(txn)

        # Reset values
        card.billed_unpaid = money(
            sum(abs(e.amount) for e in billed_expenses)
        )

        card.unbilled_spends = money(
            sum(abs(e.amount) for e in unbilled_expenses)
        )

        card.used = money(
            card.billed_unpaid + card.unbilled_spends
        )

        # Reapply payments
        payments_applied = 0
        payment_remaining = sum(p.amount for p in payments)

        for p in payments:
            apply_amt = p.amount

            if card.billed_unpaid > 0:
                paid = min(card.billed_unpaid, apply_amt)
                card.billed_unpaid = money(card.billed_unpaid - paid)
                card.used = money(card.used - paid)
                apply_amt -= paid
                payments_applied += paid

            if apply_amt > 0 and card.unbilled_spends > 0:
                paid = min(card.unbilled_spends, apply_amt)
                card.unbilled_spends = money(card.unbilled_spends - paid)
                card.used = money(card.used - paid)
                apply_amt -= paid
                payments_applied += paid

        # Update last payment info
        if payments:
            last_payment = payments[-1]
            card.last_payment_date = last_payment.date
            card.last_payment_amount = last_payment.amount

        db.session.commit()

        return jsonify({
            "message": "Billing processed successfully",
            "card": {
                "id": card.id,
                "billed_unpaid": card.billed_unpaid,
                "unbilled_spends": card.unbilled_spends,
                "used": card.used,
                "available_limit": card.available_limit,
                "total_payable": card.total_payable
            }
        })

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500
