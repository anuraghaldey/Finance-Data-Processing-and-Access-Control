import uuid

from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class RefreshToken(db.Model):
    __tablename__ = 'refresh_tokens'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = db.Column(UUID(as_uuid=True), db.ForeignKey('users.id'), nullable=False)
    token_jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

    user = db.relationship('User', back_populates='refresh_tokens')

    def __repr__(self):
        return f'<RefreshToken {self.token_jti} revoked={self.revoked}>'
