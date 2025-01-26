from flask import Blueprint, request, jsonify
from . import db
from .models import CreditCard, Asset, Saving

routes = Blueprint('routes', __name__)

@routes.route('/')
def home():
    return "Welcome to the Personal Portfolio App!"

# CRUD for Credit Cards
@routes.route('/credit_cards', methods=['GET', 'POST'])
def manage_credit_cards():
    if request.method == 'POST':
        data = request.json
        card = CreditCard(card_name=data['card_name'], limit=data['limit'], used_amount=data['used_amount'])
        db.session.add(card)
        db.session.commit()
        return jsonify({"message": "Credit Card added!"}), 201
    else:
        cards = CreditCard.query.all()
        return jsonify([{
            "id": card.id,
            "card_name": card.card_name,
            "limit": card.limit,
            "used_amount": card.used_amount
        } for card in cards])
