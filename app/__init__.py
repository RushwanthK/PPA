from flask import Flask, request, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object("config.Config")

    db.init_app(app)
    migrate.init_app(app, db)

    # ✅ ALLOW CORS ONLY FROM YOUR FRONTEND DOMAIN
    CORS(app, resources={r"/*": {"origins": [
        "https://rs-ppa.vercel.app",  # production frontend
        "http://localhost:3000"       # dev frontend
    ]}}, supports_credentials=True)

    # ✅ REGISTER ROUTES
    from .routes import routes
    app.register_blueprint(routes)

    # ✅ ADD HEADERS FOR SECURITY & CACHING
    @app.after_request
    def add_headers(response):
        # Optional: If you're serving HTML routes (usually for server-side rendered Flask apps)
        if response.content_type and response.content_type.startswith('text/html'):
            response.headers['Content-Type'] = 'text/html; charset=utf-8'

        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['Cache-Control'] = 'public, max-age=3600'
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