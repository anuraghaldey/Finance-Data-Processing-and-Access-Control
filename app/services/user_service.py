from datetime import datetime, timezone

from app.extensions import db
from app.models.user import User
from app.models.role import Role
from app.middleware.audit import log_audit
from app.errors.exceptions import NotFoundException, ConflictException, AuthorizationException
from app.utils.pagination import paginate_query


def get_users(cursor=None, limit=20):
    """List all non-deleted users with cursor pagination."""
    query = User.query.filter(User.deleted_at.is_(None))
    items, next_cursor, has_more = paginate_query(
        query, User, sort_by='created_at', sort_order='desc',
        cursor=cursor, limit=limit,
    )
    return items, next_cursor, has_more


def get_user_by_id(user_id):
    user = User.query.get(user_id)
    if not user or user.is_deleted:
        raise NotFoundException('User')
    return user


def update_user(user_id, data, current_user_id, current_role_level):
    """Update user profile. Users can update themselves, Admins can update anyone."""
    user = get_user_by_id(user_id)

    # Self-update or admin check
    if str(user.id) != str(current_user_id) and current_role_level < 4:
        raise AuthorizationException('Can only update own profile or requires Admin role')

    old_data = {'username': user.username, 'email': user.email}

    if 'username' in data:
        existing = User.query.filter_by(username=data['username']).first()
        if existing and existing.id != user.id:
            raise ConflictException('Username already taken')
        user.username = data['username']

    if 'email' in data:
        existing = User.query.filter_by(email=data['email']).first()
        if existing and existing.id != user.id:
            raise ConflictException('Email already registered')
        user.email = data['email']

    log_audit('update', 'user', resource_id=user.id,
              old_value=old_data,
              new_value={'username': user.username, 'email': user.email})
    db.session.commit()
    return user


def change_user_role(user_id, role_name, current_role_level):
    """Assign a new role to a user. Only Admin+ can do this."""
    user = get_user_by_id(user_id)
    new_role = Role.query.filter_by(name=role_name).first()

    if not new_role:
        raise NotFoundException('Role')

    # Cannot assign a role higher than or equal to your own
    if new_role.hierarchy_level >= current_role_level:
        raise AuthorizationException('Cannot assign a role equal to or higher than your own')

    old_role = user.role.name
    user.role_id = new_role.id

    log_audit('update', 'user', resource_id=user.id,
              old_value={'role': old_role},
              new_value={'role': role_name})
    db.session.commit()
    return user


def update_user_status(user_id, is_active, current_user_id):
    user = get_user_by_id(user_id)

    if str(user.id) == str(current_user_id):
        raise AuthorizationException('Cannot deactivate your own account')

    # Cannot deactivate Super Admin
    if user.role.name == Role.SUPER_ADMIN:
        raise AuthorizationException('Cannot modify Super Admin status')

    old_status = user.is_active
    user.is_active = is_active

    log_audit('update', 'user', resource_id=user.id,
              old_value={'is_active': old_status},
              new_value={'is_active': is_active})
    db.session.commit()
    return user


def soft_delete_user(user_id, current_user_id):
    user = get_user_by_id(user_id)

    if str(user.id) == str(current_user_id):
        raise AuthorizationException('Cannot delete your own account')

    if user.role.name == Role.SUPER_ADMIN:
        raise AuthorizationException('Cannot delete Super Admin')

    user.deleted_at = datetime.now(timezone.utc)
    user.is_active = False

    log_audit('delete', 'user', resource_id=user.id,
              old_value={'username': user.username, 'is_active': True})
    db.session.commit()
    return user
