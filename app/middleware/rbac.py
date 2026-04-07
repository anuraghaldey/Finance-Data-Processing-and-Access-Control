from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.models.role import Role
from app.models.permission import RolePermission


def role_required(min_role):
    """Hierarchy-based access control."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            user_level = claims.get('hierarchy_level', 0)
            required_level = Role.ROLES.get(min_role, {}).get('level', 999)

            if user_level < required_level:
                return jsonify({
                    'error': 'Insufficient permissions',
                    'required_role': min_role,
                }), 403

            if not claims.get('is_active', False):
                return jsonify({'error': 'Account is deactivated'}), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator


def permission_required(resource, action):
    """Fine-grained permission check for specific resource+action."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            role_id = claims.get('role_id')

            has_permission = RolePermission.query.filter_by(
                role_id=role_id, resource=resource, action=action
            ).first() is not None

            if not has_permission:
                return jsonify({
                    'error': 'Insufficient permissions',
                    'required': f'{resource}:{action}',
                }), 403

            return fn(*args, **kwargs)
        return wrapper
    return decorator
