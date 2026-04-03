from flask import jsonify, current_app
from marshmallow import ValidationError as MarshmallowValidationError
from sqlalchemy.exc import IntegrityError

from app.errors.exceptions import AppException


def register_error_handlers(app):
    """Register global error handlers."""

    @app.errorhandler(AppException)
    def handle_app_exception(error):
        response = {'error': error.message}
        if error.payload:
            response.update(error.payload)
        return jsonify(response), error.status_code

    @app.errorhandler(MarshmallowValidationError)
    def handle_validation_error(error):
        return jsonify({
            'error': 'Validation error',
            'details': error.messages,
        }), 422

    @app.errorhandler(IntegrityError)
    def handle_integrity_error(error):
        from app.extensions import db
        db.session.rollback()
        return jsonify({
            'error': 'Data integrity error',
            'message': 'A record with this data already exists or a constraint was violated',
        }), 409

    @app.errorhandler(400)
    def bad_request(error):
        return jsonify({'error': 'Bad request'}), 400

    @app.errorhandler(401)
    def unauthorized(error):
        return jsonify({'error': 'Unauthorized'}), 401

    @app.errorhandler(403)
    def forbidden(error):
        return jsonify({'error': 'Forbidden'}), 403

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({'error': 'Resource not found'}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify({'error': 'Method not allowed'}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(error):
        return jsonify({'error': 'Rate limit exceeded. Try again later.'}), 429

    @app.errorhandler(500)
    def internal_error(error):
        from app.extensions import db
        db.session.rollback()
        current_app.logger.error(f'Internal server error: {error}')
        return jsonify({'error': 'Internal server error'}), 500
