"""Integration tests for financial records CRUD."""

import pytest
from tests.conftest import get_auth_headers


class TestRecordsCRUD:
    def _create_record(self, client, headers, **overrides):
        data = {
            'amount': '1500.00', 'type': 'income', 'category': 'Salary',
            'date': '2026-03-15', 'description': 'Monthly salary',
            'tags': ['monthly', 'salary'],
        }
        data.update(overrides)
        return client.post('/api/v1/records', json=data, headers=headers)

    def test_create_record(self, client, seed_roles, manager_user):
        headers = get_auth_headers(client, 'manager@test.com')
        response = self._create_record(client, headers)
        assert response.status_code == 201
        data = response.get_json()
        assert data['record']['amount'] == '1500.00'
        assert data['record']['category'] == 'Salary'

    def test_create_record_validation(self, client, seed_roles, manager_user):
        headers = get_auth_headers(client, 'manager@test.com')

        # Missing required fields
        response = client.post('/api/v1/records', json={
            'amount': '100.00',
        }, headers=headers)
        assert response.status_code == 422

        # Invalid type
        response = client.post('/api/v1/records', json={
            'amount': '100.00', 'type': 'invalid', 'category': 'Test', 'date': '2026-03-15',
        }, headers=headers)
        assert response.status_code == 422

    def test_list_records(self, client, seed_roles, manager_user, analyst_user):
        # Create as manager
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        self._create_record(client, mgr_headers)
        self._create_record(client, mgr_headers, category='Rent', type='expense', amount='800.00')

        # List as analyst
        ana_headers = get_auth_headers(client, 'analyst@test.com')
        response = client.get('/api/v1/records', headers=ana_headers)
        assert response.status_code == 200
        data = response.get_json()
        assert len(data['records']) == 2

    def test_filter_by_type(self, client, seed_roles, manager_user, analyst_user):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        self._create_record(client, mgr_headers, type='income')
        self._create_record(client, mgr_headers, type='expense', category='Food', amount='50.00')

        ana_headers = get_auth_headers(client, 'analyst@test.com')
        response = client.get('/api/v1/records?type=expense', headers=ana_headers)
        data = response.get_json()
        assert all(r['type'] == 'expense' for r in data['records'])

    def test_update_record(self, client, seed_roles, manager_user):
        headers = get_auth_headers(client, 'manager@test.com')
        create_resp = self._create_record(client, headers)
        record_id = create_resp.get_json()['record']['id']

        response = client.put(f'/api/v1/records/{record_id}', json={
            'amount': '2000.00', 'description': 'Updated salary',
        }, headers=headers)
        assert response.status_code == 200
        assert response.get_json()['record']['amount'] == '2000.00'

    def test_soft_delete(self, client, seed_roles, manager_user, analyst_user):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        create_resp = self._create_record(client, mgr_headers)
        record_id = create_resp.get_json()['record']['id']

        # Soft delete
        response = client.delete(f'/api/v1/records/{record_id}', headers=mgr_headers)
        assert response.status_code == 200

        # Should not appear in listing
        ana_headers = get_auth_headers(client, 'analyst@test.com')
        list_resp = client.get('/api/v1/records', headers=ana_headers)
        ids = [r['id'] for r in list_resp.get_json()['records']]
        assert record_id not in ids

    def test_hard_delete_requires_admin(self, client, seed_roles, manager_user, admin_user, seed_permissions):
        mgr_headers = get_auth_headers(client, 'manager@test.com')
        create_resp = self._create_record(client, mgr_headers)
        record_id = create_resp.get_json()['record']['id']

        # Manager cannot hard delete
        response = client.delete(f'/api/v1/records/{record_id}?hard=true', headers=mgr_headers)
        assert response.status_code == 403

        # Admin can hard delete
        admin_headers = get_auth_headers(client, 'admin@test.com')
        response = client.delete(f'/api/v1/records/{record_id}?hard=true', headers=admin_headers)
        assert response.status_code == 200
