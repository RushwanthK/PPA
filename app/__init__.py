from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register Blueprint
    from .routes import routes
    app.register_blueprint(routes)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app



"""
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    
    db.init_app(app)
    migrate.init_app(app, db)
    CORS(app)
    
    # Register Blueprint
    from .routes import routes
    app.register_blueprint(routes)

    # Create database tables
    with app.app_context():
        db.create_all()

    return app
"""