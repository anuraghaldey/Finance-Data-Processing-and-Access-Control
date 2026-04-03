import uuid

import bcrypt
from sqlalchemy.dialects.postgresql import UUID

from app.extensions import db


class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    updated_at = db.Column(db.DateTime, server_default=db.func.now(), onupdate=db.func.now())
    deleted_at = db.Column(db.DateTime, nullable=True)

    role = db.relationship('Role', back_populates='users', lazy='joined')
    records = db.relationship('FinancialRecord', back_populates='user', lazy='dynamic')
    refresh_tokens = db.relationship('RefreshToken', back_populates='user', lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('idx_users_active', 'is_active', 'deleted_at'),
    )

    def set_password(self, password):
        self.password_hash = bcrypt.hashpw(
            password.encode('utf-8'), bcrypt.gensalt(rounds=12)
        ).decode('utf-8')

    def check_password(self, password):
        return bcrypt.checkpw(
            password.encode('utf-8'), self.password_hash.encode('utf-8')
        )

    @property
    def is_deleted(self):
        return self.deleted_at is not None

    def __repr__(self):
        return f'<User {self.username}>'
