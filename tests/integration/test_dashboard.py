"""Integration tests for dashboard analytics endpoints."""

import pytest
from tests.conftest import get_auth_headers


class TestDashboard:
    def _seed_records(self, client, headers):
        """Create sample records for dashboard testing."""
        records = [
            {'amount': '5000.00', 'type': 'income', 'category': 'Salary', 'date': '2026-03-01'},
            {'amount': '1200.00', 'type': 'expense', 'category': 'Rent', 'date': '2026-03-05'},
            {'amount': '300.00', 'type': 'expense', 'category': 'Food', 'date': '2026-03-10'},
            {'amount': '200.00', 'type': 'expense', 'category': 'Transport', 'date': '2026-03-15'},
            {'amount': '1000.00', 'type': 'income', 'category': 'Freelance', 'date': '2026-03-20'},
        ]
        for r in records:
            client.post('/api/v1/records', json=r, headers=headers)

    def test_summary(self, client, seed_roles, manager_user, viewer_user):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        self._seed_records(client, mgr_headers)

        viewer_headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/dashboard/summary', headers=viewer_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'total_income' in data
        assert 'total_expenses' in data
        assert 'net_balance' in data

    def test_categories(self, client, seed_roles, manager_user, viewer_user):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        self._seed_records(client, mgr_headers)

        viewer_headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/dashboard/categories', headers=viewer_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert 'categories' in data
        assert 'top_expense_categories' in data

    def test_trends(self, client, seed_roles, manager_user, analyst_user):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        self._seed_records(client, mgr_headers)

        ana_headers = get_auth_headers(client, 'analyst@test.com')
        response = client.get('/api/v1/dashboard/trends?period=monthly&months=3', headers=ana_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert data['period'] == 'monthly'
        assert len(data['trends']) == 3

    def test_recent(self, client, seed_roles, manager_user, viewer_user):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        self._seed_records(client, mgr_headers)

        viewer_headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/dashboard/recent?limit=3', headers=viewer_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['recent_activity']) <= 3

    def test_empty_dashboard(self, client, seed_roles, viewer_user):
        """Dashboard with no records should return zeros, not errors."""
        headers = get_auth_headers(client, 'viewer@test.com')
        response = client.get('/api/v1/dashboard/summary', headers=headers)
        assert response.status_code == 200
