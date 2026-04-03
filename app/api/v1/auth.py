from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from marshmallow import ValidationError

from app.api.v1 import api_v1_bp
from app.schemas.user_schema import RegisterSchema, LoginSchema
from app.services import auth_service
from app.middleware.rate_limiter import role_rate_limit


@api_v1_bp.route('/auth/register', methods=['POST'])
def register():
    """Register a new user.
    ---
    tags: [Authentication]
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [username, email, password]
          properties:
            username: {type: string, example: john_doe}
            email: {type: string, example: john@example.com}
            password: {type: string, example: StrongPass1}
    responses:
      201: {description: User registered}
      409: {description: Email or username already exists}
      422: {description: Validation error}
    """
    data = RegisterSchema().load(request.get_json())
    user = auth_service.register_user(data)
    return jsonify({
        'message': 'User registered successfully',
        'user': {'id': str(user.id), 'username': user.username, 'email': user.email},
    }), 201


@api_v1_bp.route('/auth/login', methods=['POST'])
def login():
    """Authenticate and receive JWT tokens.
    ---
    tags: [Authentication]
    parameters:
      - in: body
        name: body
        schema:
          type: object
          required: [email, password]
          properties:
            email: {type: string, example: john@example.com}
            password: {type: string, example: StrongPass1}
    responses:
      200: {description: Login successful, returns tokens}
      401: {description: Invalid credentials}
    """
    data = LoginSchema().load(request.get_json())
    result = auth_service.login_user(data)
    return jsonify(result), 200


@api_v1_bp.route('/auth/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """Rotate access and refresh tokens.
    ---
    tags: [Authentication]
    security: [{Bearer: []}]
    responses:
      200: {description: New token pair}
      401: {description: Invalid or revoked refresh token}
      409: {description: Token refresh already in progress}
    """
    user_id = get_jwt_identity()
    token_jti = get_jwt()['jti']
    result = auth_service.refresh_tokens(user_id, token_jti)
    return jsonify(result), 200


@api_v1_bp.route('/auth/logout', methods=['POST'])
@jwt_required()
@role_rate_limit
def logout():
    """Revoke tokens and end session.
    ---
    tags: [Authentication]
    security: [{Bearer: []}]
    responses:
      200: {description: Logged out}
    """
    jwt_data = get_jwt()
    auth_service.logout_user(
        access_jti=jwt_data['jti'],
        access_exp=jwt_data['exp'],
    )
    return jsonify({'message': 'Logged out successfully'}), 200
