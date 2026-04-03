import uuid

from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.extensions import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)  # 'create', 'update', 'delete', 'login', 'logout'
    resource = db.Column(db.String(50), nullable=False)  # 'user', 'record', 'auth'
    resource_id = db.Column(db.String(36), nullable=True)
    old_value = db.Column(JSONB, nullable=True)
    new_value = db.Column(JSONB, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)
    timestamp = db.Column(db.DateTime, server_default=db.func.now(), nullable=False)

    __table_args__ = (
        db.Index('idx_audit_timestamp', 'timestamp'),
        db.Index('idx_audit_user', 'user_id'),
    )

    def __repr__(self):
        return f'<AuditLog {self.action} {self.resource} by {self.user_id}>'
