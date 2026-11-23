from flask import Blueprint, g, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from ..models import User, Transaction, TransferTransaction
from .. import db
from ..utils.errors import server_error
from ..utils.date_util import calculate_age,parse_date
from ..utils.dashboard_cache import invalidate_dashboard_cache
from ..utils.auth_tokens import create_user_token
from ..utils.rate_limit import (
    PASSWORD_CHANGE_MESSAGE,
    account_path_key,
    is_failed_password_check,
    limiter,
    password_change_failure_rate_limit,
)

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

# Changing the password needs the current one, so a stolen token alone
# cannot lock the owner out. Wrong current passwords are rate limited per
# account (only failed checks count), like failed logins.
@users_routes.route('/users/<int:id>', methods=['PUT'])
@limiter.limit(
    password_change_failure_rate_limit,
    key_func=account_path_key,
    deduct_when=is_failed_password_check,
    error_message=PASSWORD_CHANGE_MESSAGE,
)
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

        new_password = data.get('password')
        password_changed = isinstance(new_password, str) and bool(new_password.strip())

        if password_changed:
            current_password = data.get('current_password')

            if not isinstance(current_password, str) or not current_password:
                db.session.rollback()
                return jsonify({"error": "Current password is required to set a new password."}), 400

            if not user.check_password(current_password):
                db.session.rollback()
                g.password_check_failed = True
                # 403, not 401: the session itself is still valid, and the
                # frontend logs the user out on any 401.
                return jsonify({"error": "Current password is incorrect."}), 403

            user.set_password(new_password)
            # Ends every existing session (other devices included).
            user.token_version = user.token_version + 1

        db.session.commit()

        body = {
            'id': user.id,
            'name': user.name,
            'age': user.age,
            'dob': user.dob.strftime("%Y-%m-%d"),
            'place': user.place
        }

        if password_changed:
            # The token used for this request is now invalid; hand back a new
            # one so this device stays logged in.
            body['token'] = create_user_token(user)

        return jsonify(body), 200

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
        return server_error()

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
        invalidate_dashboard_cache(user_id)

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
