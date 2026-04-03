import pytest

from app import create_app
from app.extensions import db as _db
from app.models.role import Role
from app.models.permission import RolePermission
from app.models.user import User


@pytest.fixture(scope='session')
def app():
    """Create application for testing."""
    app = create_app('testing')
    with app.app_context():
        yield app


@pytest.fixture(scope='function')
def db(app):
    """Create fresh database for each test."""
    with app.app_context():
        _db.create_all()
        yield _db
        _db.session.rollback()
        _db.drop_all()


@pytest.fixture
def client(app, db):
    """Test client."""
    return app.test_client()


@pytest.fixture
def seed_roles(db):
    """Seed all roles."""
    roles = {}
    for name, info in Role.ROLES.items():
        role = Role(name=name, hierarchy_level=info['level'], description=info['desc'])
        db.session.add(role)
        roles[name] = role
    db.session.commit()
    return roles


@pytest.fixture
def seed_permissions(db, seed_roles):
    """Seed permissions."""
    admin_role = seed_roles['admin']
    sa_role = seed_roles['super_admin']

    perms = [
        RolePermission(role_id=admin_role.id, resource='records', action='hard_delete'),
        RolePermission(role_id=sa_role.id, resource='records', action='hard_delete'),
    ]
    for p in perms:
        db.session.add(p)
    db.session.commit()


def create_user(db, seed_roles, role_name='viewer', username='testuser', email='test@test.com', password='TestPass1'):
    """Helper to create a user with a given role."""
    role = seed_roles[role_name]
    user = User(username=username, email=email, role_id=role.id)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    return user


@pytest.fixture
def viewer_user(db, seed_roles):
    return create_user(db, seed_roles, 'viewer', 'viewer1', 'viewer@test.com')


@pytest.fixture
def analyst_user(db, seed_roles):
    return create_user(db, seed_roles, 'analyst', 'analyst1', 'analyst@test.com')


@pytest.fixture
def manager_user(db, seed_roles):
    return create_user(db, seed_roles, 'manager', 'manager1', 'manager@test.com')


@pytest.fixture
def admin_user(db, seed_roles):
    return create_user(db, seed_roles, 'admin', 'admin1', 'admin@test.com')


def get_auth_headers(client, email='test@test.com', password='TestPass1'):
    """Helper to login and get auth headers."""
    response = client.post('/api/v1/auth/login', json={
        'email': email, 'password': password
    })
    token = response.get_json()['access_token']
    return {'Authorization': f'Bearer {token}'}
