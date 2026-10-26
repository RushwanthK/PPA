import base64
import hashlib
import json

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy.exc import IntegrityError
from sqlalchemy import or_, tuple_
from datetime import datetime, timedelta, timezone
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

def _serialize_bank_transaction(transaction):
    """Serialize a bank transaction using the application's naive-UTC convention."""
    transaction_date = transaction.date
    if transaction_date.tzinfo is None:
        transaction_date = pytz.UTC.localize(transaction_date)

    return {
        "id": transaction.id,
        "amount": transaction.amount,
        "description": transaction.description or '',
        "category": transaction.category or '',
        "transaction_type": transaction.transaction_type,
        "date": transaction_date.astimezone(IST).strftime("%Y-%m-%d %H:%M:%S"),
        "bank_balance_after": transaction.bank_balance_after,
    }


def _bank_transaction_cursor_signature(
    *,
    bank_id,
    user_id,
    page_size,
    search,
    transaction_type,
    start_date_value,
    end_date_value,
    amount_range,
):
    """Bind a cursor to the bank, user, page size, and active filters.

    The signature prevents accidentally reusing a cursor after the filter set
    changes. Authorization is still enforced independently by the route.
    """
    scope = {
        "bank_id": bank_id,
        "user_id": user_id,
        "page_size": page_size,
        "search": search,
        "transaction_type": transaction_type,
        "start_date": start_date_value.isoformat() if start_date_value else None,
        "end_date": end_date_value.isoformat() if end_date_value else None,
        "amount_range": amount_range,
    }
    canonical_scope = json.dumps(scope, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_scope.encode("utf-8")).hexdigest()


def _encode_bank_transaction_cursor(transaction, scope_signature):
    """Encode the exact stored timestamp and primary key for the next page."""
    cursor_date = transaction.date
    if cursor_date.tzinfo is not None:
        cursor_date = cursor_date.astimezone(timezone.utc).replace(tzinfo=None)

    payload = {
        "v": 1,
        "date": cursor_date.isoformat(timespec="microseconds"),
        "id": int(transaction.id),
        "scope": scope_signature,
    }
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw_payload).decode("ascii").rstrip("=")


def _decode_bank_transaction_cursor(cursor_token):
    """Decode and validate a cursor generated by this endpoint."""
    import binascii

    if not cursor_token or len(cursor_token) > 2048:
        raise ValueError("Invalid transaction cursor")

    try:
        padded_token = cursor_token + ("=" * (-len(cursor_token) % 4))
        raw_payload = base64.urlsafe_b64decode(padded_token.encode("ascii"))
        payload = json.loads(raw_payload.decode("utf-8"))
        if not isinstance(payload, dict) or payload.get("v") != 1:
            raise ValueError("Unsupported transaction cursor")

        cursor_date = datetime.fromisoformat(payload["date"])
        cursor_id = payload["id"]
        scope_signature = payload["scope"]

        # DB timestamps follow the application's naive-UTC convention. Cursor
        # timestamps must preserve that same convention for tuple comparison.
        if cursor_date.tzinfo is not None:
            raise ValueError("Cursor timestamp must use naive UTC")
        if type(cursor_id) is not int or cursor_id <= 0:
            raise ValueError("Invalid transaction cursor ID")
        if not isinstance(scope_signature, str) or len(scope_signature) != 64:
            raise ValueError("Invalid transaction cursor scope")

        return cursor_date, cursor_id, scope_signature
    except (
        binascii.Error,
        UnicodeDecodeError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError("Invalid transaction cursor") from exc


@bank_routes.route('/banks/<int:bank_id>/transactions', methods=['GET'])
@jwt_required()
def get_bank_transactions(bank_id):
    user_id = int(get_jwt_identity())
    bank = Bank.query.filter_by(id=bank_id, user_id=user_id).first()
    if not bank:
        return jsonify({"error": "Bank not found"}), 404

    # New clients use keyset pagination. Keep the previous page-number API
    # temporarily compatible so separately deployed frontend/backend versions
    # do not break during rollout. Requests from the updated frontend omit
    # `page`, so their normal path does not execute an exact count.
    legacy_page_request = "page" in request.args

    try:
        page_size = int(request.args.get('page_size', 25))
    except (TypeError, ValueError):
        page_size = 25

    # Keep the API bounded even if a client sends an excessively large value.
    page_size = min(max(page_size, 1), 100)

    search = (request.args.get('search') or '').strip()
    transaction_type = (request.args.get('type') or '').strip().lower()
    start_date_text = (request.args.get('start_date') or '').strip()
    end_date_text = (request.args.get('end_date') or '').strip()
    amount_range = (request.args.get('amount_range') or '').strip()

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

    # Free-text search covers description and category only. Amount and date
    # use typed filters below, allowing PostgreSQL to use appropriate indexes.
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(or_(
            BankTransaction.description.ilike(search_pattern),
            BankTransaction.category.ilike(search_pattern),
        ))

    # Stored timestamps are naive UTC by application convention. User-selected
    # dates represent IST calendar days, so use local-midnight boundaries
    # converted to naive UTC and keep the indexed column unwrapped.
    try:
        start_date_value = (
            datetime.strptime(start_date_text, "%Y-%m-%d").date()
            if start_date_text else None
        )
        end_date_value = (
            datetime.strptime(end_date_text, "%Y-%m-%d").date()
            if end_date_text else None
        )
    except ValueError:
        return jsonify({
            "error": "Dates must use YYYY-MM-DD format"
        }), 400

    if start_date_value and end_date_value and start_date_value > end_date_value:
        return jsonify({
            "error": "Start date must be on or before end date"
        }), 400

    if start_date_value:
        start_ist = IST.localize(datetime.combine(start_date_value, datetime.min.time()))
        start_utc = start_ist.astimezone(pytz.UTC).replace(tzinfo=None)
        query = query.filter(BankTransaction.date >= start_utc)

    if end_date_value:
        end_exclusive_date = end_date_value + timedelta(days=1)
        end_ist_exclusive = IST.localize(
            datetime.combine(end_exclusive_date, datetime.min.time())
        )
        end_utc_exclusive = end_ist_exclusive.astimezone(pytz.UTC).replace(tzinfo=None)
        query = query.filter(BankTransaction.date < end_utc_exclusive)

    amount_ranges = {
        "under_500": (0, 500),
        "500_1000": (500, 1000),
        "1000_5000": (1000, 5000),
        "5000_10000": (5000, 10000),
        "10000_plus": (10000, None),
    }
    if amount_range:
        bounds = amount_ranges.get(amount_range)
        if bounds is None:
            return jsonify({
                "error": "Invalid amount range filter"
            }), 400

        lower_bound, upper_bound = bounds
        query = query.filter(BankTransaction.amount >= lower_bound)
        if upper_bound is not None:
            query = query.filter(BankTransaction.amount < upper_bound)

    # The cursor is scoped to the exact filter set. This protects clients from
    # accidentally continuing with a cursor obtained for another search/filter.
    scope_signature = _bank_transaction_cursor_signature(
        bank_id=bank_id,
        user_id=user_id,
        page_size=page_size,
        search=search,
        transaction_type=transaction_type,
        start_date_value=start_date_value,
        end_date_value=end_date_value,
        amount_range=amount_range,
    )

    cursor_token = (request.args.get("cursor") or "").strip()
    if legacy_page_request and cursor_token:
        return jsonify({
            "error": "Use either legacy page pagination or cursor pagination, not both"
        }), 400

    query = query.order_by(
        BankTransaction.date.desc(),
        BankTransaction.id.desc(),
    )

    if legacy_page_request:
        # Compatibility path for a previously deployed frontend. The new
        # frontend does not send `page` and therefore does not pay this count.
        try:
            page = max(int(request.args.get("page", 1)), 1)
        except (TypeError, ValueError):
            page = 1

        total = query.count()
        total_pages = (total + page_size - 1) // page_size
        if total_pages and page > total_pages:
            page = total_pages
        transactions = query.offset((page - 1) * page_size).limit(page_size).all()

        return jsonify({
            "transactions": [_serialize_bank_transaction(tx) for tx in transactions],
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": total_pages,
        })

    if cursor_token:
        try:
            cursor_date, cursor_id, cursor_scope = _decode_bank_transaction_cursor(cursor_token)
        except ValueError:
            return jsonify({
                "error": "Invalid transaction cursor; restart from the first page"
            }), 400

        if cursor_scope != scope_signature:
            return jsonify({
                "error": "Transaction cursor does not match the current filters; restart pagination"
            }), 400

        # date DESC, id DESC requires the next page to contain lexicographically
        # smaller (date, id) pairs. The ID provides a stable tie-breaker when
        # multiple transactions have the same timestamp.
        query = query.filter(
            tuple_(BankTransaction.date, BankTransaction.id)
            < tuple_(cursor_date, cursor_id)
        )

    # Fetch one extra row to determine whether another page exists, avoiding
    # the exact COUNT(*) query on every new-client transaction-history request.
    fetched_transactions = query.limit(page_size + 1).all()
    has_more = len(fetched_transactions) > page_size
    transactions = fetched_transactions[:page_size]
    next_cursor = (
        _encode_bank_transaction_cursor(transactions[-1], scope_signature)
        if has_more and transactions
        else None
    )

    return jsonify({
        "transactions": [_serialize_bank_transaction(tx) for tx in transactions],
        "page_size": page_size,
        "has_more": has_more,
        "next_cursor": next_cursor,
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

