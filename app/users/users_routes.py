from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from ..models import User, Transaction, TransferTransaction
from .. import db
from ..utils.date_util import calculate_age,parse_date

users_routes = Blueprint("users_routes", __name__)


@users_routes.route('/users', methods=['GET'])
@jwt_required()
def get_users():
    
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify([{
        'id': user.id,
        'name': user.name,
        'age': user.age,
        'dob': user.dob.strftime("%Y-%m-%d"),
        'place': user.place
    }])

@users_routes.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    return jsonify({
        'id': user.id,
        'name': user.name,
        'dob': user.dob.strftime("%Y-%m-%d"),
        'place': user.place,
        'age': user.age
    }), 200

@users_routes.route('/users/<int:id>', methods=['PUT'])
@jwt_required()
def update_user(id):
    user_id = int(get_jwt_identity())
    if id != user_id:
        return jsonify({'error': 'Unauthorized'}), 403

    user = db.session.get(User, id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    data = request.json

    try:
        if 'age' in data:
            return jsonify({"error": "Age should not be provided manually. It will be calculated from date of birth."}), 400

        dob = parse_date(data['dob'])
        user.name = data['name']
        user.dob = dob
        user.age = calculate_age(dob)
        user.place = data['place']

        if 'password' in data and data['password'].strip():
            user.set_password(data['password'])

        db.session.commit()

        return jsonify({
            'id': user.id,
            'name': user.name,
            'age': user.age,
            'dob': user.dob.strftime("%Y-%m-%d"),
            'place': user.place
        }), 200

    except ValueError:
        db.session.rollback()
        return jsonify({"error": "Invalid date format. Use 'YYYY-MM-DD'."}), 400

    except IntegrityError as e:
        db.session.rollback()
        if 'user_name_key' in str(e.orig):
            return jsonify({"error": "Username already exists"}), 400
        return jsonify({"error": "Database integrity error"}), 400

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@users_routes.route('/users/<int:id>', methods=['DELETE'])
@jwt_required()
def delete_user(id):
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

    # Check balances before deletion.
    has_bank_balances = any(
        bank.balance != 0
        for bank in user.banks
    )

    has_asset_balances = any(
        asset.balance != 0
        for asset in user.assets
    )

    has_saving_balances = any(
        saving.balance != 0
        for saving in user.savings
    )

    has_credit_balances = any(
        card.used != 0
        for card in user.credit_cards
    )

    if (
        has_bank_balances
        or has_asset_balances
        or has_saving_balances
        or has_credit_balances
    ):
        return jsonify({
            "error": (
                "Cannot delete user with existing balances"
            ),
            "details": {
                "has_bank_balances": has_bank_balances,
                "has_asset_balances": has_asset_balances,
                "has_saving_balances": has_saving_balances,
                "has_credit_balances": has_credit_balances
            }
        }), 400

    try:
        transaction_count = (
            db.session.query(Transaction)
            .filter(
                Transaction.user_id == user.id
            )
            .delete(
                synchronize_session=False
            )
        )

        transfer_count = (
            db.session.query(TransferTransaction)
            .filter(
                TransferTransaction.user_id == user.id
            )
            .delete(
                synchronize_session=False
            )
        )

        db.session.delete(user)

        db.session.commit()

        return jsonify({
            "message": "User deleted successfully",
            "deleted_transaction_count": (
                transaction_count or 0
            ),
            "deleted_transfer_count": (
                transfer_count or 0
            )
        }), 200

    except Exception:
        db.session.rollback()

        return jsonify({
            "error": "Unable to delete user account"
        }), 500

@users_routes.route('/users/<int:id>/can_delete', methods=['GET'])
@jwt_required()
def can_delete_user(id):
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

    # Check all associated balances.
    has_bank_balances = any(
        bank.balance != 0
        for bank in user.banks
    )

    has_asset_balances = any(
        asset.balance != 0
        for asset in user.assets
    )

    has_saving_balances = any(
        saving.balance != 0
        for saving in user.savings
    )

    has_credit_balances = any(
        card.used != 0
        for card in user.credit_cards
    )

    can_delete = not (
        has_bank_balances
        or has_asset_balances
        or has_saving_balances
        or has_credit_balances
    )

    transaction_count = (
        db.session.query(Transaction)
        .filter(Transaction.user_id == user.id)
        .count()
    )

    transfer_count = (
        db.session.query(TransferTransaction)
        .filter(
            TransferTransaction.user_id == user.id
        )
        .count()
    )

    total_transaction_count = (
        transaction_count + transfer_count
    )

    if not can_delete:
        message = (
            "Cannot delete user account. "
            "Please clear all balances from: "
        )

        reasons = []

        if has_bank_balances:
            reasons.append("bank accounts")

        if has_asset_balances:
            reasons.append("assets")

        if has_saving_balances:
            reasons.append("savings")

        if has_credit_balances:
            reasons.append("credit cards")

        message += (
            ", ".join(reasons)
            + " and try again."
        )

    elif total_transaction_count > 0:
        message = (
            "User account can be deleted, but "
            f"{total_transaction_count} transaction records "
            "will be permanently deleted."
        )

    else:
        message = (
            "User account can be deleted "
            "as there are no balances."
        )

    return jsonify({
        "can_delete": can_delete,
        "message": message,
        "has_transaction_history": (
            total_transaction_count > 0
        ),
        "transaction_count": total_transaction_count,
        "details": {
            "has_bank_balances": has_bank_balances,
            "has_asset_balances": has_asset_balances,
            "has_saving_balances": has_saving_balances,
            "has_credit_balances": has_credit_balances
        }
    }), 200
