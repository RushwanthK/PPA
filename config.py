import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY', os.urandom(24))
    
    SQLALCHEMY_DATABASE_URI = (
        os.environ['LOCAL_DATABASE_URL'] 
        if os.environ.get('FLASK_ENV') == 'development'
        else os.environ['DATABASE_URL']
    )

class DevelopmentConfig(Config):
    DEBUG = True

class ProductionConfig(Config):
    DEBUG = False

# Determine which config to use
if os.environ.get('FLASK_ENV') == 'development':
    app_config = DevelopmentConfig()
else:
    app_config = ProductionConfig()

"""
import os
from dotenv import load_dotenv
load_dotenv()

class Config:
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.urandom(24)
"""