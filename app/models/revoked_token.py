from app.extensions import db


class RevokedToken(db.Model):
    """DB fallback for JWT blocklist when Redis is unavailable."""
    __tablename__ = 'revoked_tokens'

    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, nullable=False, index=True)
    revoked_at = db.Column(db.DateTime, server_default=db.func.now())
    expires_at = db.Column(db.DateTime, nullable=False)

    @classmethod
    def is_revoked(cls, jti):
        return db.session.query(
            cls.query.filter_by(jti=jti).exists()
        ).scalar()

    @classmethod
    def add(cls, jti, expires_at):
        token = cls(jti=jti, expires_at=expires_at)
        db.session.add(token)
        db.session.commit()

    @classmethod
    def cleanup_expired(cls):
        """Remove expired entries to keep the table small."""
        cls.query.filter(cls.expires_at < db.func.now()).delete()
        db.session.commit()

    def __repr__(self):
        return f'<RevokedToken {self.jti}>'
