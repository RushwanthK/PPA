from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta, timezone
from dateutil.relativedelta import relativedelta
from sqlalchemy import func
from . import db
from .models import (User, CreditCard, Bank, Asset, Saving,
                    Transaction, BankTransaction, CreditCardTransaction,
                    AssetTransaction, SavingTransaction, TransferTransaction)
import pytz
IST = pytz.timezone('Asia/Kolkata')

routes = Blueprint('routes', __name__)

# Utility functions
def parse_date(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").date()

# Home route
@routes.route('/')
def home():
    return "Welcome to the Personal Portfolio App!"

# ========== USER ROUTES ==========
@routes.route('/users', methods=['POST'])
def create_user():
    data = request.json
    try:
        new_user = User(
            name=data['name'],
            age=data['age'],
            dob=parse_date(data['dob']),
            place=data['place']
        )
        db.session.add(new_user)
        db.session.commit()
        return jsonify({
            'id': new_user.id,
            'name': new_user.name,
            'age': new_user.age,
            'dob': new_user.dob.strftime("%Y-%m-%d"),
            'place': new_user.place
        }), 201
    except ValueError:
        return jsonify({"error": "Invalid date format. Use 'YYYY-MM-DD'."}), 400


@routes.route('/users', methods=['GET'])
def get_users():
    users = User.query.all()
    return jsonify([{
        'id': user.id,
        'name': user.name,
        'age': user.age,
        'dob': user.dob.strftime("%Y-%m-%d"),
        'place': user.place
    } for user in users])

@routes.route('/users/<int:id>', methods=['PUT'])
def update_user(id):
    data = request.json
    user = User.query.get(id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    try:
        user.name = data['name']
        user.age = data['age']
        user.dob = parse_date(data['dob'])
        user.place = data['place']
        db.session.commit()
        return jsonify({
            'id': user.id,
            'name': user.name,
            'age': user.age,
            'dob': user.dob.strftime("%Y-%m-%d"),
            'place': user.place
        }), 200
    except ValueError:
        return jsonify({"error": "Invalid date format. Use 'YYYY-MM-DD'."}), 400

@routes.route('/users/<int:id>', methods=['DELETE'])
def delete_user(id):
    user = User.query.get(id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    
    db.session.delete(user)
    db.session.commit()
    return jsonify({'message': 'User deleted successfully'}), 200

@routes.route('/users/<int:id>/can_delete', methods=['GET'])
def can_delete_user(id):
    user = User.query.get(id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    # Check all associated balances
    has_bank_balances = any(bank.balance != 0 for bank in user.banks)
    has_asset_balances = any(asset.balance != 0 for asset in user.assets)
    has_saving_balances = any(saving.balance != 0 for saving in user.savings)
    has_credit_balances = any(card.balance != 0 for card in user.credit_cards)
    
    can_delete = not (has_bank_balances or has_asset_balances or 
                     has_saving_balances or has_credit_balances)
    
    return jsonify({
        "can_delete": can_delete,
        "has_bank_balances": has_bank_balances,
        "has_asset_balances": has_asset_balances,
        "has_saving_balances": has_saving_balances,
        "has_credit_balances": has_credit_balances
    })

# ========== CREDIT CARD ROUTES ==========
@routes.route('/credit_cards', methods=['POST'])
def create_credit_card():
    data = request.json
    
    # Validate required fields
    required_fields = ['name', 'user_id', 'limit']
    for field in required_fields:
        if field not in data:
            return jsonify({"error": f"Missing required field: {field}"}), 400
    
    # Validate user exists
    if not User.query.get(data['user_id']):
        return jsonify({"error": "User not found"}), 404
        
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
            user_id=data['user_id'],
            limit=limit,
            billing_cycle_start=billing_cycle_start,
            used=0,  # Initialize as 0
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
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500



@routes.route('/credit_cards', methods=['GET'])
def get_credit_cards():
    cards = CreditCard.query.all()
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
        "last_payment_date": card.last_payment_date.strftime('%d%m%Y') if card.last_payment_date else None,
        "last_payment_amount": card.last_payment_amount
    } for card in cards])

@routes.route('/credit_cards/<int:card_id>', methods=['GET'])
def get_credit_card(card_id):
    card = CreditCard.query.get(card_id)
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
        "last_payment_date": card.last_payment_date.strftime('%d%m%Y') if card.last_payment_date else None,
        "last_payment_amount": card.last_payment_amount
    })

@routes.route('/users/<int:user_id>/credit_cards', methods=['GET'])
def get_user_credit_cards(user_id):
    if not User.query.get(user_id):
        return jsonify({"error": "User not found"}), 404
        
    cards = CreditCard.query.filter_by(user_id=user_id).all()
    return jsonify([{
        "id": card.id,
        "name": card.name,
        "limit": card.limit,
        "available_limit": card.available_limit,
        "used": card.used,
        "billed_unpaid": card.billed_unpaid,
        "unbilled_spends": card.unbilled_spends,
        "billing_cycle_start": card.billing_cycle_start,
        "total_payable": card.total_payable
    } for card in cards])

@routes.route('/credit_cards/<int:card_id>', methods=['PUT'])
def update_credit_card(card_id):
    # Lock the card row immediately
    card = CreditCard.query.with_for_update().get(card_id)
    if not card:
        return jsonify({"error": "Credit card not found"}), 404
        
    data = request.json
    
    # List of allowed fields to update
    allowed_fields = {'name', 'user_id', 'limit', 'billing_cycle_start'}
    
    # Check for disallowed fields
    disallowed_fields = set(data.keys()) - allowed_fields
    if disallowed_fields:
        return jsonify({"error": f"Cannot update calculated fields: {', '.join(disallowed_fields)}"}), 400
    
    try:
        changes_made = False
        billing_cycle_changed = False
        
        if 'name' in data and data['name'] != card.name:
            card.name = data['name']
            changes_made = True
            
        if 'user_id' in data and data['user_id'] != card.user_id:
            # Validate new user exists
            if not User.query.get(data['user_id']):
                return jsonify({"error": "User not found"}), 404
            card.user_id = data['user_id']
            changes_made = True
            
        if 'limit' in data:
            new_limit = float(data['limit'])
            if new_limit <= 0:
                return jsonify({"error": "Limit must be positive"}), 400
            if new_limit != card.limit:
                card.limit = new_limit
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
        
        # If billing cycle changed, recalculate unbilled spends
        if billing_cycle_changed:
            current_cycle_start = calculate_current_cycle_start(card.billing_cycle_start)
            
            # Calculate new unbilled_spends
            card.unbilled_spends = db.session.query(
                func.sum(func.abs(CreditCardTransaction.amount))
            ).filter(
                CreditCardTransaction.credit_card_id == card.id,
                CreditCardTransaction.amount < 0,
                CreditCardTransaction.date >= current_cycle_start
            ).scalar() or 0
            
            # Subtract any payments against these expenses
            payments_applied = db.session.query(
                func.sum(CreditCardTransaction.amount)
            ).filter(
                CreditCardTransaction.credit_card_id == card.id,
                CreditCardTransaction.amount > 0,
                CreditCardTransaction.date >= current_cycle_start
            ).scalar() or 0
            
            card.unbilled_spends = max(0, card.unbilled_spends - payments_applied)
        
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
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


def calculate_current_cycle_start(billing_cycle_start):
    """Calculate the start date of the current billing cycle"""
    today = datetime.now(timezone.utc)
    
    if today.day >= billing_cycle_start:
        # Current month's cycle
        try:
            return today.replace(day=billing_cycle_start)
        except ValueError:
            # Handle invalid day for current month (e.g., 31 in April)
            next_month = today.replace(day=1) + timedelta(days=32)
            last_day = (next_month.replace(day=1) - timedelta(days=1)).day
            adjusted_day = min(billing_cycle_start, last_day)
            return today.replace(day=adjusted_day)
    else:
        # Previous month's cycle
        if today.month == 1:
            prev_month = 12
            prev_year = today.year - 1
        else:
            prev_month = today.month - 1
            prev_year = today.year
            
        try:
            return datetime(prev_year, prev_month, billing_cycle_start)
        except ValueError:
            # Last day of previous month
            last_day = (datetime(prev_year, prev_month, 1) + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            return last_day
    
@routes.route('/credit_cards/<int:card_id>', methods=['DELETE'])
def delete_credit_card(card_id):
    # Use with_for_update to lock the card
    card = CreditCard.query.with_for_update().get(card_id)
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

@routes.route('/credit_cards/<int:card_id>/transactions', methods=['GET'])
def get_credit_card_transactions(card_id):
    card = CreditCard.query.get(card_id)
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
        "is_billed": t.is_billed  # Add this line
    } for t in transactions])

@routes.route('/credit_cards/<int:card_id>/transactions', methods=['POST'])
def add_credit_card_transaction(card_id):
    # Lock the card row to prevent concurrent modifications
    card = CreditCard.query.with_for_update().get(card_id)
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

        transaction_date = IST.localize(datetime(
            year=date_part.year,
            month=date_part.month,
            day=date_part.day,
            hour=now_ist.hour,
            minute=now_ist.minute,
            second=now_ist.second,
            microsecond=now_ist.microsecond
        ))
        if transaction_date > datetime.now(timezone.utc):
            return jsonify({"error": "Transaction date cannot be in the future"}), 400

        amount = float(data['amount'])
        if amount == 0:
            return jsonify({"error": "Amount cannot be zero"}), 400

        # ✅ Enforce chronological transaction order
        latest_txn = CreditCardTransaction.query.filter_by(
            credit_card_id=card.id
        ).order_by(CreditCardTransaction.date.desc()).first()

        if latest_txn:
            latest_txn_date = latest_txn.date
            if latest_txn_date.tzinfo is None:
                latest_txn_date = latest_txn_date.replace(tzinfo=timezone.utc)

            if transaction_date < latest_txn_date:
                return jsonify({
                    "error": "Transaction date must be on or after the last transaction's date."
                }), 400

        # ✅ Reject early payments if no expenses exist yet
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
            user_id=card.user_id,
            amount=amount,
            date=transaction_date,
            description=data.get('description'),
            category=data.get('category'),
            transaction_type='expense' if amount < 0 else 'payment',
            is_payment=data.get('is_payment', amount > 0),
            is_billed=(already_billed if amount < 0 else True)  # Payments are always marked billed
        )

        # Update card balances
        if amount < 0:  # Expense
            card.used += abs(amount)

            current_cycle_start, current_cycle_end = get_billing_cycle_range(today, card.billing_cycle_start)

            if txn_date < current_cycle_start:
                card.billed_unpaid += abs(amount)
            else:
                card.unbilled_spends += abs(amount)

        else:  # Payment
            total_owed = card.billed_unpaid + card.unbilled_spends
            if amount > total_owed:
                return jsonify({"error": "Payment amount exceeds total owed amount"}), 400

            payment_remaining = amount

            if card.billed_unpaid > 0:
                paid = min(payment_remaining, card.billed_unpaid)
                card.billed_unpaid -= paid
                payment_remaining -= paid

            if payment_remaining > 0 and card.unbilled_spends > 0:
                paid = min(payment_remaining, card.unbilled_spends)
                card.unbilled_spends -= paid
                payment_remaining -= paid

            total_paid = amount - payment_remaining
            card.used -= total_paid

            if total_paid > 0:
                card.last_payment_date = transaction_date
                card.last_payment_amount = amount

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
@routes.route('/credit_cards/<int:card_id>/process_billing', methods=['POST'])
def process_billing(card_id):
    card = CreditCard.query.with_for_update().get(card_id)
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
        card.billed_unpaid = sum(abs(e.amount) for e in billed_expenses)
        card.unbilled_spends = sum(abs(e.amount) for e in unbilled_expenses)
        card.used = card.billed_unpaid + card.unbilled_spends

        # Reapply payments
        payments_applied = 0
        payment_remaining = sum(p.amount for p in payments)

        for p in payments:
            apply_amt = p.amount

            if card.billed_unpaid > 0:
                paid = min(card.billed_unpaid, apply_amt)
                card.billed_unpaid -= paid
                card.used -= paid
                apply_amt -= paid
                payments_applied += paid

            if apply_amt > 0 and card.unbilled_spends > 0:
                paid = min(card.unbilled_spends, apply_amt)
                card.unbilled_spends -= paid
                card.used -= paid
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


def is_in_current_billing_cycle(transaction_date, cycle_start_day):
    """Check if transaction falls in current billing cycle based on CURRENT DATE"""
    today = datetime.now(timezone.utc)
    
    # Calculate current cycle start date
    if today.day >= cycle_start_day:
        # Current cycle started earlier this month
        try:
            cycle_start = today.replace(day=cycle_start_day)
        except ValueError:
            # Handle invalid day for current month
            next_month = today.replace(day=1) + timedelta(days=32)
            last_day = (next_month.replace(day=1) - timedelta(days=1)).day
            cycle_start_day = min(cycle_start_day, last_day)
            cycle_start = today.replace(day=cycle_start_day)
    else:
        # Current cycle started previous month
        prev_month = today.month - 1 if today.month > 1 else 12
        prev_year = today.year if today.month > 1 else today.year - 1
        
        try:
            cycle_start = datetime(prev_year, prev_month, cycle_start_day)
        except ValueError:
            # Last day of previous month
            cycle_start = datetime(prev_year, prev_month, 1) + timedelta(days=32)
            cycle_start = cycle_start.replace(day=1) - timedelta(days=1)
    
    return transaction_date >= cycle_start

def process_billing_date_transition(card):
    """Call this when a card's billing date arrives"""
    # Move unbilled spends to billed_unpaid
    card.billed_unpaid += card.unbilled_spends
    card.unbilled_spends = 0
    db.session.commit()

def get_billing_cycle_range(reference_date, billing_day):
    """
    Given a reference date and billing cycle start day, 
    return the current cycle's start and end date.
    """
    if reference_date.day >= billing_day:
        cycle_start = reference_date.replace(day=billing_day)
    else:
        # Move to previous month
        prev_month = reference_date.replace(day=1) - timedelta(days=1)
        cycle_start = prev_month.replace(day=billing_day)

    # Calculate end as one day before next cycle start
    try:
        next_cycle_start = cycle_start + relativedelta(months=1)
        cycle_end = next_cycle_start - timedelta(days=1)
    except ValueError:
        # Handle overflow (e.g., February 30)
        last_day = (cycle_start + relativedelta(months=1)).replace(day=1) - timedelta(days=1)
        cycle_end = last_day

    return cycle_start, cycle_end

# ========== BANK ROUTES ==========
@routes.route('/banks', methods=['POST'])
def create_bank():
    data = request.json
    try:
        if not data.get('user_id'):
            return jsonify({"error": "User ID is required"}), 400
            
        if not User.query.get(data['user_id']):
            return jsonify({"error": "User not found"}), 404
            
        bank = Bank(
            name=data['name'],
            user_id=data['user_id'],
            balance=data.get('balance', 0)
        )
        db.session.add(bank)
        db.session.commit()
        return jsonify({
            "id": bank.id,
            "name": bank.name,
            "user_id": bank.user_id,
            "balance": bank.balance
        }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error creating bank: {str(e)}")  # This will show in your Flask logs
        return jsonify({"error": str(e)}), 500

@routes.route('/banks', methods=['GET'])
def get_banks():
    banks = Bank.query.all()
    return jsonify([{
        "id": bank.id,
        "name": bank.name,
        "user_id": bank.user_id,
        "balance": bank.balance
    } for bank in banks])

@routes.route('/banks/<int:bank_id>', methods=['PUT'])
def update_bank(bank_id):
    bank = Bank.query.get(bank_id)
    if not bank:
        return jsonify({"error": "Bank not found"}), 404
    
    data = request.json
    bank.name = data.get('name', bank.name)
    bank.user_id = data.get('user_id', bank.user_id)
    
    db.session.commit()
    return jsonify({
        "id": bank.id,
        "name": bank.name,
        "user_id": bank.user_id,
        "balance": bank.balance
    })

@routes.route('/banks/<int:bank_id>', methods=['DELETE'])
def delete_bank(bank_id):
    bank = Bank.query.get(bank_id)
    if not bank:
        return jsonify({"error": "Bank not found"}), 404
    
    if bank.balance != 0:
        return jsonify({"error": "Cannot delete bank with non-zero balance"}), 400
    
    db.session.delete(bank)
    db.session.commit()
    return jsonify({"message": "Bank deleted successfully"}), 200

@routes.route('/banks/<int:bank_id>/transactions', methods=['POST'])
def add_bank_transaction(bank_id):
    bank = Bank.query.get(bank_id)
    if not bank:
        return jsonify({"error": "Bank not found"}), 404
    
    data = request.json
    try:
        amount = float(data['amount'])
        transaction_type = data.get('type', 'income')  # Default to income if not specified
        description = data.get('description', '')
        category = data.get('category', '')
        
        # Validate transaction type
        if transaction_type not in ('income', 'expense'):
            return jsonify({"error": "Invalid transaction type"}), 400
            
        # For expense transactions, check balance if amount is positive
        if transaction_type == 'expense' and bank.balance < amount:
            return jsonify({"error": "Insufficient balance"}), 400
            
        # Calculate new balance based on transaction type
        if transaction_type == 'income':
            new_balance = bank.balance + amount
        else:
            new_balance = bank.balance - amount
        
        transaction = BankTransaction(
            bank_id=bank_id,
            user_id=bank.user_id,
            amount=amount,
            description=description,
            category=category,
            transaction_type=transaction_type,
            bank_balance_after=new_balance
        )
        
        bank.balance = new_balance
        db.session.add(transaction)
        db.session.commit()
        
        return jsonify({
            "message": "Transaction added",
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
    except ValueError:
        return jsonify({"error": "Invalid amount"}), 400

@routes.route('/banks/<int:bank_id>/transactions', methods=['GET'])
def get_bank_transactions(bank_id):
    bank = Bank.query.get(bank_id)
    if not bank:
        return jsonify({"error": "Bank not found"}), 404

    transactions = BankTransaction.query.filter_by(bank_id=bank_id).order_by(BankTransaction.date.desc()).all()
    return jsonify([{
        "id": tx.id,
        "amount": tx.amount,
        "description": tx.description or '',
        "category": tx.category or '',
        "transaction_type": tx.transaction_type,
        "date": tx.date.strftime("%Y-%m-%d %H:%M:%S"),
        "bank_balance_after": tx.bank_balance_after
    } for tx in transactions])

# ========== ASSET ROUTES ==========
@routes.route('/assets', methods=['POST'])
def create_asset():
    data = request.json
    if not User.query.get(data['user_id']):
        return jsonify({"error": "User not found"}), 404
        
    asset = Asset(
        name=data['name'],
        user_id=data['user_id'],
        platform=data.get('platform'),  # New field
        category=data.get('category'),  # New field
        balance=data.get('balance', 0)
    )
    db.session.add(asset)
    db.session.commit()
    return jsonify({"message": "Asset created!"}), 201

@routes.route('/assets', methods=['GET'])
def get_assets():
    assets = Asset.query.all()
    return jsonify([
        {
            "id": asset.id,
            "name": asset.name,
            "user_id": asset.user_id,
            "platform": asset.platform,  # New field
            "category": asset.category,  # New field
            "balance": asset.balance
        } 
        for asset in assets
    ])

@routes.route('/assets/<int:asset_id>', methods=['PUT'])
def update_asset(asset_id):
    asset = Asset.query.get(asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    
    data = request.json
    
    # Validate user_id if provided
    if 'user_id' in data:
        if not User.query.get(data['user_id']):
            return jsonify({"error": "New user not found"}), 404
        asset.user_id = data['user_id']
    
    # Update allowed fields
    if 'name' in data:
        asset.name = data['name']
    if 'platform' in data:
        asset.platform = data['platform']
    if 'category' in data:
        asset.category = data['category']
    
    # Explicitly prevent balance updates
    if 'balance' in data:
        return jsonify({
            "error": "Balance cannot be updated directly. Use transactions instead."
        }), 400
    
    db.session.commit()
    return jsonify({
        "message": "Asset updated successfully",
        "asset": {
            "id": asset.id,
            "name": asset.name,
            "user_id": asset.user_id,
            "platform": asset.platform,
            "category": asset.category,
            "balance": asset.balance  # Showing but not allowing direct updates
        }
    }), 200

@routes.route('/assets/<int:asset_id>/transactions', methods=['POST'])
def add_asset_transaction(asset_id):
    asset = Asset.query.get(asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    
    data = request.json
    amount = float(data['amount'])
    transaction_type = data.get('type', 'deposit')
    
    if transaction_type == 'withdraw' and asset.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400
    
    new_balance = asset.balance + amount if transaction_type == 'deposit' else asset.balance - amount
    
    transaction = AssetTransaction(
        asset_id=asset_id,
        user_id=asset.user_id,
        amount=amount,
        description=data.get('description'),
        category=data.get('category'),
        transaction_type=transaction_type,
        asset_balance_after=new_balance
    )
    
    asset.balance = new_balance
    db.session.add(transaction)
    db.session.commit()
    return jsonify({"message": "Transaction added", "balance": new_balance}), 201

@routes.route('/assets/<int:asset_id>/transactions', methods=['GET'])
def get_asset_transactions(asset_id):
    asset = Asset.query.get(asset_id)
    if not asset:
        return jsonify({"error": "Asset not found"}), 404

    transactions = AssetTransaction.query.filter_by(asset_id=asset_id).all()
    return jsonify([
        {
            "id": tx.id,
            "amount": tx.amount,
            "description": tx.description or '',
            "category": tx.category or '',
            "transaction_type": tx.transaction_type,
            "date": tx.date.strftime("%Y-%m-%d %H:%M:%S"),
            "asset_balance_after": tx.asset_balance_after
        }
        for tx in transactions
    ])

@routes.route('/assets/<int:asset_id>', methods=['DELETE'])
def delete_asset(asset_id):
    asset = Asset.query.get(asset_id)
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    print(f"Attempting to delete asset {asset_id} with balance: {asset.balance}")  # Debugging line

    if asset.balance != 0:
        return jsonify({'error': 'Asset cannot be deleted because its balance is not zero.'}), 400

    db.session.delete(asset)
    db.session.commit()
    return jsonify({'message': 'Asset deleted successfully'}), 200


# ========== SAVING ROUTES ==========
@routes.route('/savings', methods=['POST'])
def create_saving():
    data = request.json
    if not User.query.get(data['user_id']):
        return jsonify({"error": "User not found"}), 404
    
    # Validate bank if provided
    if 'bank_id' in data and data['bank_id']:
        if not Bank.query.get(data['bank_id']):
            return jsonify({"error": "Bank not found"}), 404
    
    saving = Saving(
        name=data['name'],
        user_id=data['user_id'],
        bank_id=data.get('bank_id'),
        balance=data.get('balance', 0)
    )
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

@routes.route('/savings', methods=['GET'])
def get_savings():
    savings = Saving.query.all()
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

@routes.route('/savings/<int:saving_id>', methods=['PUT'])
def update_saving(saving_id):
    saving = Saving.query.get(saving_id)
    if not saving:
        return jsonify({"error": "Saving account not found"}), 404
    
    data = request.json
    
    # Validate user_id if provided
    if 'user_id' in data:
        if not User.query.get(data['user_id']):
            return jsonify({"error": "New user not found"}), 404
        saving.user_id = data['user_id']
    
    # Handle bank_id change carefully
    if 'bank_id' in data and data['bank_id'] != saving.bank_id:
        new_bank_id = data['bank_id']
        
        # Validate new bank if provided
        if new_bank_id and not Bank.query.get(new_bank_id):
            return jsonify({"error": "New bank not found"}), 404
        
        # If there's a balance, we need to handle the bank transfer
        if saving.balance > 0:
            # If currently linked to a bank, return funds to it
            if saving.bank_id:
                old_bank = Bank.query.get(saving.bank_id)
                old_bank.balance += saving.balance
            
            # If linking to a new bank, withdraw funds from it
            if new_bank_id:
                new_bank = Bank.query.get(new_bank_id)
                if new_bank.balance < saving.balance:
                    return jsonify({
                        "error": "New bank has insufficient funds for this transfer"
                    }), 400
                new_bank.balance -= saving.balance
        
        # Update the bank link
        saving.bank_id = new_bank_id
    
    # Update allowed fields
    if 'name' in data:
        saving.name = data['name']
    
    # Explicitly prevent balance updates
    if 'balance' in data:
        return jsonify({
            "error": "Balance cannot be updated directly. Use transactions instead."
        }), 400
    
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

@routes.route('/savings/<int:saving_id>/transactions', methods=['POST'])
def add_saving_transaction(saving_id):
    saving = Saving.query.get(saving_id)
    if not saving:
        return jsonify({"error": "Saving account not found"}), 404
    
    data = request.json
    amount = float(data['amount'])
    transaction_type = data.get('type', 'deposit')
    
    if transaction_type == 'withdrawal' and saving.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400
    
    # Update saving balance
    new_saving_balance = saving.balance + amount if transaction_type == 'deposit' else saving.balance - amount
    
    # If linked to a bank, update bank balance as well
    bank_balance_update = None
    if saving.bank_id:
        bank = Bank.query.get(saving.bank_id)
        if not bank:
            return jsonify({"error": "Linked bank account not found"}), 404
        
        # Reverse operation for bank (deposit to saving = withdrawal from bank)
        bank_amount = -amount if transaction_type == 'deposit' else amount
        new_bank_balance = bank.balance + bank_amount
        
        if transaction_type == 'deposit' and bank.balance < amount:
            return jsonify({"error": "Insufficient bank balance"}), 400
        
        bank.balance = new_bank_balance
        bank_balance_update = new_bank_balance
    
    # Create saving transaction
    transaction = SavingTransaction(
        saving_id=saving_id,
        user_id=saving.user_id,
        amount=amount,
        description=data.get('description'),
        category=data.get('category'),
        transaction_type=transaction_type,
        saving_balance_after=new_saving_balance
    )
    
    saving.balance = new_saving_balance
    db.session.add(transaction)
    db.session.commit()
    
    response = {
        "message": "Transaction added",
        "saving_balance": new_saving_balance
    }
    
    if bank_balance_update is not None:
        response["bank_balance"] = bank_balance_update
    
    return jsonify(response), 201

@routes.route('/savings/<int:saving_id>/transactions', methods=['GET'])
def get_saving_transactions(saving_id):
    saving = Saving.query.get(saving_id)
    if not saving:
        return jsonify({"error": "Saving account not found"}), 404

    transactions = SavingTransaction.query.filter_by(saving_id=saving_id).all()
    return jsonify([
        {
            "id": tx.id,
            "amount": tx.amount,
            "description": tx.description or '',
            "category": tx.category or '',
            "transaction_type": tx.transaction_type,
            "date": tx.date.strftime("%Y-%m-%d %H:%M:%S"),
            "saving_balance_after": tx.saving_balance_after
        }
        for tx in transactions
    ])

@routes.route('/savings/<int:saving_id>', methods=['DELETE'])
def delete_saving(saving_id):
    saving = Saving.query.get(saving_id)
    if not saving:
        return jsonify({'error': 'Saving account not found'}), 404

    if saving.balance != 0:
        return jsonify({'error': 'Saving account cannot be deleted because its balance is not zero.'}), 400

    db.session.delete(saving)
    db.session.commit()
    return jsonify({'message': 'Saving account deleted successfully'}), 200

# ========== TRANSFER ROUTES ==========
@routes.route('/transfers', methods=['POST'])
def create_transfer():
    data = request.json
    user_id = data['user_id']
    
    # Validate accounts
    from_account = get_account(data['from_account_type'], data['from_account_id'])
    to_account = get_account(data['to_account_type'], data['to_account_id'])
    
    if not from_account or not to_account:
        return jsonify({"error": "Invalid account(s)"}), 400
    
    amount = float(data['amount'])
    fee = float(data.get('fee', 0))
    
    # Check sufficient balance
    if from_account.balance < amount + fee:
        return jsonify({"error": "Insufficient balance"}), 400
    
    # Perform transfer
    from_account.balance -= (amount + fee)
    to_account.balance += amount
    
    transfer = TransferTransaction(
        user_id=user_id,
        from_account_type=data['from_account_type'],
        from_account_id=data['from_account_id'],
        to_account_type=data['to_account_type'],
        to_account_id=data['to_account_id'],
        amount=amount,
        fee=fee,
        description=data.get('description')
    )
    
    db.session.add(transfer)
    db.session.commit()
    return jsonify({"message": "Transfer completed"}), 201

def get_account(account_type, account_id):
    if account_type == 'bank':
        return Bank.query.get(account_id)
    elif account_type == 'credit_card':
        return CreditCard.query.get(account_id)
    elif account_type == 'asset':
        return Asset.query.get(account_id)
    elif account_type == 'saving':
        return Saving.query.get(account_id)
    return None

# ========== UTILITY ROUTES ==========
@routes.route('/users_dropdown', methods=['GET'])
def get_users_dropdown():
    try:
        users = User.query.all()
        return jsonify([{
            "id": user.id,
            "name": user.name
        } for user in users])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@routes.route('/banks_dropdown', methods=['GET'])
def get_banks_dropdown():
    user_id = request.args.get('user_id')
    banks = Bank.query.filter_by(user_id=user_id).all()
    return jsonify([{"id": bank.id, "name": bank.name} for bank in banks])

@routes.route('/bank_balance', methods=['GET'])
def get_bank_balance():
    bank_id = request.args.get('bank_id')
    if not bank_id:
        return jsonify({"error": "bank_id parameter is required"}), 400
    
    bank = Bank.query.get(bank_id)
    if not bank:
        return jsonify({"error": "Bank not found"}), 404
    
    return jsonify({
        "id": bank.id,           # Bank ID
        "name": bank.name,        # Bank name
        "balance": bank.balance   # Current balance
    })