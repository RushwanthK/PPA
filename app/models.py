from . import db
from datetime import datetime, timedelta, timezone
from sqlalchemy import event, Column, Integer, String, Float, Date, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import validates, declared_attr

class User(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Added unique=True
    age = Column(Integer, nullable=False)
    dob = Column(Date, nullable=False)
    place = Column(String(100), nullable=False)
    banks = db.relationship('Bank', backref='user', lazy=True, cascade="all, delete-orphan")
    credit_cards = db.relationship('CreditCard', backref='user', lazy=True, cascade="all, delete-orphan")
    assets = db.relationship('Asset', backref='user', lazy=True, cascade="all, delete-orphan")
    savings = db.relationship('Saving', backref='user', lazy=True, cascade="all, delete-orphan")
    transactions = db.relationship('Transaction', backref='user', lazy=True)

    def __repr__(self):
        return f'<User {self.name}>'

class CreditCard(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Added unique=True
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)  # user id
    billing_cycle_start = Column(Integer, nullable=False, default=1)  # Day of month when billing cycle starts
    limit = Column(Float, nullable=False)  # CC limit
    
    # Track spending
    used = Column(Float, nullable=False, default=0)  # total spends (all transactions)
    # Remove the outstanding field since it's deprecated
    # outstanding = Column(Float, nullable=False, default=0)  # Remove this line
    
    # Track payment status
    last_payment_date = Column(DateTime)
    last_payment_amount = Column(Float)
    
    # New columns
    billed_unpaid = Column(Float, default=0)    # From last bill (definitely payable)
    unbilled_spends = Column(Float, default=0)  # Current cycle spends (payable only if billing date passed)
    
    @property
    def available_limit(self):
        return self.limit - self.used
    
    @property
    def total_payable(self):
        """Amount that should be paid based on current date and billing cycle"""
        # Only the billed_unpaid amount should be payable, regardless of current date
        return self.billed_unpaid
    # 'Note': Temporary redundancy during transition period:
    # - outstanding ≈ unbilled_spends (will be removed)

    transactions = db.relationship('CreditCardTransaction', backref='credit_card', lazy=True)

    def __repr__(self):
        return f'<CreditCard {self.name} for User {self.user_id}>'

class Asset(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Added unique=True
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    platform = Column(String(100), nullable=True)  # New column
    category = Column(String(50), nullable=True)    # New column
    balance = Column(Float, nullable=False, default=0)
    transactions = db.relationship('AssetTransaction', backref='asset', lazy=True)

    def __repr__(self):
        return f'<Asset {self.name} for User {self.user_id}>'

class Bank(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Added unique=True
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    balance = Column(Float, nullable=False, default=0)
    transactions = db.relationship('BankTransaction', backref='bank', lazy=True)
    savings_accounts = db.relationship('Saving', backref='bank', lazy=True)

    def __repr__(self):
        return f'<Bank {self.name} for User {self.user_id}>'

    def can_delete(self):
        return self.balance == 0 and len(self.savings_accounts) == 0
    
    def as_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'balance': self.balance,
            'user_id': self.user_id
        }

class Saving(db.Model):
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False, unique=True)  # Added unique=True
    bank_id = Column(Integer, ForeignKey('bank.id'), nullable=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    balance = Column(Float, nullable=False, default=0)
    transactions = db.relationship('SavingTransaction', backref='saving', lazy=True)

    def __repr__(self):
        return f'<Saving {self.name} for User {self.user_id}>'

# ========== TRANSACTION MODELS ==========

class Transaction(db.Model):
    """Base transaction model"""
    __tablename__ = 'transaction'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(String(200))
    category = Column(String(50))
    transaction_type = Column(String(20))
    
    # Polymorphic discriminator
    type = Column(String(50))
    
    __mapper_args__ = {
        'polymorphic_identity': 'transaction',
        'polymorphic_on': type
    }

    def __repr__(self):
        return f'<Transaction {self.id} by User {self.user_id}>'

class BankTransaction(Transaction):
    bank_id = Column(Integer, ForeignKey('bank.id'))
    bank_balance_after = Column(Float)  # Renamed to avoid conflict
    
    __mapper_args__ = {
        'polymorphic_identity': 'bank_transaction'
    }

class CreditCardTransaction(Transaction):
    credit_card_id = Column(Integer, ForeignKey('credit_card.id'))
    card_balance_after = Column(Float)  # Renamed to avoid conflict
    is_payment = Column(Boolean, default=False)
    is_billed = Column(Boolean, default=False)  # Add this line
    
    __mapper_args__ = {
        'polymorphic_identity': 'credit_card_transaction'
    }

class AssetTransaction(Transaction):
    asset_id = Column(Integer, ForeignKey('asset.id'))
    asset_balance_after = Column(Float)  # Renamed to avoid conflict
    
    __mapper_args__ = {
        'polymorphic_identity': 'asset_transaction'
    }

class SavingTransaction(Transaction):
    saving_id = Column(Integer, ForeignKey('saving.id'))
    saving_balance_after = Column(Float)  # Renamed to avoid conflict
    
    __mapper_args__ = {
        'polymorphic_identity': 'saving_transaction'
    }

class TransferTransaction(db.Model):
    """Special transaction to track transfers between accounts"""
    __tablename__ = 'transfer_transaction'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    from_account_type = Column(String(20))
    from_account_id = Column(Integer)
    to_account_type = Column(String(20))
    to_account_id = Column(Integer)
    amount = Column(Float, nullable=False)
    date = Column(DateTime, default=datetime.utcnow, nullable=False)
    description = Column(String(200))
    fee = Column(Float, default=0)

    def __repr__(self):
        return f'<Transfer {self.amount} from {self.from_account_type}:{self.from_account_id} to {self.to_account_type}:{self.from_account_id}>'