from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone
import pytz

from ..models import Asset, AssetTransaction
from .. import db
from ..utils.financial_util import money 

assets_routes = Blueprint("assets_routes", __name__)

IST = pytz.timezone('Asia/Kolkata')

VALID_ASSET_CATEGORIES = {
    "Provident Fund",
    "Mutual Funds",
    "Stocks",
    "ETF",
    "FD",
    "Other"
}

@assets_routes.route('/assets', methods=['POST'])
@jwt_required()
def create_asset():
    user_id = int(get_jwt_identity())
    data = request.json

    category = data.get('category')

    if not category:
        return jsonify({
            "error": "Category is required"
        }), 400

    if category not in VALID_ASSET_CATEGORIES:
        return jsonify({
            "error": (
                f"Invalid category. "
                f"Allowed values: "
                f"{', '.join(sorted(VALID_ASSET_CATEGORIES))}"
            )
        }), 400
        
    asset = Asset(
        name=data['name'],
        user_id=user_id,
        platform=data.get('platform'),
        category=data.get('category'),
        balance=money(data.get('balance', 0))
    )
    try:
        db.session.add(asset)
        db.session.commit()
        return jsonify({"message": "Asset created!"}), 201
    except IntegrityError as e:
        db.session.rollback()
        if 'asset_name_key' in str(e.orig):
            return jsonify({"error": "Asset name already exists"}), 400
        return jsonify({"error": "Database integrity error"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500

@assets_routes.route('/assets', methods=['GET'])
@jwt_required()
def get_assets():
    user_id = int(get_jwt_identity())
    assets = Asset.query.filter_by(user_id=user_id).all()
    return jsonify([
        {
            "id": asset.id,
            "name": asset.name,
            "user_id": asset.user_id,
            "platform": asset.platform,
            "category": asset.category,
            "balance": asset.balance
        } 
        for asset in assets
    ])

@assets_routes.route('/assets/<int:asset_id>', methods=['PUT'])
@jwt_required()
def update_asset(asset_id):
    user_id = int(get_jwt_identity())
    asset = Asset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    
    data = request.json
    
    # Update allowed fields
    if 'name' in data:
        asset.name = data['name']
    if 'platform' in data:
        asset.platform = data['platform']
    if 'category' in data:

        category = data['category']

        if not category:
            return jsonify({
                "error": "Category is required"
            }), 400

        if category not in VALID_ASSET_CATEGORIES:
            return jsonify({
                "error": (
                    f"Invalid category. "
                    f"Allowed values: "
                    f"{', '.join(sorted(VALID_ASSET_CATEGORIES))}"
                )
            }), 400

        asset.category = category
    
    # Explicitly prevent balance updates
    if 'balance' in data:
        return jsonify({
            "error": "Balance cannot be updated directly. Use transactions instead."
        }), 400
    
    try:
        db.session.commit()
        return jsonify({
            "message": "Asset updated successfully",
            "asset": {
                "id": asset.id,
                "name": asset.name,
                "user_id": asset.user_id,
                "platform": asset.platform,
                "category": asset.category,
                "balance": asset.balance
            }
        }), 200
    except IntegrityError as e:
        db.session.rollback()
        if 'asset_name_key' in str(e.orig):
            return jsonify({"error": "Asset name already exists"}), 400
        return jsonify({"error": "Database integrity error"}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@assets_routes.route('/assets/<int:asset_id>/transactions', methods=['POST'])
@jwt_required()
def add_asset_transaction(asset_id):
    user_id = int(get_jwt_identity())
    asset = Asset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not asset:
        return jsonify({"error": "Asset not found"}), 404
    
    data = request.json
    amount = float(data['amount'])
    transaction_type = data.get('type', 'deposit')
    
    if transaction_type == 'withdraw' and asset.balance < amount:
        return jsonify({"error": "Insufficient balance"}), 400
    
    new_balance = money(asset.balance + amount if transaction_type == 'deposit' else asset.balance - amount)
    
    transaction = AssetTransaction(
        asset_id=asset_id,
        user_id=user_id,
        amount=amount,
        description=data.get('description'),
        category=data.get('category'),
        transaction_type=transaction_type,
        asset_balance_after=new_balance,
        date=datetime.now(timezone.utc)
    )
    
    asset.balance = money(new_balance)
    db.session.add(transaction)
    db.session.commit()
    return jsonify({"message": "Transaction added", "balance": new_balance}), 201

@assets_routes.route('/assets/<int:asset_id>/transactions', methods=['GET'])
@jwt_required()
def get_asset_transactions(asset_id):
    user_id = int(get_jwt_identity())
    asset = Asset.query.filter_by(id=asset_id, user_id=user_id).first()
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
            "date": tx.date.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
            "asset_balance_after": tx.asset_balance_after
        }
        for tx in transactions
    ])

@assets_routes.route('/assets/<int:asset_id>', methods=['DELETE'])
@jwt_required()
def delete_asset(asset_id):
    user_id = int(get_jwt_identity())
    asset = Asset.query.filter_by(id=asset_id, user_id=user_id).first()
    if not asset:
        return jsonify({'error': 'Asset not found'}), 404

    if asset.balance != 0:
        return jsonify({'error': 'Asset cannot be deleted because its balance is not zero.'}), 400

    db.session.delete(asset)
    db.session.commit()
    return jsonify({'message': 'Asset deleted successfully'}), 200
