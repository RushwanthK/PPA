from flask import Blueprint, jsonify, send_file
from datetime import datetime

from flask_jwt_extended import jwt_required, get_jwt_identity

from . import db
from .models import User

from .utils.transaction_export_util import (
    create_transaction_excel,
    create_transaction_pdf,
)

routes = Blueprint('routes', __name__)

# Home route
@routes.route('/')
def home():
    return "Welcome to the Personal Portfolio App!"

# ========== TRANSACTION EXPORT ROUTES ==========
@routes.route('/users/<int:id>/transactions/export/excel',methods=['GET'])
@jwt_required()
def export_user_transactions_excel(id):
    user = db.session.get(User, id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    user_id = int(get_jwt_identity())

    if id != user_id:
        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:
        output = create_transaction_excel(user.id)

        filename = (
            f"transaction_backup_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            )
        )

    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to generate transaction backup"
        }), 500

@routes.route('/users/<int:id>/transactions/export/pdf',methods=['GET'])
@jwt_required()
def export_user_transactions_pdf(id):
    user = db.session.get(User, id)

    if not user:
        return jsonify({
            "error": "User not found"
        }), 404

    user_id = int(get_jwt_identity())

    if id != user_id:
        return jsonify({
            "error": "Unauthorized"
        }), 403

    try:
        output = create_transaction_pdf(user.id)

        filename = (
            f"transaction_backup_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )

        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype="application/pdf"
        )

    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to generate transaction backup"
        }), 500


"""
Redundant comment block at the end of the file. It can be removed as it doesn't serve any purpose.

@routes.route('/users', methods=['POST'])
@jwt_required()
def create_user():
    user_id = int(get_jwt_identity())
    data = request.json
    try:
        if 'age' in data:
            return jsonify({"error": "Age should not be provided manually. It will be calculated from date of birth."}), 400
            
        dob = parse_date(data['dob'])
        new_user = User(
            id=user_id,  # Use JWT identity as user ID
            name=data['name'],
            age=calculate_age(dob),
            dob=dob,
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
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400

        
@routes.route('/users/<int:user_id>/credit_cards', methods=['GET'])
@jwt_required()
def get_user_credit_cards(user_id):
    current_user_id = int(get_jwt_identity())
    if current_user_id != user_id:
        return jsonify({"error": "Unauthorized access"}), 403
        
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
    from_account.balance = money(
        from_account.balance - (amount + fee)
    )

    to_account.balance = money(
        to_account.balance + amount
    )
    
    transfer = TransferTransaction(
        user_id=user_id,
        from_account_type=data['from_account_type'],
        from_account_id=data['from_account_id'],
        to_account_type=data['to_account_type'],
        to_account_id=data['to_account_id'],
        amount=amount,
        fee=fee,
        description=data.get('description'),
        date=datetime.now(timezone.utc)
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

@routes.route('/users/dropdown', methods=['GET'])
@jwt_required()
def get_users_dropdown():
    user_id = int(get_jwt_identity())
    user = User.query.get(user_id)
    if not user:
        return jsonify([])

    return jsonify([{
        'id': user.id,
        'name': user.name
    }])


    
"""