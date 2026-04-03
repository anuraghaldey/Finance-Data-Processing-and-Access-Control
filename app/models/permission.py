from app.extensions import db


class RolePermission(db.Model):
    """Fine-grained permissions for edge cases beyond hierarchy level."""
    __tablename__ = 'role_permissions'

    id = db.Column(db.Integer, primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    resource = db.Column(db.String(50), nullable=False)  # e.g., 'records', 'users'
    action = db.Column(db.String(50), nullable=False)     # e.g., 'hard_delete', 'export'

    role = db.relationship('Role', back_populates='permissions')

    __table_args__ = (
        db.UniqueConstraint('role_id', 'resource', 'action', name='uq_role_resource_action'),
    )

    def __repr__(self):
        return f'<RolePermission {self.role_id}:{self.resource}:{self.action}>'
