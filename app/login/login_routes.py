import secrets
from functools import lru_cache

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, get_jwt_identity, jwt_required
from sqlalchemy import update
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db
from ..utils.errors import server_error
from ..models import User
from ..utils.auth_tokens import create_user_token, revoke_token
from ..utils.date_util import parse_date, calculate_age
from ..utils.rate_limit import (
    LOGIN_ACCOUNT_MESSAGE,
    LOGIN_IP_MESSAGE,
    REGISTER_IP_MESSAGE,
    is_failed_login,
    limiter,
    login_failure_rate_limit,
    login_rate_limit,
    login_username_key,
    register_rate_limit,
)

login_routes = Blueprint("login_routes", __name__)


def _json_object():
    """Request body as a dict; anything else (no JSON, a list, ...) -> {}."""
    data = request.get_json(silent=True)
    return data if isinstance(data, dict) else {}


@lru_cache(maxsize=1)
def _dummy_password_hash():
    """A hash in the same format as real ones (see User.set_password).

    Checking a password against it for unknown usernames makes "no such user"
    take as long as "wrong password", so response timing does not reveal which
    usernames exist. Created once per process on first use.
    """
    return generate_password_hash(
        secrets.token_urlsafe(32),
        method="pbkdf2:sha256",
        salt_length=8,
    )


@login_routes.route('/register', methods=['POST'])
@limiter.limit(register_rate_limit, error_message=REGISTER_IP_MESSAGE)
def register():
    data = _json_object()

    if not data.get('name') or not data.get('password') or not data.get('dob') or not data.get('place'):
        return jsonify({'error': 'Missing required fields'}), 400

    if User.query.filter_by(name=data['name']).first():
        return jsonify({'error': 'Username already taken'}), 400

    try:
        dob = parse_date(data['dob'])
        user = User(
            name=data['name'],
            dob=dob,
            age=calculate_age(dob),
            place=data['place']
        )
        user.set_password(data['password'])
        db.session.add(user)
        db.session.commit()

        return jsonify({'message': 'User registered successfully'}), 201

    except ValueError:
        db.session.rollback()
        return jsonify({
            "error": "Invalid date format. Use 'YYYY-MM-DD'."
        }), 400

    except Exception as e:
        db.session.rollback()
        return server_error()


# Two independent limits, both checked before the view (and its password
# hashing) runs:
#   1. per client IP: every attempt counts (brute force + CPU protection);
#   2. per account: only failed attempts (401) count, so a distributed attack
#      on one account is capped even when it comes from many IPs.
@login_routes.route('/login', methods=['POST'])
@limiter.limit(login_rate_limit, error_message=LOGIN_IP_MESSAGE)
@limiter.limit(
    login_failure_rate_limit,
    key_func=login_username_key,
    deduct_when=is_failed_login,
    error_message=LOGIN_ACCOUNT_MESSAGE,
)
def login():
    data = _json_object()
    name = data.get('name')
    password = data.get('password')

    if (
        not isinstance(name, str)
        or not isinstance(password, str)
        or not name
        or not password
    ):
        return jsonify({'error': 'Name and password required'}), 400

    user = User.query.filter_by(name=name).first()

    if not user:
        # Spend the same hashing time as a real check (timing equalization).
        check_password_hash(_dummy_password_hash(), password)
        return jsonify({'error': 'Invalid credentials'}), 401

    if not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_user_token(user)
    return jsonify({
        'token': access_token,
        'user': {
            'id': user.id,
            'name': user.name,
            'dob': user.dob.strftime("%Y-%m-%d"),
            'place': user.place,
            'age': user.age
        }
    }), 200


@login_routes.route('/logout', methods=['POST'])
@jwt_required()
def logout():
    """End the current token only (this device)."""
    revoke_token(get_jwt())
    db.session.commit()
    return jsonify({'message': 'Logged out'}), 200


@login_routes.route('/logout-all', methods=['POST'])
@jwt_required()
def logout_all():
    """End every token of this user, on every device, including this one."""
    user_id = int(get_jwt_identity())

    # Atomic increment in SQL: two concurrent requests cannot both read the
    # same old value and write the same new one.
    db.session.execute(
        update(User)
        .where(User.id == user_id)
        .values(token_version=User.token_version + 1)
    )
    db.session.commit()
    return jsonify({'message': 'Logged out of all devices'}), 200
