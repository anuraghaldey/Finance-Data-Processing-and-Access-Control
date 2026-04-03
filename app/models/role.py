from app.extensions import db


class Role(db.Model):
    __tablename__ = 'roles'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    hierarchy_level = db.Column(db.Integer, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    users = db.relationship('User', back_populates='role', lazy='dynamic')
    permissions = db.relationship('RolePermission', back_populates='role', lazy='select', cascade='all, delete-orphan')

    # Seed roles
    VIEWER = 'viewer'
    ANALYST = 'analyst'
    MANAGER = 'manager'
    ADMIN = 'admin'
    SUPER_ADMIN = 'super_admin'

    ROLES = {
        VIEWER: {'level': 1, 'desc': 'Read-only access to dashboard summaries and own profile'},
        ANALYST: {'level': 2, 'desc': 'View all financial records and access analytics'},
        MANAGER: {'level': 3, 'desc': 'Create, update, and soft-delete financial records'},
        ADMIN: {'level': 4, 'desc': 'Full management access including users and hard-delete'},
        SUPER_ADMIN: {'level': 5, 'desc': 'System-level access, manage admins, cannot be deleted'},
    }

    def __repr__(self):
        return f'<Role {self.name}>'
