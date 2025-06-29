from flask import Flask, request, make_response
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

    # 🔒 Add security + performance headers to all responses
    @app.after_request
    def add_headers(response):
        # Set charset in Content-Type if it's a text-based response
        if response.content_type.startswith('text/html'):
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

        # Security header
        response.headers['X-Content-Type-Options'] = 'nosniff'

        # Caching header (adjust max-age as needed)
        response.headers['Cache-Control'] = 'public, max-age=3600'

        return response

    # Create database tables
    with app.app_context():
        db.create_all()

    return app




"""from flask import Flask
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