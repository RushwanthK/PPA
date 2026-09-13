import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))

    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]

    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)

    CORS_ORIGINS = os.environ["CORS_ORIGINS"]


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = False
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


def get_config():
    environment = os.environ.get("FLASK_ENV", "production")

    config_map = {
        "development": DevelopmentConfig,
        "testing": TestingConfig,
        "production": ProductionConfig,
    }

    return config_map.get(environment, ProductionConfig)