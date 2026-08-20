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
    from .dashboard_routes import dashboard_routes

    app.register_blueprint(routes)
    app.register_blueprint(dashboard_routes)

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