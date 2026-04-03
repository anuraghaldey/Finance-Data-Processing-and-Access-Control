from flask import jsonify, request
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from app.api.v1 import api_v1_bp
from app.middleware.rbac import role_required
from app.middleware.rate_limiter import role_rate_limit
from app.schemas.user_schema import (
    UserResponseSchema, UserUpdateSchema, RoleAssignSchema, StatusUpdateSchema
)
from app.services import user_service

user_schema = UserResponseSchema()
users_schema = UserResponseSchema(many=True)


@api_v1_bp.route('/users', methods=['GET'])
@jwt_required()
@role_required('admin')
@role_rate_limit
def list_users():
    """List all users with pagination.
    ---
    tags: [Users]
    security: [{Bearer: []}]
    parameters:
      - {in: query, name: cursor, type: string}
      - {in: query, name: limit, type: integer, default: 20}
    responses:
      200: {description: Paginated user list}
    """
    cursor = request.args.get('cursor')
    limit = request.args.get('limit', 20, type=int)

    users, next_cursor, has_more = user_service.get_users(cursor=cursor, limit=limit)

    return jsonify({
        'users': users_schema.dump(users),
        'pagination': {
            'next_cursor': next_cursor,
            'has_more': has_more,
            'limit': limit,
        }
    }), 200


@api_v1_bp.route('/users/<user_id>', methods=['GET'])
@jwt_required()
@role_rate_limit
def get_user(user_id):
    """Get user profile.
    ---
    tags: [Users]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: user_id, type: string, required: true}
    responses:
      200: {description: User details}
      404: {description: User not found}
    """
    claims = get_jwt()
    current_user_id = get_jwt_identity()

    # Viewers and Analysts can only see their own profile
    if str(user_id) != str(current_user_id) and claims.get('hierarchy_level', 0) < 4:
        return jsonify({'error': 'Can only view own profile or requires Admin role'}), 403

    user = user_service.get_user_by_id(user_id)
    return jsonify({'user': user_schema.dump(user)}), 200


@api_v1_bp.route('/users/<user_id>', methods=['PUT'])
@jwt_required()
@role_rate_limit
def update_user(user_id):
    """Update user information.
    ---
    tags: [Users]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: user_id, type: string, required: true}
      - in: body
        name: body
        schema:
          type: object
          properties:
            username: {type: string}
            email: {type: string}
    responses:
      200: {description: User updated}
    """
    data = UserUpdateSchema().load(request.get_json())
    claims = get_jwt()
    current_user_id = get_jwt_identity()

    user = user_service.update_user(
        user_id, data, current_user_id, claims.get('hierarchy_level', 0)
    )
    return jsonify({'user': user_schema.dump(user), 'message': 'User updated'}), 200


@api_v1_bp.route('/users/<user_id>/role', methods=['PATCH'])
@jwt_required()
@role_required('admin')
@role_rate_limit
def change_role(user_id):
    """Change user role.
    ---
    tags: [Users]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: user_id, type: string, required: true}
      - in: body
        name: body
        schema:
          type: object
          required: [role_name]
          properties:
            role_name: {type: string, enum: [viewer, analyst, manager, admin]}
    responses:
      200: {description: Role changed}
    """
    data = RoleAssignSchema().load(request.get_json())
    claims = get_jwt()

    user = user_service.change_user_role(
        user_id, data['role_name'], claims.get('hierarchy_level', 0)
    )
    return jsonify({'user': user_schema.dump(user), 'message': 'Role updated'}), 200


@api_v1_bp.route('/users/<user_id>/status', methods=['PATCH'])
@jwt_required()
@role_required('admin')
@role_rate_limit
def update_status(user_id):
    """Activate or deactivate user.
    ---
    tags: [Users]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: user_id, type: string, required: true}
      - in: body
        name: body
        schema:
          type: object
          required: [is_active]
          properties:
            is_active: {type: boolean}
    responses:
      200: {description: Status updated}
    """
    data = StatusUpdateSchema().load(request.get_json())
    current_user_id = get_jwt_identity()

    user = user_service.update_user_status(user_id, data['is_active'], current_user_id)
    return jsonify({'user': user_schema.dump(user), 'message': 'Status updated'}), 200


@api_v1_bp.route('/users/<user_id>', methods=['DELETE'])
@jwt_required()
@role_required('admin')
@role_rate_limit
def delete_user(user_id):
    """Soft delete a user.
    ---
    tags: [Users]
    security: [{Bearer: []}]
    parameters:
      - {in: path, name: user_id, type: string, required: true}
    responses:
      200: {description: User deleted}
    """
    current_user_id = get_jwt_identity()
    user_service.soft_delete_user(user_id, current_user_id)
    return jsonify({'message': 'User deleted'}), 200
