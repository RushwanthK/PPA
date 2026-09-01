from flask import Blueprint, jsonify, request
from flask_jwt_extended import create_access_token

from .. import db
from ..models import User
from ..utils.date_util import parse_date, calculate_age

login_routes = Blueprint("login_routes", __name__)

@login_routes.route('/register', methods=['POST'])
def register():
    data = request.get_json()

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
        return jsonify({
            "error": str(e)
        }), 500

@login_routes.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    name = data.get('name')
    password = data.get('password')

    if not name or not password:
        return jsonify({'error': 'Name and password required'}), 400

    user = User.query.filter_by(name=name).first()

    if not user or not user.check_password(password):
        return jsonify({'error': 'Invalid credentials'}), 401

    access_token = create_access_token(identity=str(user.id))
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
