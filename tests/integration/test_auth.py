"""Integration tests for authentication endpoints."""

import pytest
from tests.conftest import get_auth_headers


class TestRegistration:
    def test_register_success(self, client, seed_roles):
        response = client.post('/api/v1/auth/register', json={
            'username': 'newuser',
            'email': 'new@test.com',
            'password': 'StrongPass1',
        })
        assert response.status_code == 201
        data = response.get_json()
        assert data['user']['username'] == 'newuser'

    def test_register_duplicate_email(self, client, seed_roles):
        client.post('/api/v1/auth/register', json={
            'username': 'user1', 'email': 'dup@test.com', 'password': 'StrongPass1',
        })
        response = client.post('/api/v1/auth/register', json={
            'username': 'user2', 'email': 'dup@test.com', 'password': 'StrongPass1',
        })
        assert response.status_code == 409

    def test_register_weak_password(self, client, seed_roles):
        response = client.post('/api/v1/auth/register', json={
            'username': 'weakuser', 'email': 'weak@test.com', 'password': 'weak',
        })
        assert response.status_code == 422

    def test_register_missing_fields(self, client, seed_roles):
        response = client.post('/api/v1/auth/register', json={
            'username': 'incomplete',
        })
        assert response.status_code == 422


class TestLogin:
    def test_login_success(self, client, seed_roles, viewer_user):
        response = client.post('/api/v1/auth/login', json={
            'email': 'viewer@test.com', 'password': 'TestPass1',
        })
        assert response.status_code == 200
        data = response.get_json()
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert data['user']['role'] == 'viewer'

    def test_login_wrong_password(self, client, seed_roles, viewer_user):
        response = client.post('/api/v1/auth/login', json={
            'email': 'viewer@test.com', 'password': 'WrongPass1',
        })
        assert response.status_code == 401

    def test_login_nonexistent_email(self, client, seed_roles):
        response = client.post('/api/v1/auth/login', json={
            'email': 'nobody@test.com', 'password': 'TestPass1',
        })
        assert response.status_code == 401


class TestLogout:
    def test_logout_success(self, client, seed_roles, viewer_user):
        headers = get_auth_headers(client, 'viewer@test.com')
        response = client.post('/api/v1/auth/logout', headers=headers)
        assert response.status_code == 200

    def test_logout_without_token(self, client):
        response = client.post('/api/v1/auth/logout')
        assert response.status_code == 401
