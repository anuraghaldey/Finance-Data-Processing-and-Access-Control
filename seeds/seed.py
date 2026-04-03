"""
Database seed script.
Creates roles, permissions, and the Super Admin user.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app import create_app
from app.extensions import db
from app.models.role import Role
from app.models.permission import RolePermission
from app.models.user import User


def seed_roles():
    """Create all roles if they don't exist."""
    for name, info in Role.ROLES.items():
        existing = Role.query.filter_by(name=name).first()
        if not existing:
            role = Role(name=name, hierarchy_level=info['level'], description=info['desc'])
            db.session.add(role)
            print(f'  Created role: {name} (level {info["level"]})')
        else:
            print(f'  Role exists: {name}')
    db.session.commit()


def seed_permissions():
    """Create fine-grained permissions for edge cases."""
    permissions = [
        # Admin can hard-delete records
        {'role': 'admin', 'resource': 'records', 'action': 'hard_delete'},
        {'role': 'super_admin', 'resource': 'records', 'action': 'hard_delete'},
        # Admin can manage users
        {'role': 'admin', 'resource': 'users', 'action': 'manage'},
        {'role': 'super_admin', 'resource': 'users', 'action': 'manage'},
        # Super Admin can manage admins
        {'role': 'super_admin', 'resource': 'users', 'action': 'manage_admins'},
        # Admin can view audit logs
        {'role': 'admin', 'resource': 'audit_logs', 'action': 'read'},
        {'role': 'super_admin', 'resource': 'audit_logs', 'action': 'read'},
    ]

    for perm in permissions:
        role = Role.query.filter_by(name=perm['role']).first()
        if not role:
            continue
        existing = RolePermission.query.filter_by(
            role_id=role.id, resource=perm['resource'], action=perm['action']
        ).first()
        if not existing:
            rp = RolePermission(role_id=role.id, resource=perm['resource'], action=perm['action'])
            db.session.add(rp)
            print(f'  Created permission: {perm["role"]} -> {perm["resource"]}:{perm["action"]}')
    db.session.commit()


def seed_super_admin(app):
    """Create the Super Admin user."""
    email = app.config['SUPER_ADMIN_EMAIL']
    existing = User.query.filter_by(email=email).first()
    if existing:
        print(f'  Super Admin exists: {email}')
        return

    sa_role = Role.query.filter_by(name=Role.SUPER_ADMIN).first()
    user = User(
        username='superadmin',
        email=email,
        role_id=sa_role.id,
        is_active=True,
    )
    user.set_password(app.config['SUPER_ADMIN_PASSWORD'])
    db.session.add(user)
    db.session.commit()
    print(f'  Created Super Admin: {email}')


def run_seed():
    app = create_app()
    with app.app_context():
        print('Seeding database...')
        print('\n[Roles]')
        seed_roles()
        print('\n[Permissions]')
        seed_permissions()
        print('\n[Super Admin]')
        seed_super_admin(app)
        print('\nSeeding complete!')


if __name__ == '__main__':
    run_seed()
