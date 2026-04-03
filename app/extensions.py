from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import redis

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()
cors = CORS()
limiter = Limiter(key_func=get_remote_address)

# Redis client initialized in app factory
redis_client = None


def init_redis(app):
    """Initialize Redis client with fallback handling."""
    global redis_client
    try:
        redis_client = redis.from_url(
            app.config['REDIS_URL'],
            decode_responses=True,
            socket_connect_timeout=3,
            socket_timeout=3,
            retry_on_timeout=True,
        )
        redis_client.ping()
        app.logger.info('Redis connected successfully')
    except (redis.ConnectionError, redis.TimeoutError):
        app.logger.warning('Redis unavailable — running with DB fallbacks')
        redis_client = None


def get_redis():
    """Get Redis client, may be None if Redis is down."""
    return redis_client
