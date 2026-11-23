import os
from datetime import timedelta

from dotenv import load_dotenv


load_dotenv()


def _env_bool(name, default):
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Opt-in request/SQL timing for performance diagnosis. Keep disabled by default.
    PERF_DIAGNOSTICS_ENABLED = os.environ.get(
        "PPA_PERF_DIAGNOSTICS", "false"
    ).strip().lower() in {"1", "true", "yes", "on"}

    SECRET_KEY = os.environ.get("SECRET_KEY", os.urandom(24))

    SQLALCHEMY_DATABASE_URI = os.environ["DATABASE_URL"]
    REDIS_URL = os.environ.get("REDIS_URL")
    DASHBOARD_CACHE_TTL_SECONDS = int(
        os.environ.get("DASHBOARD_CACHE_TTL_SECONDS", "60")
    )
    REDIS_MAX_CONNECTIONS = int(
        os.environ.get("REDIS_MAX_CONNECTIONS", "5")
    )

    JWT_SECRET_KEY = os.environ["JWT_SECRET_KEY"]
    JWT_TOKEN_LOCATION = ["headers"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(days=1)

    CORS_ORIGINS = os.environ["CORS_ORIGINS"]

    # Largest request body accepted. Every PPA request is a small JSON object
    # (a few KB at most); bigger bodies get 413 before Flask reads them.
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_REQUEST_KB", "256")) * 1024

    # Number of reverse proxies in front of Flask that append to
    # X-Forwarded-For. 0 = trust no forwarded headers (local development).
    # On Render this must match the real proxy hop count, otherwise every
    # client appears to have the proxy's IP (or clients can spoof their IP).
    TRUSTED_PROXY_COUNT = int(os.environ.get("TRUSTED_PROXY_COUNT", "0"))

    # Temporary diagnostic for choosing TRUSTED_PROXY_COUNT: when on, every
    # GET / logs the proxy-related headers Flask received (one WARNING line).
    # The log contains client IP addresses, so switch it off afterwards.
    PROXY_DIAGNOSTICS = _env_bool("PROXY_DIAGNOSTICS", False)

    # ---- Rate limiting (Flask-Limiter) ----
    # Counters live in the existing Redis under their own key prefix. If Redis
    # is unreachable, Flask-Limiter falls back to per-process memory with the
    # SAME route limits (no RATELIMIT_IN_MEMORY_FALLBACK list on purpose: that
    # would replace the route limits on every endpoint during an outage).
    RATELIMIT_ENABLED = _env_bool("RATELIMIT_ENABLED", True)
    RATELIMIT_STORAGE_URI = os.environ.get("REDIS_URL") or "memory://"
    RATELIMIT_STORAGE_OPTIONS = {
        # Fail fast like the dashboard cache, so a Redis outage cannot hang
        # the login request; the fallback takes over instead.
        "socket_connect_timeout": 0.2,
        "socket_timeout": 0.2,
        "health_check_interval": 30,
        "max_connections": int(os.environ.get("RATELIMIT_REDIS_MAX_CONNECTIONS", "5")),
    }
    RATELIMIT_KEY_PREFIX = "ppa:ratelimit"
    # Exact sliding window: each hit is a timestamp, so there is no burst at
    # fixed-window boundaries. Cheap here because the limits are small.
    RATELIMIT_STRATEGY = "moving-window"
    RATELIMIT_IN_MEMORY_FALLBACK_ENABLED = True
    # The failed-login counter is written after the response is built; never
    # turn a normal 401 into a 500 because Redis failed at that moment.
    RATELIMIT_SWALLOW_ERRORS = True
    RATELIMIT_HEADERS_ENABLED = True

    # Limits use the "limits" notation; several separated by ";".
    LOGIN_RATE_LIMIT = os.environ.get(
        "LOGIN_RATE_LIMIT", "10 per minute;50 per hour"
    )
    LOGIN_FAILURE_RATE_LIMIT = os.environ.get(
        "LOGIN_FAILURE_RATE_LIMIT", "5 per 15 minutes"
    )
    REGISTER_RATE_LIMIT = os.environ.get("REGISTER_RATE_LIMIT", "3 per hour")
    PASSWORD_CHANGE_FAILURE_RATE_LIMIT = os.environ.get(
        "PASSWORD_CHANGE_FAILURE_RATE_LIMIT", "5 per 15 minutes"
    )


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    # Tests must not depend on a running external Redis service.
    REDIS_URL = None
    RATELIMIT_STORAGE_URI = "memory://"
    TRUSTED_PROXY_COUNT = 0
    PROXY_DIAGNOSTICS = False
    # Fixed limits for the rate-limit tests, independent of local env vars.
    LOGIN_RATE_LIMIT = "10 per minute;50 per hour"
    LOGIN_FAILURE_RATE_LIMIT = "5 per 15 minutes"
    REGISTER_RATE_LIMIT = "3 per hour"
    PASSWORD_CHANGE_FAILURE_RATE_LIMIT = "5 per 15 minutes"


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