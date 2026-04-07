from datetime import datetime, timezone

from flask_jwt_extended import create_access_token, create_refresh_token, decode_token

from app.extensions import db, get_redis
from app.models.user import User
from app.models.role import Role
from app.models.refresh_token import RefreshToken
from app.models.revoked_token import RevokedToken
from app.middleware.audit import log_audit
from app.errors.exceptions import (
    AuthenticationException, ConflictException, NotFoundException, ValidationException
)


def _build_jwt_claims(user):
    return {
        'role': user.role.name,
        'role_id': user.role.id,
        'hierarchy_level': user.role.hierarchy_level,
        'is_active': user.is_active,
        'username': user.username,
    }


def register_user(data):
    if User.query.filter_by(email=data['email']).first():
        raise ConflictException('Email already registered')
    if User.query.filter_by(username=data['username']).first():
        raise ConflictException('Username already taken')

    viewer_role = Role.query.filter_by(name=Role.VIEWER).first()
    if not viewer_role:
        raise ValidationException('System roles not initialized. Run database seed.')

    user = User(
        username=data['username'],
        email=data['email'],
        role_id=viewer_role.id,
    )
    user.set_password(data['password'])

    db.session.add(user)
    log_audit('create', 'user', resource_id=user.id,
              new_value={'username': user.username, 'email': user.email, 'role': 'viewer'})
    db.session.commit()

    return user


def login_user(data):
    user = User.query.filter_by(email=data['email']).first()

    if not user or not user.check_password(data['password']):
        raise AuthenticationException('Invalid email or password')

    if not user.is_active:
        raise AuthenticationException('Account is deactivated')

    if user.is_deleted:
        raise AuthenticationException('Account has been deleted')

    claims = _build_jwt_claims(user)
    access_token = create_access_token(identity=str(user.id), additional_claims=claims)
    refresh_token = create_refresh_token(identity=str(user.id), additional_claims=claims)

    # Store refresh token JTI
    decoded = decode_token(refresh_token)
    rt = RefreshToken(
        user_id=user.id,
        token_jti=decoded['jti'],
        expires_at=datetime.fromtimestamp(decoded['exp'], tz=timezone.utc),
    )
    db.session.add(rt)

    user.last_login = datetime.now(timezone.utc)
    log_audit('login', 'auth', resource_id=user.id)
    db.session.commit()

    return {
        'access_token': access_token,
        'refresh_token': refresh_token,
        'user': {
            'id': str(user.id),
            'username': user.username,
            'email': user.email,
            'role': user.role.name,
        }
    }


def refresh_tokens(user_id, token_jti):
    """
    Rotate tokens: revoke old refresh token, issue new pair.
    Uses Redis SETNX lock to prevent race conditions on concurrent refresh requests.
    """
    r = get_redis()
    lock_key = f'refresh_lock:{token_jti}'

    # Atomic lock to prevent double-refresh race condition
    if r:
        try:
            if not r.set(lock_key, '1', nx=True, ex=5):
                raise ConflictException('Token refresh already in progress')
        except Exception:
            pass  # If Redis fails, proceed without lock (acceptable risk)

    # Revoke old refresh token
    rt = RefreshToken.query.filter_by(token_jti=token_jti, revoked=False).first()
    if not rt:
        raise AuthenticationException('Refresh token is invalid or already revoked')

    rt.revoked = True

    user = User.query.get(user_id)
    if not user or not user.is_active or user.is_deleted:
        raise AuthenticationException('User account is invalid')

    claims = _build_jwt_claims(user)
    new_access = create_access_token(identity=str(user.id), additional_claims=claims)
    new_refresh = create_refresh_token(identity=str(user.id), additional_claims=claims)

    # Store new refresh token
    decoded = decode_token(new_refresh)
    new_rt = RefreshToken(
        user_id=user.id,
        token_jti=decoded['jti'],
        expires_at=datetime.fromtimestamp(decoded['exp'], tz=timezone.utc),
    )
    db.session.add(new_rt)
    db.session.commit()

    return {'access_token': new_access, 'refresh_token': new_refresh}


def logout_user(access_jti, access_exp, refresh_jti=None):
    r = get_redis()
    exp_time = datetime.fromtimestamp(access_exp, tz=timezone.utc)
    ttl = int((exp_time - datetime.now(timezone.utc)).total_seconds())

    # Blocklist access token
    if r:
        try:
            r.setex(f'blocklist:{access_jti}', max(ttl, 1), '1')
        except Exception:
            # Fallback to DB
            RevokedToken.add(access_jti, exp_time)
    else:
        RevokedToken.add(access_jti, exp_time)

    # Revoke refresh token
    if refresh_jti:
        rt = RefreshToken.query.filter_by(token_jti=refresh_jti).first()
        if rt:
            rt.revoked = True
            db.session.commit()

    return True
