import os

from flask import Flask
from flasgger import Swagger

from app.config import config_by_name
from app.extensions import db, migrate, jwt, cors, limiter, init_redis, get_redis
from app.errors.handlers import register_error_handlers


def create_app(config_name=None):
    """Application factory pattern."""
    if config_name is None:
        config_name = os.getenv('FLASK_ENV', 'development')

    app = Flask(__name__)
    app.config.from_object(config_by_name[config_name])

    # Initialize extensions
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})
    limiter.init_app(app)
    init_redis(app)

    # Swagger docs
    app.config['SWAGGER'] = {
        'title': 'Finance Data Processing & Access Control API',
        'version': '1.0',
        'description': 'Backend API for finance dashboard with RBAC and analytics',
        'uiversion': 3,
    }
    Swagger(app)

    # JWT blocklist check
    @jwt.token_in_blocklist_loader
    def check_token_blocklist(jwt_header, jwt_payload):
        jti = jwt_payload['jti']
        r = get_redis()
        if r:
            try:
                return r.get(f'blocklist:{jti}') is not None
            except Exception:
                pass
        # Fallback to DB
        from app.models.revoked_token import RevokedToken
        return RevokedToken.is_revoked(jti)

    # Register error handlers
    register_error_handlers(app)

    # Register blueprints
    from app.api.v1 import api_v1_bp
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')

    # Import models for migrations
    with app.app_context():
        from app.models import user, role, permission, financial_record, audit_log, refresh_token, revoked_token  # noqa: F401

    # DSA warm-up + cross-worker Pub/Sub sync.
    # Skipped for testing config (tests manage their own DB lifecycle).
    if not app.config.get('TESTING'):
        from app.utils.dsa_sync import warm_up_dsas, start_background_sync
        warm_up_dsas(app)
        start_background_sync(app)

    return app
