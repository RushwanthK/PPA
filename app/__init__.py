from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_cors import CORS
from dotenv import load_dotenv
from flask_jwt_extended import JWTManager


load_dotenv()

db = SQLAlchemy()
migrate = Migrate()


def create_app():
    app = Flask(__name__)

    from config import get_config

    app.config.from_object(get_config())

    JWTManager(app)

    db.init_app(app)
    migrate.init_app(app, db)

    # Allow local development and tests to use the same local CORS behavior.
    CORS(
        app,
        resources={
            r"/*": {
                "origins": app.config["CORS_ORIGINS"]
            }
        },
        supports_credentials=True,
        expose_headers=["Authorization"],
        allow_headers=["Content-Type", "Authorization"],
    )

    from .routes import routes
    from .dashboard.dashboard_routes import dashboard_routes
    from .users.users_routes import users_routes
    from .banks.bank_routes import bank_routes
    from .savings.savings_routes import savings_routes
    from .assets.assets_routes import assets_routes
    from .credit_cards.credit_card_routes import credit_card_routes
    from .login.login_routes import login_routes


    app.register_blueprint(routes)
    app.register_blueprint(dashboard_routes)
    app.register_blueprint(users_routes)
    app.register_blueprint(bank_routes)
    app.register_blueprint(savings_routes)
    app.register_blueprint(assets_routes)
    app.register_blueprint(credit_card_routes)
    app.register_blueprint(login_routes)

    @app.after_request
    def add_headers(response):
        if response.content_type:
            if response.content_type.startswith("text/html"):
                response.headers["Content-Type"] = "text/html; charset=utf-8"

            elif response.content_type.startswith("application/json"):
                response.headers["Cache-Control"] = (
                    "no-cache, no-store, must-revalidate"
                )
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    return app