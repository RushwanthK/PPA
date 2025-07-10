from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager
import os  # You'll need this for the environment check

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")
    # Initialize JWT Manager
    jwt = JWTManager(app)

    db.init_app(app)
    migrate.init_app(app, db)

    # Enhanced CORS configuration
    if os.environ.get('FLASK_ENV') == 'development':
        CORS(app, supports_credentials=True)
    else:
        CORS(app, resources={r"/*": {"origins": [
            "https://rs-ppa.vercel.app",
            "http://localhost:3000"
        ]}}, supports_credentials=True, expose_headers=["Authorization"], allow_headers=["Content-Type", "Authorization"])

    # ✅ REGISTER ROUTES
    from .routes import routes
    app.register_blueprint(routes)

    # ✅ ADD HEADERS FOR SECURITY & CACHING
    @app.after_request
    def add_headers(response):
        if response.content_type:
            if response.content_type.startswith('text/html'):
                response.headers['Content-Type'] = 'text/html; charset=utf-8'

            elif response.content_type.startswith('application/json'):
                response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
                response.headers['Pragma'] = 'no-cache'
                response.headers['Expires'] = '0'

        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    # Create database tables
    #with app.app_context():
    #    db.create_all()

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