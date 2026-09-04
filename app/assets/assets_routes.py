import math
from datetime import datetime, timezone

import pytz

from flask import (
    Blueprint,
    jsonify,
    request,
)

from flask_jwt_extended import (
    get_jwt_identity,
    jwt_required,
)

from sqlalchemy.exc import IntegrityError

from .. import db
from ..models import (
    Asset,
    AssetTransaction,
)
from ..utils.financial_util import money


assets_routes = Blueprint(
    "assets_routes",
    __name__,
)

IST = pytz.timezone(
    "Asia/Kolkata"
)


VALID_ASSET_CATEGORIES = {
    "Provident Fund",
    "Mutual Funds",
    "Stocks",
    "ETF",
    "FD",
    "Other",
}


VALID_TRANSACTION_TYPES = {
    "deposit",
    "withdraw",
}


def _validate_asset_name(data):
    name = data.get("name")

    if not isinstance(name, str):
        return None, "Asset name is required"

    name = name.strip()

    if not name:
        return None, "Asset name is required"

    return name, None


def _parse_asset_balance(value):
    try:
        balance = float(value)
    except (
        TypeError,
        ValueError,
    ):
        return None, (
            "Asset balance must be a valid number"
        )

    if not math.isfinite(balance):
        return None, (
            "Asset balance must be a valid number"
        )

    if balance < 0:
        return None, (
            "Asset balance cannot be negative"
        )

    return money(balance), None


def _parse_transaction_amount(data):
    if "amount" not in data:
        return None, "Amount is required"

    raw_amount = data.get("amount")

    try:
        amount = float(raw_amount)
    except (
        TypeError,
        ValueError,
    ):
        return None, (
            "Amount must be a valid number"
        )

    if not math.isfinite(amount):
        return None, (
            "Amount must be a valid number"
        )

    if amount <= 0:
        return None, (
            "Amount must be greater than 0"
        )

    return amount, None


@assets_routes.route(
    "/assets",
    methods=["POST"],
)
@jwt_required()
def create_asset():
    user_id = int(
        get_jwt_identity()
    )

    data = request.get_json(
        silent=True
    ) or {}

    name, name_error = (
        _validate_asset_name(data)
    )

    if name_error:
        return jsonify({
            "error": name_error
        }), 400

    category = data.get(
        "category"
    )

    if not category:
        return jsonify({
            "error": "Category is required"
        }), 400

    if category not in VALID_ASSET_CATEGORIES:
        return jsonify({
            "error": (
                "Invalid category. "
                "Allowed values: "
                f"{', '.join(sorted(VALID_ASSET_CATEGORIES))}"
            )
        }), 400

    balance, balance_error = (
        _parse_asset_balance(
            data.get("balance", 0)
        )
    )

    if balance_error:
        return jsonify({
            "error": balance_error
        }), 400

    asset = Asset(
        name=name,
        user_id=user_id,
        platform=data.get("platform"),
        category=category,
        balance=balance,
    )

    try:
        db.session.add(asset)
        db.session.commit()

        return jsonify({
            "message": "Asset created!",
            "asset": {
                "id": asset.id,
                "name": asset.name,
                "user_id": asset.user_id,
                "platform": asset.platform,
                "category": asset.category,
                "balance": asset.balance,
            },
        }), 201

    except IntegrityError as exc:
        db.session.rollback()

        if "asset_name_key" in str(
            exc.orig
        ):
            return jsonify({
                "error": "Asset name already exists"
            }), 400

        return jsonify({
            "error": "Database integrity error"
        }), 400

    except Exception as exc:
        db.session.rollback()

        return jsonify({
            "error": (
                f"Server error: {str(exc)}"
            )
        }), 500


@assets_routes.route(
    "/assets",
    methods=["GET"],
)
@jwt_required()
def get_assets():
    user_id = int(
        get_jwt_identity()
    )

    assets = (
        Asset.query
        .filter_by(
            user_id=user_id
        )
        .all()
    )

    return jsonify([
        {
            "id": asset.id,
            "name": asset.name,
            "user_id": asset.user_id,
            "platform": asset.platform,
            "category": asset.category,
            "balance": asset.balance,
        }
        for asset in assets
    ])


@assets_routes.route(
    "/assets/<int:asset_id>",
    methods=["PUT"],
)
@jwt_required()
def update_asset(asset_id):
    user_id = int(
        get_jwt_identity()
    )

    asset = (
        Asset.query
        .filter_by(
            id=asset_id,
            user_id=user_id,
        )
        .first()
    )

    if not asset:
        return jsonify({
            "error": "Asset not found"
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    if "name" in data:
        name, name_error = (
            _validate_asset_name(data)
        )

        if name_error:
            return jsonify({
                "error": name_error
            }), 400

        asset.name = name

    if "platform" in data:
        asset.platform = data[
            "platform"
        ]

    if "category" in data:
        category = data.get(
            "category"
        )

        if not category:
            return jsonify({
                "error": "Category is required"
            }), 400

        if category not in (
            VALID_ASSET_CATEGORIES
        ):
            return jsonify({
                "error": (
                    "Invalid category. "
                    "Allowed values: "
                    f"{', '.join(sorted(VALID_ASSET_CATEGORIES))}"
                )
            }), 400

        asset.category = category

    if "balance" in data:
        return jsonify({
            "error": (
                "Balance cannot be updated "
                "directly. Use transactions "
                "instead."
            )
        }), 400

    try:
        db.session.commit()

        return jsonify({
            "message": (
                "Asset updated successfully"
            ),
            "asset": {
                "id": asset.id,
                "name": asset.name,
                "user_id": asset.user_id,
                "platform": asset.platform,
                "category": asset.category,
                "balance": asset.balance,
            },
        }), 200

    except IntegrityError as exc:
        db.session.rollback()

        if "asset_name_key" in str(
            exc.orig
        ):
            return jsonify({
                "error": "Asset name already exists"
            }), 400

        return jsonify({
            "error": "Database integrity error"
        }), 400

    except Exception as exc:
        db.session.rollback()

        return jsonify({
            "error": (
                f"Server error: {str(exc)}"
            )
        }), 500


@assets_routes.route(
    "/assets/<int:asset_id>/transactions",
    methods=["POST"],
)
@jwt_required()
def add_asset_transaction(asset_id):
    user_id = int(
        get_jwt_identity()
    )

    asset = (
        Asset.query
        .filter_by(
            id=asset_id,
            user_id=user_id,
        )
        .first()
    )

    if not asset:
        return jsonify({
            "error": "Asset not found"
        }), 404

    data = request.get_json(
        silent=True
    ) or {}

    amount, amount_error = (
        _parse_transaction_amount(
            data
        )
    )

    if amount_error:
        return jsonify({
            "error": amount_error
        }), 400

    transaction_type = data.get(
        "type",
        "deposit",
    )

    if transaction_type not in (
        VALID_TRANSACTION_TYPES
    ):
        return jsonify({
            "error": (
                "Invalid transaction type"
            )
        }), 400

    if (
        transaction_type == "withdraw"
        and asset.balance < amount
    ):
        return jsonify({
            "error": "Insufficient balance"
        }), 400

    if transaction_type == "deposit":
        new_balance = money(
            asset.balance + amount
        )
    else:
        new_balance = money(
            asset.balance - amount
        )

    transaction = AssetTransaction(
        asset_id=asset_id,
        user_id=user_id,
        amount=amount,
        description=data.get(
            "description"
        ),
        category=data.get(
            "category"
        ),
        transaction_type=transaction_type,
        asset_balance_after=new_balance,
        date=datetime.now(
            timezone.utc
        ),
    )

    asset.balance = new_balance

    try:
        db.session.add(transaction)
        db.session.commit()

        return jsonify({
            "message": "Transaction added",
            "balance": new_balance,
        }), 201

    except Exception as exc:
        db.session.rollback()

        return jsonify({
            "error": (
                f"Server error: {str(exc)}"
            )
        }), 500


@assets_routes.route(
    "/assets/<int:asset_id>/transactions",
    methods=["GET"],
)
@jwt_required()
def get_asset_transactions(asset_id):
    user_id = int(
        get_jwt_identity()
    )

    asset = (
        Asset.query
        .filter_by(
            id=asset_id,
            user_id=user_id,
        )
        .first()
    )

    if not asset:
        return jsonify({
            "error": "Asset not found"
        }), 404

    transactions = (
        AssetTransaction.query
        .filter_by(
            asset_id=asset_id
        )
        .order_by(
            AssetTransaction.date.asc(),
            AssetTransaction.id.asc(),
        )
        .all()
    )

    return jsonify([
        {
            "id": tx.id,
            "amount": tx.amount,
            "description": (
                tx.description
                or ""
            ),
            "category": (
                tx.category
                or ""
            ),
            "transaction_type": (
                tx.transaction_type
            ),
            "date": tx.date.astimezone(
                IST
            ).strftime(
                "%Y-%m-%d %H:%M:%S"
            ),
            "asset_balance_after": (
                tx.asset_balance_after
            ),
        }
        for tx in transactions
    ])


@assets_routes.route(
    "/assets/<int:asset_id>",
    methods=["DELETE"],
)
@jwt_required()
def delete_asset(asset_id):
    user_id = int(
        get_jwt_identity()
    )

    asset = (
        Asset.query
        .filter_by(
            id=asset_id,
            user_id=user_id,
        )
        .first()
    )

    if not asset:
        return jsonify({
            "error": "Asset not found"
        }), 404

    if asset.balance != 0:
        return jsonify({
            "error": (
                "Asset cannot be deleted "
                "because its balance is not zero."
            )
        }), 400

    try:
        
        AssetTransaction.query.filter_by(
            asset_id=asset.id,
            user_id=user_id,
        ).delete(
            synchronize_session=False
        )

        db.session.delete(asset)
        db.session.commit()

        return jsonify({
            "message": (
                "Asset deleted successfully"
            )
        }), 200

    except Exception as exc:
        db.session.rollback()

        return jsonify({
            "error": (
                f"Server error: {str(exc)}"
            )
        }), 500