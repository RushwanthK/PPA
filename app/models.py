from . import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    dob = db.Column(db.Date, nullable=False)
    place = db.Column(db.String(100), nullable=False)

class CreditCard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  # CC name
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    limit = db.Column(db.Float, nullable=False)
    used = db.Column(db.Float, nullable=False)
    balance = db.Column(db.Float, nullable=False)
    transactions = db.Column(db.Text)  # JSON or string format for transactions

class Asset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    transactions = db.Column(db.Text)  # JSON or string format for transactions

class Bank(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    transactions = db.Column(db.Text)  # JSON or string format for transactions

class Saving(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    bank_id = db.Column(db.Integer, db.ForeignKey('bank.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    balance = db.Column(db.Float, nullable=False)
    transactions = db.Column(db.Text)  # JSON or string format for transactions
