"""Integration tests for Role-Based Access Control."""

import pytest
from tests.conftest import get_auth_headers


class TestRBAC:
    def test_viewer_cannot_create_records(self, client, seed_roles, viewer_user):
        headers = get_auth_headers(client, 'viewer@test.com')
        response = client.post('/api/v1/records', json={
            'amount': '100.00', 'type': 'income', 'category': 'Salary', 'date': '2026-03-15',
        }, headers=headers)
        assert response.status_code == 403

    def test_analyst_cannot_create_records(self, client, seed_roles, analyst_user):
        headers = get_auth_headers(client, 'analyst@test.com')
        response = client.post('/api/v1/records', json={
            'amount': '100.00', 'type': 'income', 'category': 'Salary', 'date': '2026-03-15',
        }, headers=headers)
        assert response.status_code == 403

    def test_manager_can_create_records(self, client, seed_roles, manager_user):
        headers = get_auth_headers(client, 'manager@test.com')
        response = client.post('/api/v1/records', json={
            'amount': '100.00', 'type': 'income', 'category': 'Salary', 'date': '2026-03-15',
        }, headers=headers)
        assert response.status_code == 201

    def test_viewer_cannot_list_users(self, client, seed_roles, viewer_user):
        headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/users', headers=headers)
        assert response.status_code == 403

    def test_admin_can_list_users(self, client, seed_roles, admin_user):
        headers = get_auth_headers(client, 'admin@test.com')
        response = client.get('/api/v1/users', headers=headers)
        assert response.status_code == 200

    def test_viewer_can_access_dashboard(self, client, seed_roles, viewer_user):
        headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/dashboard/summary', headers=headers)
        assert response.status_code == 200

    def test_viewer_cannot_access_trends(self, client, seed_roles, viewer_user):
        headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/dashboard/trends', headers=headers)
        assert response.status_code == 403

    def test_analyst_can_access_trends(self, client, seed_roles, analyst_user):
        headers = get_auth_headers(client, 'analyst@test.com')
        response = client.get('/api/v1/dashboard/trends', headers=headers)
        assert response.status_code == 200

    def test_no_token_returns_401(self, client):
        response = client.get('/api/v1/records')
        assert response.status_code == 401

    def test_deactivated_user_blocked(self, client, db, seed_roles, viewer_user):
        # Login first
        headers = get_auth_headers(client, 'viewer@test.com')

        # Deactivate user
        viewer_user.is_active = False
        db.session.commit()

        # Re-login should fail
        response = client.post('/api/v1/auth/login', json={
            'email': 'viewer@test.com', 'password': 'TestPass1',
        })
        assert response.status_code == 401
